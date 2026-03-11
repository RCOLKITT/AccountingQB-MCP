import { NextRequest, NextResponse } from "next/server";
import { getStripe, getTierPrice } from "@/lib/stripe";

/**
 * GET /api/stripe/checkout?tier=solopreneur&email=user@example.com
 * Creates a Stripe Checkout session for subscription with 14-day trial.
 */
export async function GET(req: NextRequest) {
  const tier = req.nextUrl.searchParams.get("tier") || "solopreneur";
  const email = req.nextUrl.searchParams.get("email") || undefined;

  let priceId: string;
  try {
    priceId = getTierPrice(tier);
  } catch {
    return NextResponse.json({ error: "Invalid tier" }, { status: 400 });
  }

  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || req.nextUrl.origin;

  try {
    const session = await getStripe().checkout.sessions.create({
      mode: "subscription",
      payment_method_types: ["card"],
      customer_email: email,
      subscription_data: {
        trial_period_days: 14,
        metadata: { tier },
      },
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: `${baseUrl}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${baseUrl}/#pricing`,
      metadata: { tier },
    });

    return NextResponse.redirect(session.url!, 303);
  } catch (err) {
    console.error("Stripe checkout error:", err);
    return NextResponse.json(
      { error: "Failed to create checkout session" },
      { status: 500 }
    );
  }
}
