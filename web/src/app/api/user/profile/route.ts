import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

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
      { status: 400 }
    );
  }

  const supabase = getSupabase();

  // Get license info
  const { data: license, error } = await supabase
    .from("licenses")
    .select(
      "key, email, tier, status, trial_ends_at, card_last_four, card_brand, next_billing_date, billing_amount_cents"
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

  return NextResponse.json({
    profile: {
      email: license.email,
      tier: license.tier,
      status: license.status,
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
