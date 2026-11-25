import Stripe from "stripe";
import { getStripe } from "./stripe";

// Real revenue straight from Stripe — actual billed amounts (not list-price
// estimates), plus dunning (past-due/unpaid subscriptions = involuntary churn
// risk), refunds, and the current Stripe cash balance. Returns null when Stripe
// isn't configured so the page can degrade gracefully.
//
// MONEY IS NEVER BLENDED ACROSS CURRENCIES. A subscription billed in CAD and
// one billed in USD are reported on separate lines. We bill some customers in
// CAD against a USD-based price (subscription.currency = "cad" while
// price.currency = "usd"), so the ONLY correct currency for a sub is
// `subscription.currency` — `price.unit_amount` is the amount billed, but in
// the SUBSCRIPTION's currency. Summing price.unit_amount across subs and
// calling it USD overstated MRR by ~18% (two CAD subs counted at face value).

export interface CurrencyAmount {
  currency: string; // upper-case ISO, e.g. "USD", "CAD"
  amount: number; // major units (dollars)
}

export interface StripeRevenue {
  // Per-currency so a reader never adds CAD to USD. Sorted by amount desc.
  mrrByCurrency: CurrencyAmount[];
  activeSubs: number;
  dunningSubs: number; // past_due + unpaid subscriptions
  dunningMrrByCurrency: CurrencyAmount[]; // MRR at risk, per currency
  refunds30d: number; // $ refunded in the last 30 days (USD only; see note)
  refundCount30d: number;
  balanceByCurrency: {
    currency: string;
    available: number;
    pending: number;
  }[];
}

/** Normalize a recurring amount (in minor units) to a monthly figure. */
export function toMonthly(
  amountMinor: number,
  interval: string | undefined,
  count = 1,
): number {
  const base = amountMinor * (count || 1);
  switch (interval) {
    case "year":
      return base / 12;
    case "week":
      return base * (52 / 12);
    case "day":
      return base * (365 / 12);
    default: // month (or unknown recurring)
      return base;
  }
}

/**
 * Sum normalized monthly recurring revenue, GROUPED BY the subscription's
 * billing currency. Each sub's amount is attributed to `subscription.currency`
 * (what the customer is actually charged in), never the price's base currency.
 * Returns major-unit amounts sorted by size, so the caller can render one line
 * per currency and never blend them into a single wrong number.
 */
export function mrrByCurrency(subs: Stripe.Subscription[]): CurrencyAmount[] {
  const cents = new Map<string, number>();
  for (const sub of subs) {
    const currency = (sub.currency || "usd").toUpperCase();
    const subCents = sub.items.data.reduce((t, it) => {
      const price = it.price;
      return (
        t +
        toMonthly(
          price.unit_amount || 0,
          price.recurring?.interval,
          it.quantity ?? 1,
        )
      );
    }, 0);
    cents.set(currency, (cents.get(currency) || 0) + subCents);
  }
  return [...cents.entries()]
    .map(([currency, c]) => ({ currency, amount: c / 100 }))
    .sort((a, b) => b.amount - a.amount);
}

export async function getStripeRevenue(): Promise<StripeRevenue | null> {
  if (!process.env.STRIPE_SECRET_KEY) return null;
  const stripe = getStripe();
  try {
    const listSubs = (status: Stripe.SubscriptionListParams.Status) =>
      stripe.subscriptions
        .list({ status, limit: 100, expand: ["data.items.data.price"] })
        .autoPagingToArray({ limit: 10000 });

    // All five Stripe reads are independent — one parallel batch instead of three
    // sequential round-trips (Stripe calls dominate this page's latency).
    const since = Math.floor(Date.now() / 1000) - 30 * 86400;
    const [active, pastDue, unpaid, refunds, balance] = await Promise.all([
      listSubs("active"),
      listSubs("past_due"),
      listSubs("unpaid"),
      stripe.refunds
        .list({ created: { gte: since }, limit: 100 })
        .autoPagingToArray({ limit: 10000 }),
      stripe.balance.retrieve(),
    ]);

    const dunning = [...pastDue, ...unpaid];

    // Balance is already one bucket per currency — keep them separate, never
    // add a CAD payout to a USD payout.
    const balanceByCurrency = balance.available.map((a) => {
      const pending =
        balance.pending.find((p) => p.currency === a.currency)?.amount || 0;
      return {
        currency: a.currency.toUpperCase(),
        available: a.amount / 100,
        pending: pending / 100,
      };
    });

    return {
      mrrByCurrency: mrrByCurrency(active),
      activeSubs: active.length,
      dunningSubs: dunning.length,
      dunningMrrByCurrency: mrrByCurrency(dunning),
      // Refunds are reported in their own currencies by Stripe; we surface the
      // USD-denominated ones (the vast majority) and the count of all.
      refunds30d:
        refunds
          .filter((r) => (r.currency || "usd") === "usd")
          .reduce((s, r) => s + (r.amount || 0), 0) / 100,
      refundCount30d: refunds.length,
      balanceByCurrency,
    };
  } catch (e) {
    console.error("Stripe revenue fetch failed:", e);
    return null;
  }
}
