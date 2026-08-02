import Stripe from "stripe";
import { getStripe } from "./stripe";

// Real revenue straight from Stripe — actual billed amounts (not list-price
// estimates), plus dunning (past-due/unpaid subscriptions = involuntary churn
// risk), refunds, and the current Stripe cash balance. Returns null when Stripe
// isn't configured so the page can degrade gracefully.

export interface StripeRevenue {
  mrr: number; // real monthly recurring revenue, USD, annual normalized to /12
  activeSubs: number;
  dunningSubs: number; // past_due + unpaid subscriptions
  dunningMrr: number; // MRR at risk from those
  refunds30d: number; // $ refunded in the last 30 days
  refundCount30d: number;
  balanceAvailable: number;
  balancePending: number;
  currency: string;
}

/** Normalize a recurring amount (in minor units) to a monthly figure. */
export function toMonthly(
  amountMinor: number,
  interval: string | undefined,
  count = 1
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

/** Sum normalized monthly recurring revenue across a set of subscriptions. */
export function subscriptionsMrr(subs: Stripe.Subscription[]): number {
  const cents = subs.reduce(
    (s, sub) =>
      s +
      sub.items.data.reduce((t, it) => {
        const price = it.price;
        return (
          t +
          toMonthly(
            price.unit_amount || 0,
            price.recurring?.interval,
            it.quantity ?? 1
          )
        );
      }, 0),
    0
  );
  return cents / 100;
}

export async function getStripeRevenue(): Promise<StripeRevenue | null> {
  if (!process.env.STRIPE_SECRET_KEY) return null;
  const stripe = getStripe();
  try {
    const listSubs = (status: Stripe.SubscriptionListParams.Status) =>
      stripe.subscriptions
        .list({ status, limit: 100, expand: ["data.items.data.price"] })
        .autoPagingToArray({ limit: 10000 });

    const [active, pastDue, unpaid] = await Promise.all([
      listSubs("active"),
      listSubs("past_due"),
      listSubs("unpaid"),
    ]);

    const dunning = [...pastDue, ...unpaid];
    const since = Math.floor(Date.now() / 1000) - 30 * 86400;
    const refunds = await stripe.refunds
      .list({ created: { gte: since }, limit: 100 })
      .autoPagingToArray({ limit: 10000 });
    const balance = await stripe.balance.retrieve();

    const sumBalance = (arr: Stripe.Balance.Available[] | Stripe.Balance.Pending[]) =>
      arr.reduce((s, b) => s + b.amount, 0) / 100;

    return {
      mrr: subscriptionsMrr(active),
      activeSubs: active.length,
      dunningSubs: dunning.length,
      dunningMrr: subscriptionsMrr(dunning),
      refunds30d: refunds.reduce((s, r) => s + (r.amount || 0), 0) / 100,
      refundCount30d: refunds.length,
      balanceAvailable: sumBalance(balance.available),
      balancePending: sumBalance(balance.pending),
      currency: (balance.available[0]?.currency || "usd").toUpperCase(),
    };
  } catch (e) {
    console.error("Stripe revenue fetch failed:", e);
    return null;
  }
}
