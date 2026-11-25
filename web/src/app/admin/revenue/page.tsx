import { getSupabase } from "@/lib/supabase";
import { getStripeRevenue } from "@/lib/stripe-revenue";
import { getNrr } from "@/lib/nrr";
import { unstable_cache } from "next/cache";

// Revenue cockpit — MRR/ARR, paying customers, trial→paid conversion, paid
// churn, and a 6-month trend. Real subscriptions only (has a Stripe sub, not
// test/comp).
//
// DOLLARS COME FROM STRIPE, PER CURRENCY. The "Live from Stripe" panel is the
// source of truth for MRR and is reported one line per billing currency (we
// bill some customers in CAD) — never blended into a single USD figure. The
// list-price table below is a COUNT view only + a fallback when Stripe isn't
// configured; it is explicitly labeled as a USD list-price estimate.

export const dynamic = "force-dynamic";

// USD monthly list prices per tier — used only for the Stripe-not-configured
// fallback estimate and as a reference column. Not summed across currencies.
const TIER_LIST_USD: Record<string, number> = {
  solopreneur: 39,
  business: 99,
  firm: 299,
};

// Everything on this page is a COUNT, so we ask Postgres for exact counts
// (head: true — no rows transferred) instead of scanning a capped select. That
// is accurate at any scale, with no row cap to undercount past.
async function getData() {
  const supabase = getSupabase();
  const tiers = Object.keys(TIER_LIST_USD);

  const lic = () =>
    supabase
      .from("licenses")
      .select("*", { count: "exact", head: true })
      .eq("is_test", false);
  const countOf = async (
    b: PromiseLike<{ count: number | null }>,
  ): Promise<number> => (await b).count ?? 0;

  // 6 calendar months (oldest→newest) with [start, end) bounds.
  const now = new Date();
  const months = Array.from({ length: 6 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (5 - i), 1);
    const end = new Date(d.getFullYear(), d.getMonth() + 1, 1);
    return {
      key: d.toISOString().slice(0, 7),
      start: d.toISOString(),
      end: end.toISOString(),
    };
  });

  const [
    tierCounts,
    trialingCount,
    expiredTrials,
    paidChurnCount,
    pastTrialCount,
    signupTrend,
    churnTrend,
  ] = await Promise.all([
    Promise.all(
      tiers.map((t) =>
        countOf(
          lic()
            .eq("status", "active")
            .not("stripe_subscription_id", "is", null)
            .eq("tier", t),
        ),
      ),
    ),
    countOf(lic().eq("status", "trialing")),
    countOf(lic().eq("status", "expired")),
    countOf(
      lic().eq("status", "canceled").not("stripe_subscription_id", "is", null),
    ),
    countOf(lic().neq("status", "trialing")),
    Promise.all(
      months.map((m) =>
        countOf(lic().gte("created_at", m.start).lt("created_at", m.end)),
      ),
    ),
    // Reliable cancel dates come from the subscription-deleted webhook events
    // (licenses.updated_at is bumped by any edit, so it's not a valid date).
    Promise.all(
      months.map((m) =>
        countOf(
          supabase
            .from("event_logs")
            .select("*", { count: "exact", head: true })
            .eq("action", "customer.subscription.deleted")
            .eq("success", true)
            .gte("created_at", m.start)
            .lt("created_at", m.end),
        ),
      ),
    ),
  ]);

  // Customer COUNT per tier (accurate). The estimate column multiplies by the
  // USD list price and is a fallback reference only — real MRR comes from the
  // per-currency Stripe panel, since a tier can hold both USD and CAD subs.
  const byTier = tiers.map((tier, i) => ({
    tier,
    count: tierCounts[i],
    estMrrUsd: tierCounts[i] * (TIER_LIST_USD[tier] || 0),
  }));
  const payingCount = tierCounts.reduce((a, b) => a + b, 0);
  const estMrrUsd = byTier.reduce((s, t) => s + t.estMrrUsd, 0);
  const conversion = pastTrialCount ? (payingCount / pastTrialCount) * 100 : 0;
  const churnRate =
    payingCount + paidChurnCount
      ? (paidChurnCount / (payingCount + paidChurnCount)) * 100
      : 0;
  const trend = months.map((m, i) => ({
    month: m.key,
    signups: signupTrend[i],
    churned: churnTrend[i],
  }));

  return {
    estMrrUsd, // USD list-price estimate — fallback / reference only
    payingCount,
    conversion,
    churnRate,
    paidChurnCount,
    expiredTrials,
    trialingCount,
    byTier,
    trend,
  };
}

const usd = (n: number) => "$" + Math.round(n).toLocaleString("en-US");
// Format a per-currency amount, e.g. "US$138", "CA$138".
const money = (currency: string, n: number) => {
  const sym: Record<string, string> = { USD: "US$", CAD: "CA$" };
  return (
    (sym[currency] || currency + " ") + Math.round(n).toLocaleString("en-US")
  );
};

// Cache the three heavy reads (Supabase aggregate + Stripe API + NRR) for 60s —
// the Revenue page is the slowest (live Stripe calls) and doesn't need
// second-level freshness.
const getRevenue = unstable_cache(
  async () => Promise.all([getData(), getStripeRevenue(), getNrr()]),
  ["admin-revenue"],
  { revalidate: 60 },
);

export default async function RevenuePage() {
  const [d, stripe, nrr] = await getRevenue();
  const maxTrend = Math.max(
    1,
    ...d.trend.map((t) => Math.max(t.signups, t.churned)),
  );
  const maxSnap = Math.max(1, ...nrr.trend.map((t) => t.mrr));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Revenue</h1>
        <p className="text-gray-400 mt-1">
          Real paying subscriptions only (test &amp; comp accounts excluded) ·
          pulls live from Stripe, refreshed at most every 60s.
        </p>
      </div>

      {/* Live from Stripe — actual billed revenue, PER CURRENCY (never blended) */}
      {stripe ? (
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">
              Live from Stripe
            </h2>
            <span className="text-xs text-emerald-400">
              actual billed amounts · per currency
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* One MRR metric per billing currency — USD and CAD are not added
                together (doing so overstated MRR by ~18%). */}
            {stripe.mrrByCurrency.length > 0 ? (
              stripe.mrrByCurrency.map((m, i) => (
                <Metric
                  key={m.currency}
                  label={`MRR · ${m.currency}`}
                  value={money(m.currency, m.amount)}
                  sub={`${money(m.currency, m.amount * 12)} ARR`}
                  accent={i === 0}
                />
              ))
            ) : (
              <Metric label="MRR" value="$0" accent />
            )}
            <Metric label="Active subs" value={String(stripe.activeSubs)} />
            <Metric
              label="Past-due (dunning)"
              value={String(stripe.dunningSubs)}
              sub={
                stripe.dunningMrrByCurrency
                  .map((m) => `${money(m.currency, m.amount)}/mo`)
                  .join(" + ") || "none at risk"
              }
            />
            <Metric
              label="Refunds 30d (USD)"
              value={usd(stripe.refunds30d)}
              sub={`${stripe.refundCount30d} refunds (all cur.)`}
            />
          </div>
          <div className="mt-4 border-t border-white/5 pt-4">
            <p className="mb-2 text-xs text-gray-400">Stripe balance</p>
            <div className="flex flex-wrap gap-4 text-sm">
              {stripe.balanceByCurrency.length > 0 ? (
                stripe.balanceByCurrency.map((b) => (
                  <span key={b.currency} className="text-gray-300">
                    <span className="font-semibold text-white">
                      {money(b.currency, b.available)}
                    </span>{" "}
                    available
                    <span className="text-gray-500">
                      {" "}
                      · {money(b.currency, b.pending)} pending
                    </span>
                  </span>
                ))
              ) : (
                <span className="text-gray-500">—</span>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6 text-sm text-gray-400">
          Stripe not configured — the numbers below are USD list-price
          estimates. Set STRIPE_SECRET_KEY to see real billed MRR per currency,
          dunning (failed payments), and refunds.
        </div>
      )}

      {/* Net Revenue Retention (from monthly MRR snapshots) */}
      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            Net Revenue Retention
          </h2>
          <span className="text-xs text-gray-500">
            {nrr.accruing
              ? "accruing — needs 2 monthly snapshots"
              : `${nrr.prevMonth} → ${nrr.curMonth}`}
          </span>
        </div>
        {nrr.accruing ? (
          <p className="text-sm text-gray-400">
            The monthly MRR snapshot is capturing data. NRR,
            expansion/contraction, and the MRR trend appear once two months of
            snapshots exist.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Metric
                label="NRR"
                value={`${Math.round(nrr.nrr ?? 0)}%`}
                accent
              />
              <Metric label="GRR" value={`${Math.round(nrr.grr ?? 0)}%`} />
              <Metric
                label="Expansion"
                value={usd(nrr.expansion)}
                sub="upgrades"
              />
              <Metric
                label="Contraction"
                value={usd(nrr.contraction)}
                sub="downgrades"
              />
              <Metric label="Churned MRR" value={usd(nrr.churned)} sub="lost" />
            </div>
            {nrr.trend.length > 1 && (
              <div className="mt-6">
                <p className="mb-2 text-xs text-gray-400">MRR trend</p>
                <div className="flex h-24 items-end gap-2">
                  {nrr.trend.map((t) => (
                    <div
                      key={t.month}
                      className="flex flex-1 h-full flex-col items-center gap-1"
                    >
                      {/* flex-1 wrapper gives the % bar a definite height (was
                          collapsing to zero against the content-sized column). */}
                      <div className="w-full flex-1 flex items-end">
                        <div
                          className="w-full rounded-t bg-cyan-500/40"
                          style={{ height: `${(t.mrr / maxSnap) * 100}%` }}
                          title={usd(t.mrr)}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500">
                        {t.month.slice(5)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Operational metrics — COUNTS and rates (currency-agnostic). Dollar MRR
          lives in the per-currency Stripe panel above. The est. MRR appears
          only as a reference here and as the fallback when Stripe is off. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="Paying customers" value={String(d.payingCount)} accent />
        <Metric
          label="In trial now"
          value={String(d.trialingCount)}
          sub="pipeline"
        />
        <Metric
          label="Trial → paid"
          value={`${Math.round(d.conversion * 10) / 10}%`}
          sub="of completed trials"
        />
        <Metric
          label="Logo churn"
          value={`${Math.round(d.churnRate * 10) / 10}%`}
          sub={`${d.paidChurnCount} paid cancels`}
        />
        <Metric
          label="Trials expired"
          value={String(d.expiredTrials)}
          sub="never converted"
        />
        {!stripe && (
          <>
            <Metric label="MRR (USD est.)" value={usd(d.estMrrUsd)} />
            <Metric label="ARR (USD est.)" value={usd(d.estMrrUsd * 12)} />
          </>
        )}
      </div>

      {/* Customers by tier — COUNT view. Dollar MRR is per-currency in the
          Stripe panel; a tier can hold both USD and CAD subs, so a single
          blended MRR-per-tier column would be wrong. */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="px-6 py-3 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">
            Customers by tier
          </h2>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-white/5">
              <th className="px-6 py-2 font-medium">Tier</th>
              <th className="px-6 py-2 font-medium">Paying customers</th>
              <th className="px-6 py-2 font-medium">List price (USD)</th>
            </tr>
          </thead>
          <tbody>
            {d.byTier.map((t) => (
              <tr key={t.tier} className="border-b border-white/5">
                <td className="px-6 py-3 text-sm text-white capitalize">
                  {t.tier}
                </td>
                <td className="px-6 py-3 text-sm text-cyan-400">{t.count}</td>
                <td className="px-6 py-3 text-sm text-gray-500">
                  {usd(TIER_LIST_USD[t.tier])}/mo
                </td>
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
                  style={{
                    width: `${(t.signups / maxTrend) * 100}%`,
                    minWidth: t.signups ? "8px" : 0,
                  }}
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
        Dollar MRR comes from Stripe, reported per billing currency — USD and
        CAD are never added together. The list-price estimate (
        {usd(TIER_LIST_USD.solopreneur)}/{usd(TIER_LIST_USD.business)}/
        {usd(TIER_LIST_USD.firm)} per tier, USD) is a reference/fallback only.
        Paid churn excludes expired trials (those are trial non-conversions,
        tracked separately).
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
    <div
      className={`rounded-xl border p-5 ${accent ? "border-cyan-500/40 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}
    >
      <p className="text-xs text-gray-400">{label}</p>
      <p
        className={`text-2xl font-bold mt-1 ${accent ? "text-cyan-300" : "text-white"}`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}
