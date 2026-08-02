import { getSupabase } from "./supabase";

// Logo retention by signup-month cohort: of the customers who signed up in a
// given month, how many are paying now vs. churned. Computed from licenses
// (test/comp excluded). A young cohort naturally shows more "in trial" — it
// hasn't settled yet — so read the older rows for a true retention signal.

export interface Cohort {
  month: string; // YYYY-MM
  size: number;
  paying: number; // active AND has a Stripe subscription
  trialing: number;
  churned: number; // canceled or expired
  retentionPct: number; // paying / size
}

interface Lic {
  status: string;
  stripe_subscription_id: string | null;
  created_at: string;
}

export async function getRetention(monthsBack = 8): Promise<Cohort[]> {
  const sb = getSupabase();
  const start = new Date();
  start.setMonth(start.getMonth() - (monthsBack - 1));
  start.setDate(1);
  start.setHours(0, 0, 0, 0);

  const { data } = await sb
    .from("licenses")
    .select("status, stripe_subscription_id, created_at, is_test")
    .eq("is_test", false)
    .gte("created_at", start.toISOString())
    .limit(50000);
  const rows = (data as (Lic & { is_test: boolean })[]) || [];

  const byMonth = new Map<string, Cohort>();
  for (let i = 0; i < monthsBack; i++) {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
    const key = d.toISOString().slice(0, 7);
    byMonth.set(key, {
      month: key,
      size: 0,
      paying: 0,
      trialing: 0,
      churned: 0,
      retentionPct: 0,
    });
  }

  for (const r of rows) {
    const key = new Date(r.created_at).toISOString().slice(0, 7);
    const c = byMonth.get(key);
    if (!c) continue;
    c.size += 1;
    if (r.status === "active" && r.stripe_subscription_id) c.paying += 1;
    else if (r.status === "trialing") c.trialing += 1;
    else if (r.status === "canceled" || r.status === "expired") c.churned += 1;
  }

  const cohorts = [...byMonth.values()];
  for (const c of cohorts) {
    c.retentionPct = c.size ? (c.paying / c.size) * 100 : 0;
  }
  return cohorts;
}
