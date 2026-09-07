import { getSupabase } from "@/lib/supabase";

/**
 * Server-side aggregation of MCP tool usage for the admin CEO dashboard.
 *
 * Aggregates over the permanent `tool_usage_daily` rollup via SQL RPCs (bounded to
 * ≤#tools / ≤#accounts rows) instead of paging every raw `tool_usage` row — the old
 * paginating scan grew unbounded and each page still risked the PostgREST cap.
 * Test/demo licenses (`is_test = true`) are excluded so numbers reflect real
 * customers. Windows (7/30/90d) are within the 90-day raw-retention window and the
 * rollup is ≤15 min fresh, so figures match live usage. `lastActive` is date-grain
 * (the rollup's UTC day).
 */

export interface ToolStat {
  tool: string;
  calls: number;
  minutesSaved: number;
}

export interface AccountUsage {
  licenseKey: string;
  email: string;
  tier: string;
  status: string;
  company: string | null;
  calls: number;
  minutesSaved: number;
  distinctTools: number;
  lastActive: string | null;
}

export interface TierUsage {
  tier: string;
  calls: number;
  activeAccounts: number;
}

export interface UsageAnalytics {
  totalCalls: number;
  activeAccounts: number;
  hoursSaved: number;
  avgCallsPerAccount: number;
  topTools: ToolStat[];
  byTier: TierUsage[];
  accounts: AccountUsage[];
  /** True when the tool_usage table has zero rows for real users in-range. */
  empty: boolean;
}

interface LicenseRow {
  key: string;
  email: string;
  tier: string;
  status: string;
  is_test: boolean;
}

/** Only 7/30/90 are accepted upstream; clamp defensively. */
export function normalizeDays(raw: string | undefined): number {
  return raw === "7" ? 7 : raw === "90" ? 90 : 30;
}

function emptyAnalytics(): UsageAnalytics {
  return {
    totalCalls: 0,
    activeAccounts: 0,
    hoursSaved: 0,
    avgCallsPerAccount: 0,
    topTools: [],
    byTier: [],
    accounts: [],
    empty: true,
  };
}

export async function getUsageAnalytics(days: number): Promise<UsageAnalytics> {
  const sb = getSupabase();
  // Rollup grain is UTC calendar day; convert the lookback to a since-date.
  const sinceDate = new Date(Date.now() - days * 86400000)
    .toISOString()
    .slice(0, 10);

  const [{ data: licenses }, { data: tokens }] = await Promise.all([
    sb
      .from("licenses")
      .select("key, email, tier, status, is_test")
      .limit(50000),
    sb.from("oauth_tokens").select("license_key, company_name").limit(50000),
  ]);

  const licByKey = new Map<string, LicenseRow>();
  for (const l of (licenses as LicenseRow[]) || []) licByKey.set(l.key, l);
  const nonTestKeys = [...licByKey.values()]
    .filter((l) => !l.is_test)
    .map((l) => l.key);

  if (nonTestKeys.length === 0) return emptyAnalytics();

  const companyByKey = new Map<string, string>();
  for (const t of (tokens as {
    license_key: string;
    company_name: string | null;
  }[]) || []) {
    if (t.company_name && !companyByKey.has(t.license_key)) {
      companyByKey.set(t.license_key, t.company_name);
    }
  }

  // Per-tool and per-account aggregates for real customers in-window (SQL-side).
  const [{ data: toolRows }, { data: acctRows }] = await Promise.all([
    sb.rpc("rollup_by_tool", { p_keys: nonTestKeys, p_since: sinceDate }),
    sb.rpc("rollup_by_license", { p_keys: nonTestKeys, p_since: sinceDate }),
  ]);

  const topTools: ToolStat[] = (
    (toolRows as { tool_name: string; calls: number; minutes: number }[]) || []
  )
    .map((r) => ({
      tool: r.tool_name,
      calls: Number(r.calls || 0),
      minutesSaved: Number(r.minutes || 0),
    }))
    .sort((x, y) => y.calls - x.calls);

  const accounts: AccountUsage[] = (
    (acctRows as {
      license_key: string;
      calls: number;
      minutes: number;
      distinct_tools: number;
      last_day: string;
    }[]) || []
  )
    .map((r) => {
      const l = licByKey.get(r.license_key);
      if (!l) return null;
      return {
        licenseKey: r.license_key,
        email: l.email,
        tier: l.tier,
        status: l.status,
        company: companyByKey.get(r.license_key) || null,
        calls: Number(r.calls || 0),
        minutesSaved: Number(r.minutes || 0),
        distinctTools: Number(r.distinct_tools || 0),
        lastActive: r.last_day,
      } as AccountUsage;
    })
    .filter((a): a is AccountUsage => a !== null)
    .sort((x, y) => y.calls - x.calls);

  const tierMap = new Map<string, TierUsage>();
  for (const a of accounts) {
    const tu = tierMap.get(a.tier) || {
      tier: a.tier,
      calls: 0,
      activeAccounts: 0,
    };
    tu.calls += a.calls;
    tu.activeAccounts += 1;
    tierMap.set(a.tier, tu);
  }

  const totalCalls = accounts.reduce((s, a) => s + a.calls, 0);
  const activeAccounts = accounts.length;
  const minutes = accounts.reduce((s, a) => s + a.minutesSaved, 0);

  return {
    totalCalls,
    activeAccounts,
    hoursSaved: Math.round(minutes / 6) / 10, // one decimal
    avgCallsPerAccount: activeAccounts
      ? Math.round((totalCalls / activeAccounts) * 10) / 10
      : 0,
    topTools,
    byTier: [...tierMap.values()].sort((x, y) => y.calls - x.calls),
    accounts,
    empty: totalCalls === 0,
  };
}
