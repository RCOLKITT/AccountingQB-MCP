import type Stripe from "stripe";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import { logEvent } from "@/lib/event-logger";

export type LicenseStatus = "active" | "trialing" | "canceled" | "expired";

/**
 * Canonical Stripe `subscription.status` → our `licenses.status`. The SINGLE source
 * of truth shared by the webhook and by reconciliation, so the two can never diverge.
 *
 * - `past_due` stays `active`: Stripe is still retrying a failed charge (dunning) —
 *   revoking access instantly would kill recovery.
 * - `unpaid` / `incomplete*` (retries exhausted or never started) → `expired`.
 * Stripe fires `subscription.deleted` when a sub finally cancels → `canceled`.
 */
export function mapStripeStatus(stripeStatus: string): LicenseStatus {
  switch (stripeStatus) {
    case "active":
    case "past_due":
      return "active";
    case "trialing":
      return "trialing";
    case "canceled":
      return "canceled";
    default:
      return "expired";
  }
}

export interface ReconcileResult {
  /** The true status after reconciliation (DB value if nothing to reconcile). */
  status: string;
  /** Whether the DB row was corrected (drift detected + fixed). */
  reconciled: boolean;
  /** License has a Stripe subscription (i.e. a paid/card-backed plan). */
  hasSubscription: boolean;
  /** License has a Stripe customer (a payment method may exist). */
  hasBillingAccount: boolean;
}

/**
 * Reconcile a license's stored `status` against the live Stripe subscription and
 * self-heal drift. Returns `null` if the license doesn't exist.
 *
 * - No `stripe_subscription_id` (e.g. the no-credit-card trial cohort) → no-op; a
 *   trial with no subscription can't drift, so we return the DB status unchanged.
 * - Live Stripe status differs from the DB → update `licenses.status` + log it.
 * - Stripe `resource_missing` (subscription deleted) → `canceled`.
 * - Any other (transient) Stripe error → leave the DB untouched, return current status.
 */
export async function reconcileSubscriptionStatus(
  licenseKey: string,
): Promise<ReconcileResult | null> {
  const supabase = getSupabase();
  const { data: license, error } = await supabase
    .from("licenses")
    .select("key, status, stripe_customer_id, stripe_subscription_id")
    .eq("key", licenseKey)
    .single();

  if (error || !license) return null;

  const hasBillingAccount = !!license.stripe_customer_id;
  const hasSubscription = !!license.stripe_subscription_id;

  if (!hasSubscription) {
    return {
      status: license.status,
      reconciled: false,
      hasSubscription: false,
      hasBillingAccount,
    };
  }

  // Never resurrect a locally-canceled license. A subscription set to
  // cancel_at_period_end still reports Stripe status `active` until the period
  // actually ends, so mapping status alone would flip a user's cancellation back
  // to active. We only heal drift in the direction of "should be canceled/expired"
  // (Chris's case: DB trialing, Stripe sub gone). The webhook owns forward status.
  if (license.status === "canceled") {
    return {
      status: "canceled",
      reconciled: false,
      hasSubscription: true,
      hasBillingAccount,
    };
  }

  let trueStatus: string;
  try {
    const sub = (await getStripe().subscriptions.retrieve(
      license.stripe_subscription_id as string,
    )) as Stripe.Subscription;
    trueStatus = mapStripeStatus(sub.status);
  } catch (e: unknown) {
    if ((e as { code?: string })?.code === "resource_missing") {
      trueStatus = "canceled"; // sub no longer exists in Stripe
    } else {
      // Transient Stripe/network error — don't mutate on uncertainty.
      return {
        status: license.status,
        reconciled: false,
        hasSubscription: true,
        hasBillingAccount,
      };
    }
  }

  if (trueStatus === license.status) {
    return {
      status: trueStatus,
      reconciled: false,
      hasSubscription: true,
      hasBillingAccount,
    };
  }

  await supabase
    .from("licenses")
    .update({ status: trueStatus, updated_at: new Date().toISOString() })
    .eq("key", licenseKey);

  await logEvent({
    eventType: "subscription_reconciled",
    licenseKey,
    action: "reconcile_status",
    payload: { from: license.status, to: trueStatus },
    success: true,
  });

  return {
    status: trueStatus,
    reconciled: true,
    hasSubscription: true,
    hasBillingAccount,
  };
}
