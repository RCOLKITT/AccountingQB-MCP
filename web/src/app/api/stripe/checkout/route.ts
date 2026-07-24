import { NextRequest, NextResponse } from "next/server";
import { getStripe, getTierPrice } from "@/lib/stripe";
import {
  getCheckoutLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * GET /api/stripe/checkout?tier=solopreneur&email=user@example.com
 * Creates a Stripe Checkout session for subscription with 14-day trial.
 */
export async function GET(req: NextRequest) {
  // Rate limit: 5 requests per minute per IP
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getCheckoutLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  const tier = req.nextUrl.searchParams.get("tier") || "solopreneur";
  const email = req.nextUrl.searchParams.get("email") || undefined;

  // CAD for Canadian visitors (the prices carry currency_options.cad);
  // an explicit ?currency= always wins over IP-based detection.
  const currencyParam = req.nextUrl.searchParams.get("currency")?.toLowerCase();
  const isCanadianIP = req.headers.get("x-vercel-ip-country") === "CA";
  const currency =
    currencyParam === "cad" || (!currencyParam && isCanadianIP)
      ? "cad"
      : undefined;

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
      ...(currency ? { currency } : {}),
      subscription_data: {
        trial_period_days: 14,
        metadata: { tier },
      },
      line_items: [{ price: priceId, quantity: 1 }],
      // Clickwrap: a required "I agree to the Terms of Service" checkbox at the
      // point of payment. Makes the limitation-of-liability / no-advice terms
      // affirmatively agreed to. Requires the ToS URL set in Stripe Dashboard.
      consent_collection: { terms_of_service: "required" },
      custom_text: {
        terms_of_service_acceptance: {
          message:
            "I agree to the AccountingQB [Terms of Service](https://accountingqb.com/terms) and understand it is a software tool, not tax or accounting advice.",
        },
      },
      success_url: `${baseUrl}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${baseUrl}/#pricing`,
      metadata: { tier },
    });

    return NextResponse.redirect(session.url!, 303);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Stripe checkout error:", message);
    return NextResponse.json(
      { error: "Failed to create checkout session" },
      { status: 500 }
    );
  }
}
