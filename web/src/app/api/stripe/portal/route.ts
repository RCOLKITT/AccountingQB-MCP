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
      // No Stripe customer (e.g. a no-credit-card trial) → not an error: there's
      // simply no billing account to manage, and nothing that can be charged.
      return NextResponse.json({
        state: "no_billing_account",
        message:
          "You're on a trial with no payment method on file — there's no billing account to manage, and no charge will be made.",
      });
    }
    return NextResponse.json({ url, state: "ok" });
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
    // No Stripe customer (e.g. a no-credit-card trial) → back to the dashboard with
    // a flag so it can show the "no billing account, nothing to manage" state,
    // rather than dumping the user on the pricing page.
    return NextResponse.redirect(
      url ||
        `${baseUrl}/dashboard?key=${encodeURIComponent(licenseKey)}&billing=none`,
      303,
    );
  } catch (err) {
    console.error("Portal GET error:", err);
    return NextResponse.redirect(
      `${baseUrl}/dashboard?key=${encodeURIComponent(licenseKey)}`,
      303,
    );
  }
}
