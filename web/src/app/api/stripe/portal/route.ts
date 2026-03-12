import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";

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
        { status: 400 }
      );
    }

    // Look up the license to get the Stripe customer ID
    const { data: license, error } = await getSupabase()
      .from("licenses")
      .select("stripe_customer_id")
      .eq("key", licenseKey)
      .single();

    if (error || !license?.stripe_customer_id) {
      return NextResponse.json(
        { error: "License not found or no associated Stripe customer" },
        { status: 404 }
      );
    }

    // Create portal session
    const portalSession = await getStripe().billingPortal.sessions.create({
      customer: license.stripe_customer_id,
      return_url: process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com",
    });

    return NextResponse.json({ url: portalSession.url });
  } catch (err) {
    console.error("Portal session error:", err);
    return NextResponse.json(
      { error: "Failed to create portal session" },
      { status: 500 }
    );
  }
}
