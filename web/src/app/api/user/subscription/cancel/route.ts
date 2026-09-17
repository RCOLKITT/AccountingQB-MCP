import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getStripe } from "@/lib/stripe";
import { reconcileSubscriptionStatus } from "@/lib/subscription";

const NO_SUB = {
  ok: true,
  state: "no_active_subscription" as const,
  message:
    "You're on a trial with no active paid subscription — there's nothing to cancel, and no charge will be made.",
};

/**
 * POST /api/user/subscription/cancel
 *
 * Always resolves to a clear, non-error outcome so a user can *always* reach a
 * "you won't be charged" state:
 *  - no paid subscription (e.g. no-credit-card trial) or already canceled → 200
 *    `no_active_subscription` (nothing to cancel),
 *  - active subscription → cancel at period end → 200 `canceled_at_period_end`.
 * Reconciles against Stripe first, so a locally-stale status can't cause a false
 * error or a failed cancel.
 */
export async function POST(req: NextRequest) {
  try {
    const { licenseKey } = await req.json();
    if (!licenseKey) {
      return NextResponse.json(
        { error: "License key required" },
        { status: 400 },
      );
    }

    const supabase = getSupabase();

    // Act on the true state (heals drift like DB=trialing while Stripe=canceled).
    const recon = await reconcileSubscriptionStatus(licenseKey);
    if (!recon) {
      return NextResponse.json({ error: "License not found" }, { status: 404 });
    }

    // Nothing billable to cancel → reassure, don't error.
    if (!recon.hasSubscription || recon.status === "canceled") {
      return NextResponse.json(NO_SUB);
    }

    const { data: license } = await supabase
      .from("licenses")
      .select("stripe_subscription_id")
      .eq("key", licenseKey)
      .single();
    const subId = license?.stripe_subscription_id;
    if (!subId) return NextResponse.json(NO_SUB);

    try {
      // Cancel at period end — the user keeps access until the period ends.
      await getStripe().subscriptions.update(subId, {
        cancel_at_period_end: true,
      });
    } catch (e: unknown) {
      // Sub already gone in Stripe → sync our record + treat as success.
      if ((e as { code?: string })?.code === "resource_missing") {
        await supabase
          .from("licenses")
          .update({ status: "canceled", updated_at: new Date().toISOString() })
          .eq("key", licenseKey);
        return NextResponse.json(NO_SUB);
      }
      console.error("Cancel subscription error:", e);
      return NextResponse.json(
        { error: "Failed to cancel subscription" },
        { status: 500 },
      );
    }

    await supabase
      .from("licenses")
      .update({ status: "canceled", updated_at: new Date().toISOString() })
      .eq("key", licenseKey);

    // Cancel any pending trial-warning / expiry emails.
    await supabase
      .from("email_schedules")
      .update({ cancelled: true })
      .eq("license_key", licenseKey)
      .in("email_type", [
        "trial_warning_4day",
        "trial_warning_1day",
        "trial_expired",
      ])
      .is("sent_at", null);

    console.log(`Subscription canceled for ${licenseKey}`);
    return NextResponse.json({
      ok: true,
      state: "canceled_at_period_end",
      message:
        "Your subscription is set to cancel at the end of the current billing period — you'll keep access until then and won't be charged again.",
    });
  } catch (err) {
    console.error("Cancel subscription error:", err);
    return NextResponse.json(
      { error: "Failed to cancel subscription" },
      { status: 500 },
    );
  }
}
