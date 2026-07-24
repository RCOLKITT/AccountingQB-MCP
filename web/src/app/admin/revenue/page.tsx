import { getSupabase } from "@/lib/supabase";

// Revenue cockpit — MRR/ARR, paying customers, trial→paid conversion, paid
// churn, and a 6-month trend. Real subscriptions only (has a Stripe sub, not
// test/comp). Monthly USD prices per tier.

export const dynamic = "force-dynamic";

const TIER_MRR: Record<string, number> = {
  solopreneur: 39,
  business: 99,
  firm: 299,
};

interface Lic {
  status: string;
  tier: string;
  stripe_subscription_id: string | null;
  created_at: string;
  updated_at: string | null;
}

function monthKey(d: string): string {
  return new Date(d).toISOString().slice(0, 7); // YYYY-MM
}

async function getData() {
  const supabase = getSupabase();
  const { data } = await supabase
    .from("licenses")
    .select("status, tier, stripe_subscription_id, created_at, updated_at, is_test")
    .eq("is_test", false)
    .limit(10000);
  const rows = (data || []) as (Lic & { is_test: boolean })[];

  const paying = rows.filter(
    (r) => r.status === "active" && r.stripe_subscription_id
  );
  const mrr = paying.reduce((s, r) => s + (TIER_MRR[r.tier] || 0), 0);

  const byTier = Object.keys(TIER_MRR).map((tier) => {
    const t = paying.filter((r) => r.tier === tier);
    return { tier, count: t.length, mrr: t.length * (TIER_MRR[tier] || 0) };
  });

  // Paid churn = canceled AND had a real subscription. Expired trials are not churn.
  const paidChurn = rows.filter(
    (r) => r.status === "canceled" && r.stripe_subscription_id
  );
  const expiredTrials = rows.filter((r) => r.status === "expired");

  // Trial→paid conversion: of everyone past their trial (not currently trialing),
  // how many are paying now.
  const pastTrial = rows.filter((r) => r.status !== "trialing");
  const conversion = pastTrial.length
    ? (paying.length / pastTrial.length) * 100
    : 0;

  // Logo churn rate over the trailing window: paid cancels / (paying + paid cancels)
  const churnRate = paying.length + paidChurn.length
    ? (paidChurn.length / (paying.length + paidChurn.length)) * 100
    : 0;

  // 6-month trend: signups (created_at) + paid-cancels (updated_at)
  const months: string[] = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(d.toISOString().slice(0, 7));
  }
  const trend = months.map((m) => ({
    month: m,
    signups: rows.filter((r) => monthKey(r.created_at) === m).length,
    churned: paidChurn.filter((r) => r.updated_at && monthKey(r.updated_at) === m).length,
  }));

  return {
    mrr,
    arr: mrr * 12,
    payingCount: paying.length,
    arpu: paying.length ? mrr / paying.length : 0,
    conversion,
    churnRate,
    paidChurnCount: paidChurn.length,
    expiredTrials: expiredTrials.length,
    trialingCount: rows.filter((r) => r.status === "trialing").length,
    byTier,
    trend,
  };
}

const usd = (n: number) =>
  "$" + Math.round(n).toLocaleString("en-US");

export default async function RevenuePage() {
  const d = await getData();
  const maxTrend = Math.max(1, ...d.trend.map((t) => Math.max(t.signups, t.churned)));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Revenue</h1>
        <p className="text-gray-400 mt-1">
          Real paying subscriptions only (test &amp; comp accounts excluded).
        </p>
      </div>

      {/* Headline metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="MRR" value={usd(d.mrr)} accent />
        <Metric label="ARR" value={usd(d.arr)} />
        <Metric label="Paying customers" value={String(d.payingCount)} />
        <Metric label="ARPU" value={usd(d.arpu) + "/mo"} />
        <Metric label="Trial → paid" value={`${Math.round(d.conversion * 10) / 10}%`} sub="of completed trials" />
        <Metric label="Logo churn" value={`${Math.round(d.churnRate * 10) / 10}%`} sub={`${d.paidChurnCount} paid cancels`} />
        <Metric label="In trial now" value={String(d.trialingCount)} sub="pipeline" />
        <Metric label="Trials expired" value={String(d.expiredTrials)} sub="never converted" />
      </div>

      {/* MRR by tier */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="px-6 py-3 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">MRR by tier</h2>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-white/5">
              <th className="px-6 py-2 font-medium">Tier</th>
              <th className="px-6 py-2 font-medium">Customers</th>
              <th className="px-6 py-2 font-medium">Price</th>
              <th className="px-6 py-2 font-medium">MRR</th>
            </tr>
          </thead>
          <tbody>
            {d.byTier.map((t) => (
              <tr key={t.tier} className="border-b border-white/5">
                <td className="px-6 py-3 text-sm text-white capitalize">{t.tier}</td>
                <td className="px-6 py-3 text-sm text-gray-300">{t.count}</td>
                <td className="px-6 py-3 text-sm text-gray-500">{usd(TIER_MRR[t.tier])}/mo</td>
                <td className="px-6 py-3 text-sm text-cyan-400">{usd(t.mrr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 6-month trend */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h2 className="text-sm font-semibold text-white mb-4">Last 6 months</h2>
        <div className="space-y-3">
          {d.trend.map((t) => (
            <div key={t.month} className="flex items-center gap-4 text-xs">
              <span className="w-16 text-gray-500">{t.month}</span>
              <div className="flex-1 flex items-center gap-1">
                <div
                  className="h-5 rounded bg-cyan-500/40"
                  style={{ width: `${(t.signups / maxTrend) * 100}%`, minWidth: t.signups ? "8px" : 0 }}
                  title={`${t.signups} signups`}
                />
                <span className="text-gray-400">{t.signups} signups</span>
              </div>
              {t.churned > 0 && (
                <span className="text-red-400/80">↓ {t.churned} churned</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-600">
        MRR uses list prices ({usd(TIER_MRR.solopreneur)}/{usd(TIER_MRR.business)}/{usd(TIER_MRR.firm)} per tier).
        Paid churn excludes expired trials (those are trial non-conversions, tracked separately).
        CAD subscribers are counted at the USD-tier price as an approximation.
      </p>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "border-cyan-500/40 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent ? "text-cyan-300" : "text-white"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}
