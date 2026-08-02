import { getSupabase } from "./supabase";

// Net & Gross Revenue Retention from mrr_snapshots. Takes the two most recent
// snapshot months; for the cohort of accounts present in the earlier month,
// compares their MRR then vs. now. Needs >=2 snapshot months to produce a
// number (returns null while "accruing"). All money in dollars.

export interface NrrResult {
  accruing: boolean; // true until >=2 snapshot months exist
  prevMonth: string | null;
  curMonth: string | null;
  startMrr: number; // cohort MRR in the earlier month
  endMrr: number; // same cohort's MRR now
  expansion: number;
  contraction: number;
  churned: number;
  nrr: number | null; // endMrr / startMrr (%)
  grr: number | null; // (startMrr - contraction - churned) / startMrr (%)
  trend: { month: string; mrr: number }[]; // total MRR by month
}

const EMPTY: NrrResult = {
  accruing: true,
  prevMonth: null,
  curMonth: null,
  startMrr: 0,
  endMrr: 0,
  expansion: 0,
  contraction: 0,
  churned: 0,
  nrr: null,
  grr: null,
  trend: [],
};

export async function getNrr(): Promise<NrrResult> {
  const sb = getSupabase();
  const { data } = await sb
    .from("mrr_snapshots")
    .select("month, license_key, mrr_cents")
    .order("month", { ascending: false })
    .limit(100000);
  const rows = (data as { month: string; license_key: string; mrr_cents: number }[]) || [];
  if (rows.length === 0) return EMPTY;

  // Total MRR by month (for the trend), oldest→newest.
  const byMonth = new Map<string, number>();
  for (const r of rows) byMonth.set(r.month, (byMonth.get(r.month) || 0) + r.mrr_cents);
  const trend = [...byMonth.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, cents]) => ({ month, mrr: cents / 100 }));

  const months = [...byMonth.keys()].sort((a, b) => b.localeCompare(a)); // newest first
  if (months.length < 2) return { ...EMPTY, trend };

  const [cur, prev] = [months[0], months[1]];
  const prevMap = new Map<string, number>();
  const curMap = new Map<string, number>();
  for (const r of rows) {
    if (r.month === prev) prevMap.set(r.license_key, r.mrr_cents);
    else if (r.month === cur) curMap.set(r.license_key, r.mrr_cents);
  }

  let startMrr = 0,
    endMrr = 0,
    expansion = 0,
    contraction = 0,
    churned = 0;
  for (const [key, s] of prevMap) {
    startMrr += s;
    const e = curMap.get(key) ?? 0;
    endMrr += e;
    const d = e - s;
    if (e === 0) churned += s;
    else if (d > 0) expansion += d;
    else if (d < 0) contraction += -d;
  }

  const c = (n: number) => n / 100;
  return {
    accruing: false,
    prevMonth: prev,
    curMonth: cur,
    startMrr: c(startMrr),
    endMrr: c(endMrr),
    expansion: c(expansion),
    contraction: c(contraction),
    churned: c(churned),
    nrr: startMrr ? (endMrr / startMrr) * 100 : null,
    grr: startMrr ? ((startMrr - contraction - churned) / startMrr) * 100 : null,
    trend,
  };
}
