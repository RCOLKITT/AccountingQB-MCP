import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { reconcileSubscriptionStatus } from "@/lib/subscription";

/**
 * GET /api/user/profile
 * Get user profile information by license key.
 */
export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const licenseKey = searchParams.get("key");

  if (!licenseKey) {
    return NextResponse.json(
      { error: "License key required" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();

  // Heal any drift against Stripe first, so the settings/billing view always shows
  // the true status (and reflects a cancel done in the Stripe portal). Returns the
  // billing shape (has-subscription / has-billing-account) for the UI to render.
  const recon = await reconcileSubscriptionStatus(licenseKey);

  // Get license info (fresh — reconcile may have just corrected the status)
  const { data: license, error } = await supabase
    .from("licenses")
    .select(
      "key, email, tier, status, trial_ends_at, card_last_four, card_brand, next_billing_date, billing_amount_cents, read_only",
    )
    .eq("key", licenseKey)
    .single();

  if (error || !license) {
    return NextResponse.json({ error: "License not found" }, { status: 404 });
  }

  // Get QB connections
  const { data: qbConnections } = await supabase
    .from("oauth_tokens")
    .select("realm_id, company_name")
    .eq("license_key", licenseKey);

  // A single state the UI can switch on to always show an accurate, non-confusing
  // billing panel (and never a cancel button that would error).
  const hasSubscription = recon?.hasSubscription ?? false;
  const billingState =
    license.status === "canceled"
      ? "canceled"
      : license.status === "expired"
        ? "expired"
        : license.status === "active"
          ? "active"
          : license.status === "trialing"
            ? hasSubscription
              ? "trialing_paid" // card-backed trial → will convert unless canceled
              : "trialing_free" // no card on file → nothing to cancel, no charge
            : license.status;

  return NextResponse.json({
    profile: {
      email: license.email,
      tier: license.tier,
      status: license.status,
      readOnly: !!license.read_only,
      billingState,
      hasSubscription,
      hasBillingAccount: recon?.hasBillingAccount ?? false,
      licenseKey: license.key,
      trialEndsAt: license.trial_ends_at,
      cardLastFour: license.card_last_four,
      cardBrand: license.card_brand,
      nextBillingDate: license.next_billing_date,
      billingAmountCents: license.billing_amount_cents,
      qbConnections: (qbConnections || []).map((c) => ({
        realmId: c.realm_id,
        companyName: c.company_name,
      })),
    },
  });
}
