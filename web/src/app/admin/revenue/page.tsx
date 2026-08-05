import { getSupabase } from "@/lib/supabase";
import { getStripeRevenue } from "@/lib/stripe-revenue";
import { getNrr } from "@/lib/nrr";
import { unstable_cache } from "next/cache";

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

  // Reliable cancellation dates come from the subscription-deleted webhook
  // events — licenses.updated_at is bumped by ANY edit, so it is not a valid
  // cancel date for a churn-by-month trend.
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
  sixMonthsAgo.setDate(1);
  const { data: cancelEvents } = await supabase
    .from("event_logs")
    .select("created_at")
    .eq("action", "customer.subscription.deleted")
    .eq("success", true)
    .gte("created_at", sixMonthsAgo.toISOString())
    .limit(10000);
  const cancelsByMonth: Record<string, number> = {};
  for (const e of cancelEvents || []) {
    const k = monthKey(e.created_at as string);
    cancelsByMonth[k] = (cancelsByMonth[k] || 0) + 1;
  }

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

  // 6-month trend: signups (created_at) + cancellations (webhook events)
  const months: string[] = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(d.toISOString().slice(0, 7));
  }
  const trend = months.map((m) => ({
    month: m,
    signups: rows.filter((r) => monthKey(r.created_at) === m).length,
    churned: cancelsByMonth[m] || 0,
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

// Cache the three heavy reads (Supabase aggregate + Stripe API + NRR) for 60s —
// the Revenue page is the slowest (live Stripe calls) and doesn't need
// second-level freshness.
const getRevenue = unstable_cache(
  async () => Promise.all([getData(), getStripeRevenue(), getNrr()]),
  ["admin-revenue"],
  { revalidate: 60 }
);

export default async function RevenuePage() {
  const [d, stripe, nrr] = await getRevenue();
  const maxTrend = Math.max(1, ...d.trend.map((t) => Math.max(t.signups, t.churned)));
  const maxSnap = Math.max(1, ...nrr.trend.map((t) => t.mrr));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Revenue</h1>
        <p className="text-gray-400 mt-1">
          Real paying subscriptions only (test &amp; comp accounts excluded).
        </p>
      </div>

      {/* Live from Stripe — actual billed revenue + dunning + refunds */}
      {stripe ? (
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Live from Stripe</h2>
            <span className="text-xs text-emerald-400">actual billed amounts</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Metric label="MRR (real)" value={usd(stripe.mrr)} accent />
            <Metric label="Active subs" value={String(stripe.activeSubs)} />
            <Metric
              label="Past-due (dunning)"
              value={String(stripe.dunningSubs)}
              sub={`${usd(stripe.dunningMrr)}/mo at risk`}
            />
            <Metric
              label="Refunds (30d)"
              value={usd(stripe.refunds30d)}
              sub={`${stripe.refundCount30d} refunds`}
            />
            <Metric
              label="Stripe balance"
              value={usd(stripe.balanceAvailable)}
              sub={`${usd(stripe.balancePending)} pending`}
            />
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6 text-sm text-gray-400">
          Stripe not configured — the numbers below are list-price estimates. Set
          STRIPE_SECRET_KEY to see real billed MRR, dunning (failed payments), and
          refunds.
        </div>
      )}

      {/* Net Revenue Retention (from monthly MRR snapshots) */}
      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Net Revenue Retention</h2>
          <span className="text-xs text-gray-500">
            {nrr.accruing ? "accruing — needs 2 monthly snapshots" : `${nrr.prevMonth} → ${nrr.curMonth}`}
          </span>
        </div>
        {nrr.accruing ? (
          <p className="text-sm text-gray-400">
            The monthly MRR snapshot is capturing data. NRR, expansion/contraction,
            and the MRR trend appear once two months of snapshots exist.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Metric label="NRR" value={`${Math.round(nrr.nrr ?? 0)}%`} accent />
              <Metric label="GRR" value={`${Math.round(nrr.grr ?? 0)}%`} />
              <Metric label="Expansion" value={usd(nrr.expansion)} sub="upgrades" />
              <Metric label="Contraction" value={usd(nrr.contraction)} sub="downgrades" />
              <Metric label="Churned MRR" value={usd(nrr.churned)} sub="lost" />
            </div>
            {nrr.trend.length > 1 && (
              <div className="mt-6">
                <p className="mb-2 text-xs text-gray-400">MRR trend</p>
                <div className="flex h-24 items-end gap-2">
                  {nrr.trend.map((t) => (
                    <div key={t.month} className="flex flex-1 h-full flex-col items-center gap-1">
                      {/* flex-1 wrapper gives the % bar a definite height (was
                          collapsing to zero against the content-sized column). */}
                      <div className="w-full flex-1 flex items-end">
                        <div
                          className="w-full rounded-t bg-cyan-500/40"
                          style={{ height: `${(t.mrr / maxSnap) * 100}%` }}
                          title={usd(t.mrr)}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500">{t.month.slice(5)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Headline metrics (estimated from list prices — see Stripe panel for real) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="MRR (est.)" value={usd(d.mrr)} accent />
        <Metric label="ARR (est.)" value={usd(d.arr)} />
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
