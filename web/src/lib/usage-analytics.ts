import { getSupabase } from "@/lib/supabase";

/**
 * Server-side aggregation of MCP tool usage for the admin CEO dashboard.
 * Reads the `tool_usage` table (populated by the MCP server after each tool
 * invocation) joined to `licenses` and `oauth_tokens`. Test/demo licenses
 * (`is_test = true`) are excluded so the numbers reflect real customers.
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

interface UsageRow {
  license_key: string;
  tool_name: string;
  time_saved_minutes: number | null;
  invoked_at: string;
}

/** Only 7/30/90 are accepted upstream; clamp defensively. */
export function normalizeDays(raw: string | undefined): number {
  return raw === "7" ? 7 : raw === "90" ? 90 : 30;
}

export async function getUsageAnalytics(days: number): Promise<UsageAnalytics> {
  const sb = getSupabase();
  const since = new Date(Date.now() - days * 86400000).toISOString();

  const [{ data: licenses }, { data: tokens }, { data: usage }] = await Promise.all([
    sb.from("licenses").select("key, email, tier, status, is_test"),
    sb.from("oauth_tokens").select("license_key, company_name"),
    sb
      .from("tool_usage")
      .select("license_key, tool_name, time_saved_minutes, invoked_at")
      .gte("invoked_at", since)
      .order("invoked_at", { ascending: false }),
  ]);

  const licByKey = new Map<string, LicenseRow>();
  for (const l of (licenses as LicenseRow[]) || []) licByKey.set(l.key, l);

  const companyByKey = new Map<string, string>();
  for (const t of (tokens as { license_key: string; company_name: string | null }[]) || []) {
    if (t.company_name && !companyByKey.has(t.license_key)) {
      companyByKey.set(t.license_key, t.company_name);
    }
  }

  // Only real customers' usage.
  const rows = ((usage as UsageRow[]) || []).filter((r) => {
    const l = licByKey.get(r.license_key);
    return l && !l.is_test;
  });

  const toolAgg = new Map<string, ToolStat>();
  const acctAgg = new Map<string, AccountUsage & { tools: Set<string> }>();

  for (const r of rows) {
    const l = licByKey.get(r.license_key)!;
    const mins = r.time_saved_minutes || 0;

    const t = toolAgg.get(r.tool_name) || { tool: r.tool_name, calls: 0, minutesSaved: 0 };
    t.calls += 1;
    t.minutesSaved += mins;
    toolAgg.set(r.tool_name, t);

    let a = acctAgg.get(r.license_key);
    if (!a) {
      a = {
        licenseKey: r.license_key,
        email: l.email,
        tier: l.tier,
        status: l.status,
        company: companyByKey.get(r.license_key) || null,
        calls: 0,
        minutesSaved: 0,
        distinctTools: 0,
        lastActive: r.invoked_at,
        tools: new Set<string>(),
      };
      acctAgg.set(r.license_key, a);
    }
    a.calls += 1;
    a.minutesSaved += mins;
    a.tools.add(r.tool_name);
    // rows are ordered newest-first, so the first seen is the most recent.
  }

  const topTools = [...toolAgg.values()].sort((x, y) => y.calls - x.calls);

  const accounts: AccountUsage[] = [...acctAgg.values()]
    .map(({ tools, ...a }) => ({ ...a, distinctTools: tools.size }))
    .sort((x, y) => y.calls - x.calls);

  const tierMap = new Map<string, TierUsage>();
  for (const a of accounts) {
    const tu = tierMap.get(a.tier) || { tier: a.tier, calls: 0, activeAccounts: 0 };
    tu.calls += a.calls;
    tu.activeAccounts += 1;
    tierMap.set(a.tier, tu);
  }

  const totalCalls = rows.length;
  const activeAccounts = accounts.length;
  const minutes = rows.reduce((s, r) => s + (r.time_saved_minutes || 0), 0);

  return {
    totalCalls,
    activeAccounts,
    hoursSaved: Math.round(minutes / 6) / 10, // one decimal
    avgCallsPerAccount: activeAccounts ? Math.round((totalCalls / activeAccounts) * 10) / 10 : 0,
    topTools,
    byTier: [...tierMap.values()].sort((x, y) => y.calls - x.calls),
    accounts,
    empty: totalCalls === 0,
  };
}
