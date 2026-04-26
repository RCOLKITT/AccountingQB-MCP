import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getStripe } from "@/lib/stripe";

/**
 * POST /api/user/subscription/cancel
 * Cancel user's subscription via Stripe.
 */
export async function POST(req: NextRequest) {
  try {
    const { licenseKey } = await req.json();

    if (!licenseKey) {
      return NextResponse.json(
        { error: "License key required" },
        { status: 400 }
      );
    }

    const supabase = getSupabase();

    // Get license with Stripe subscription ID
    const { data: license, error } = await supabase
      .from("licenses")
      .select("key, stripe_subscription_id, status")
      .eq("key", licenseKey)
      .single();

    if (error || !license) {
      return NextResponse.json({ error: "License not found" }, { status: 404 });
    }

    if (license.status === "canceled") {
      return NextResponse.json(
        { error: "Subscription already canceled" },
        { status: 400 }
      );
    }

    if (!license.stripe_subscription_id) {
      return NextResponse.json(
        { error: "No active subscription found" },
        { status: 400 }
      );
    }

    const stripe = getStripe();

    // Cancel at period end (user keeps access until billing period ends)
    await stripe.subscriptions.update(license.stripe_subscription_id, {
      cancel_at_period_end: true,
    });

    // Update status in database
    await supabase
      .from("licenses")
      .update({
        status: "canceled",
        updated_at: new Date().toISOString(),
      })
      .eq("key", licenseKey);

    // Cancel any pending trial warning emails
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

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Cancel subscription error:", err);
    return NextResponse.json(
      { error: "Failed to cancel subscription" },
      { status: 500 }
    );
  }
}
