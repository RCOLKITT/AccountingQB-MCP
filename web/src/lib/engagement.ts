import { getSupabase } from "./supabase";

// Product-engagement health from tool_usage: active-account counts (DAU/WAU/MAU),
// stickiness (DAU/MAU), and "at-risk" accounts — paying/trialing customers that
// were active recently but have gone quiet in the last 7 days. Usage decline is
// the strongest leading indicator of churn, so this is the churn-prevention view.

export interface AtRiskAccount {
  license_key: string;
  email: string;
  tier: string;
  status: string;
  priorCalls: number; // calls in the [8,30]-day window
  lastActive: string; // ISO
}

export interface Engagement {
  dau: number;
  wau: number;
  mau: number;
  stickiness: number; // DAU/MAU as a percentage
  atRisk: AtRiskAccount[];
  atRiskCount: number;
}

interface EngRow {
  license_key: string;
  last_day: string | null;
  calls_7d: number;
  calls_prior: number;
  active_1d: boolean;
  active_7d: boolean;
  active_30d: boolean;
}
interface Lic {
  key: string;
  email: string;
  tier: string;
  status: string;
  is_test: boolean;
}

export async function getEngagement(): Promise<Engagement> {
  const sb = getSupabase();
  const today = new Date().toISOString().slice(0, 10); // UTC calendar day

  // Non-test licenses (identity + eligibility).
  const { data: licData } = await sb
    .from("licenses")
    .select("key, email, tier, status, is_test")
    .limit(50000);
  const licByKey = new Map<string, Lic>();
  for (const l of (licData as Lic[]) || []) licByKey.set(l.key, l);

  // Per-license 30-day activity windows, aggregated server-side over the rollup
  // (one bounded row per active license) instead of paging raw tool_usage. Active
  // day-buckets are calendar-day (UTC): DAU = active today, WAU = last 7d, MAU = 30d.
  const { data: engData } = await sb.rpc("engagement_by_license", {
    p_today: today,
  });

  let dau = 0,
    wau = 0,
    mau = 0;
  const atRisk: AtRiskAccount[] = [];
  for (const r of (engData as EngRow[]) || []) {
    const lic = licByKey.get(r.license_key);
    if (!lic || lic.is_test) continue;
    if (r.active_1d) dau += 1;
    if (r.active_7d) wau += 1;
    if (r.active_30d) mau += 1;
    // At-risk: was meaningfully active in the prior window, silent in the last 7
    // days, and still a live (paying/trialing) customer worth saving.
    const prior = Number(r.calls_prior || 0);
    const recent7 = Number(r.calls_7d || 0);
    if (
      prior >= 3 &&
      recent7 === 0 &&
      (lic.status === "active" || lic.status === "trialing")
    ) {
      atRisk.push({
        license_key: r.license_key,
        email: lic.email,
        tier: lic.tier,
        status: lic.status,
        priorCalls: prior,
        lastActive: r.last_day
          ? new Date(`${r.last_day}T00:00:00Z`).toISOString()
          : new Date(0).toISOString(),
      });
    }
  }
  atRisk.sort((x, y) => y.priorCalls - x.priorCalls);

  return {
    dau,
    wau,
    mau,
    stickiness: mau ? (dau / mau) * 100 : 0,
    atRisk: atRisk.slice(0, 25),
    atRiskCount: atRisk.length,
  };
}
