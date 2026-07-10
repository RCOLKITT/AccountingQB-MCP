import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import { ensureLicenseForSession } from "@/lib/license-issuance";

/**
 * GET /api/stripe/session?id=cs_test_...
 * Looks up a completed Stripe Checkout session and returns the associated license key.
 * Called by the success page to display the key after checkout.
 */
export async function GET(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("id");

  if (!sessionId) {
    return NextResponse.json(
      { error: "Session ID is required" },
      { status: 400 }
    );
  }

  try {
    // Retrieve the Checkout session from Stripe
    const session = await getStripe().checkout.sessions.retrieve(sessionId, {
      expand: ["subscription"],
    });

    if (!session.subscription) {
      return NextResponse.json(
        { error: "No subscription found for this session" },
        { status: 404 }
      );
    }

    const subscriptionId =
      typeof session.subscription === "string"
        ? session.subscription
        : session.subscription.id;

    const supabase = getSupabase();

    // Look up the license in Supabase by subscription ID
    let { data: license } = await supabase
      .from("licenses")
      .select("key, email, tier")
      .eq("stripe_subscription_id", subscriptionId)
      .maybeSingle();

    // Reconciliation: if the webhook was missed but the session is actually
    // complete/paid, issue the license here (idempotent) and re-query.
    if (
      !license &&
      (session.status === "complete" || session.payment_status === "paid")
    ) {
      await ensureLicenseForSession(getStripe(), supabase, session);

      const { data: reconciled } = await supabase
        .from("licenses")
        .select("key, email, tier")
        .eq("stripe_subscription_id", subscriptionId)
        .maybeSingle();

      license = reconciled;
    }

    if (!license) {
      // License may not be created yet (webhook still processing)
      return NextResponse.json(
        { licenseKey: null, email: session.customer_email, tier: session.metadata?.tier },
        { status: 200 }
      );
    }

    return NextResponse.json({
      licenseKey: license.key,
      email: license.email,
      tier: license.tier,
    });
  } catch (err) {
    console.error("Session lookup error:", err);
    return NextResponse.json(
      { error: "Failed to look up session" },
      { status: 500 }
    );
  }
}
