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

interface UsageRow {
  license_key: string;
  invoked_at: string;
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
  const now = Date.now();
  const DAY = 86400000;
  const since30 = new Date(now - 30 * DAY).toISOString();

  // Non-test licenses (identity + eligibility) and the last 30 days of usage.
  const { data: licData } = await sb
    .from("licenses")
    .select("key, email, tier, status, is_test")
    .limit(50000);
  const licByKey = new Map<string, Lic>();
  for (const l of (licData as Lic[]) || []) licByKey.set(l.key, l);

  const usage: UsageRow[] = [];
  const PAGE = 1000;
  for (let from = 0; from <= 500000; from += PAGE) {
    const { data } = await sb
      .from("tool_usage")
      .select("license_key, invoked_at")
      .gte("invoked_at", since30)
      .order("invoked_at", { ascending: false })
      .range(from, from + PAGE - 1);
    const rows = (data as UsageRow[]) || [];
    usage.push(...rows);
    if (rows.length < PAGE) break;
  }

  // Per real (non-test) account: active-day buckets + call counts by window.
  interface Acc {
    d1: boolean;
    d7: boolean;
    d30: boolean;
    recent7: number; // calls in last 7 days
    prior: number; // calls in [8,30] days
    lastActive: number; // ms
  }
  const acc = new Map<string, Acc>();
  for (const r of usage) {
    const lic = licByKey.get(r.license_key);
    if (!lic || lic.is_test) continue;
    const t = new Date(r.invoked_at).getTime();
    const ageDays = (now - t) / DAY;
    const a = acc.get(r.license_key) || {
      d1: false,
      d7: false,
      d30: false,
      recent7: 0,
      prior: 0,
      lastActive: 0,
    };
    if (ageDays <= 1) a.d1 = true;
    if (ageDays <= 7) {
      a.d7 = true;
      a.recent7 += 1;
    } else if (ageDays <= 30) {
      a.prior += 1;
    }
    a.d30 = true;
    if (t > a.lastActive) a.lastActive = t;
    acc.set(r.license_key, a);
  }

  let dau = 0,
    wau = 0,
    mau = 0;
  const atRisk: AtRiskAccount[] = [];
  for (const [key, a] of acc) {
    if (a.d1) dau += 1;
    if (a.d7) wau += 1;
    if (a.d30) mau += 1;
    // At-risk: was meaningfully active in the prior window, silent in the last 7
    // days, and still a live (paying/trialing) customer worth saving.
    const lic = licByKey.get(key)!;
    if (
      a.prior >= 3 &&
      a.recent7 === 0 &&
      (lic.status === "active" || lic.status === "trialing")
    ) {
      atRisk.push({
        license_key: key,
        email: lic.email,
        tier: lic.tier,
        status: lic.status,
        priorCalls: a.prior,
        lastActive: new Date(a.lastActive).toISOString(),
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
