import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { getSupabase } from "@/lib/supabase";
import { getStripe } from "@/lib/stripe";
import { mapStripeStatus } from "@/lib/subscription";
import { logEvent } from "@/lib/event-logger";

/**
 * POST /api/user/subscription/reactivate  { licenseKey }
 *
 * The expired-trial dead end (user incident): when a trial lapses, Stripe
 * CANCELS the trial subscription. The dashboard then sent the user to the
 * billing portal, where adding a card does nothing — a canceled subscription
 * is never revived by Stripe, so the dashboard kept saying "expired / no
 * payment method" even after the card was saved.
 *
 * This endpoint completes the loop: for an expired/canceled license whose
 * Stripe customer has a saved default payment method, create a NEW
 * subscription on the SAME price the previous subscription used (preserves
 * tier and currency, e.g. CAD), link it to the license immediately (so every
 * later webhook matches by subscription id), and sync status/card/billing
 * fields. If the card issuer demands authentication (SCA), we return the
 * hosted invoice URL so the user can confirm — the already-linked webhook
 * finishes the job. If no card is on file, we say so and the client opens
 * the billing portal first. Clerk-authed via middleware (not a public route).
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
    const { data: license } = await supabase
      .from("licenses")
      .select("key, status, tier, stripe_customer_id, stripe_subscription_id")
      .eq("key", licenseKey)
      .maybeSingle();
    if (!license) {
      return NextResponse.json({ error: "License not found" }, { status: 404 });
    }
    if (license.status === "active" || license.status === "trialing") {
      return NextResponse.json({
        ok: true,
        state: "already_active",
        message: "Your subscription is already active — no charge was made.",
      });
    }
    if (!license.stripe_customer_id) {
      // Never had a Stripe customer (e.g. pure no-credit-card trial) → the
      // normal checkout flow is the right path.
      return NextResponse.json({ ok: false, state: "needs_checkout" });
    }

    const stripe = getStripe();
    const customerId = license.stripe_customer_id;

    // A saved card is required — reactivation charges immediately.
    const customer = (await stripe.customers.retrieve(
      customerId,
    )) as Stripe.Customer;
    let pmId =
      typeof customer.invoice_settings?.default_payment_method === "string"
        ? customer.invoice_settings.default_payment_method
        : customer.invoice_settings?.default_payment_method?.id;
    if (!pmId) {
      const pms = await stripe.paymentMethods.list({
        customer: customerId,
        type: "card",
        limit: 1,
      });
      pmId = pms.data[0]?.id;
    }
    if (!pmId) {
      return NextResponse.json({
        ok: false,
        state: "needs_payment_method",
        message:
          "No card on file yet — add a payment method first, then reactivate.",
      });
    }

    // Reuse the price of the most recent subscription: same tier, same
    // currency (a Canadian customer stays on CAD pricing) — never guessed.
    const prior = await stripe.subscriptions.list({
      customer: customerId,
      status: "all",
      limit: 3,
    });
    const priorSub = prior.data.sort((a, b) => b.created - a.created)[0];
    const priceId = priorSub?.items?.data?.[0]?.price?.id;
    if (!priceId) {
      return NextResponse.json({ ok: false, state: "needs_checkout" });
    }

    // Guard against double-charging: if a live subscription already exists
    // (e.g. double-click, or support created one manually), adopt it instead
    // of creating a second.
    const live = prior.data.find((s) =>
      ["active", "trialing", "past_due"].includes(s.status),
    );
    const sub =
      live ??
      (await stripe.subscriptions.create({
        customer: customerId,
        items: [{ price: priceId }],
        default_payment_method: pmId,
        payment_behavior: "allow_incomplete",
        expand: ["latest_invoice.payment_intent"],
      }));

    // Link FIRST — from here on, every webhook for this sub finds the license.
    const status = mapStripeStatus(sub.status);
    const updateData: Record<string, unknown> = {
      stripe_subscription_id: sub.id,
      status,
      updated_at: new Date().toISOString(),
    };
    if (sub.current_period_end) {
      updateData.next_billing_date = new Date(
        sub.current_period_end * 1000,
      ).toISOString();
    }
    if (sub.items?.data?.[0]?.price?.unit_amount) {
      updateData.billing_amount_cents = sub.items.data[0].price.unit_amount;
    }
    // Store the billing currency so MRR math never blends CAD into USD.
    if (sub.currency) {
      updateData.currency = sub.currency;
    }
    try {
      const pm = await stripe.paymentMethods.retrieve(pmId);
      if (pm.card) {
        updateData.card_last_four = pm.card.last4;
        updateData.card_brand = pm.card.brand;
      }
    } catch {
      // card display info is cosmetic — never block reactivation on it
    }
    await supabase.from("licenses").update(updateData).eq("key", licenseKey);

    await logEvent({
      eventType: "subscription_reconciled",
      action: "reactivated",
      licenseKey,
      payload: { subscriptionId: sub.id, stripeStatus: sub.status },
      success: status === "active",
    });

    if (status === "active") {
      return NextResponse.json({
        ok: true,
        state: "reactivated",
        message:
          "Welcome back — your subscription is active again and your saved card was charged for the new billing period.",
      });
    }

    // SCA / card action needed: hand back the hosted invoice to confirm.
    const invoice = sub.latest_invoice as Stripe.Invoice | null;
    const hostedUrl =
      invoice && typeof invoice === "object"
        ? invoice.hosted_invoice_url
        : null;
    if (hostedUrl) {
      return NextResponse.json({
        ok: true,
        state: "confirmation_required",
        url: hostedUrl,
        message:
          "Your bank asked for a quick confirmation — complete it and your subscription activates automatically.",
      });
    }
    return NextResponse.json(
      {
        error:
          "The charge could not be completed with the saved card. Please update your payment method and try again.",
      },
      { status: 402 },
    );
  } catch (err) {
    console.error("Reactivate subscription error:", err);
    return NextResponse.json(
      { error: "Failed to reactivate subscription" },
      { status: 500 },
    );
  }
}
