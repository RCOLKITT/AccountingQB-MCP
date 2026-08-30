import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";

async function createPortalUrl(licenseKey: string): Promise<string | null> {
  const { data: license, error } = await getSupabase()
    .from("licenses")
    .select("stripe_customer_id")
    .eq("key", licenseKey)
    .single();

  if (error || !license?.stripe_customer_id) return null;

  const baseUrl =
    process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";
  const portalSession = await getStripe().billingPortal.sessions.create({
    customer: license.stripe_customer_id,
    return_url: `${baseUrl}/dashboard?key=${encodeURIComponent(licenseKey)}`,
  });
  return portalSession.url;
}

/**
 * POST /api/stripe/portal
 * Creates a Stripe Customer Portal session so users can manage their subscription.
 * Body: { licenseKey: string }
 */
export async function POST(req: NextRequest) {
  try {
    const { licenseKey } = await req.json();
    if (!licenseKey) {
      return NextResponse.json(
        { error: "License key is required" },
        { status: 400 },
      );
    }
    const url = await createPortalUrl(licenseKey);
    if (!url) {
      return NextResponse.json(
        { error: "License not found or no associated Stripe customer" },
        { status: 404 },
      );
    }
    return NextResponse.json({ url });
  } catch (err) {
    console.error("Portal session error:", err);
    return NextResponse.json(
      { error: "Failed to create portal session" },
      { status: 500 },
    );
  }
}

/**
 * GET /api/stripe/portal?key=LICENSE
 * Email-linkable entry point: opens the customer's billing portal (where they can
 * add a payment method to keep their plan past the trial). The license key is the
 * bearer credential, consistent with the dashboard's ?key= access model.
 */
export async function GET(req: NextRequest) {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || req.nextUrl.origin;
  const licenseKey = req.nextUrl.searchParams.get("key");
  if (!licenseKey) {
    return NextResponse.redirect(`${baseUrl}/pricing`, 303);
  }
  try {
    const url = await createPortalUrl(licenseKey);
    // No Stripe customer yet (e.g. admin-issued trial) → send them to pricing to subscribe.
    return NextResponse.redirect(url || `${baseUrl}/pricing`, 303);
  } catch (err) {
    console.error("Portal GET error:", err);
    return NextResponse.redirect(
      `${baseUrl}/dashboard?key=${encodeURIComponent(licenseKey)}`,
      303,
    );
  }
}
