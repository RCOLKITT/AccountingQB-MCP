import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import { sendLicenseEmail } from "@/lib/resend";
import crypto from "crypto";
import Stripe from "stripe";

/**
 * POST /api/stripe/webhook
 * Handles Stripe webhook events for subscription lifecycle.
 */
export async function POST(req: NextRequest) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature");

  if (!sig) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = getStripe().webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err) {
    console.error("Webhook signature verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const supabase = getSupabase();

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const tier = session.metadata?.tier || "solopreneur";
      const email = session.customer_email || session.customer_details?.email || "";
      const licenseKey = `LK-${crypto.randomBytes(16).toString("hex").toUpperCase()}`;
      const trialEndsAt = new Date(
        Date.now() + 14 * 24 * 60 * 60 * 1000
      ).toISOString();

      // Check if license already exists (idempotent — safe for replayed webhook events)
      const { data: existing } = await supabase
        .from("licenses")
        .select("key")
        .eq("stripe_subscription_id", session.subscription as string)
        .maybeSingle();

      if (!existing) {
        await supabase.from("licenses").insert({
          key: licenseKey,
          email,
          tier,
          stripe_customer_id: session.customer as string,
          stripe_subscription_id: session.subscription as string,
          status: "trialing",
          trial_ends_at: trialEndsAt,
        });

        // Send license email
        if (email) {
          try {
            await sendLicenseEmail({
              to: email,
              licenseKey,
              tier,
              trialEndsAt,
            });
            console.log(`License email sent to ${email}`);
          } catch (emailErr) {
            console.error("Failed to send license email:", emailErr);
          }
        }

        console.log(`New license created: ${licenseKey} for ${email} (${tier})`);
      }
      break;
    }

    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      const status = sub.status === "active" ? "active" :
                     sub.status === "trialing" ? "trialing" :
                     sub.status === "canceled" ? "canceled" : "expired";

      await supabase
        .from("licenses")
        .update({ status, updated_at: new Date().toISOString() })
        .eq("stripe_subscription_id", sub.id);
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      await supabase
        .from("licenses")
        .update({ status: "canceled", updated_at: new Date().toISOString() })
        .eq("stripe_subscription_id", sub.id);
      break;
    }

    case "invoice.payment_succeeded": {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription) {
        // Trial converted to paid — activate license
        await supabase
          .from("licenses")
          .update({
            status: "active",
            trial_ends_at: null,
            updated_at: new Date().toISOString(),
          })
          .eq("stripe_subscription_id", invoice.subscription as string);
      }
      break;
    }

    case "invoice.payment_failed": {
      const invoice = event.data.object as Stripe.Invoice;
      console.warn(
        `Payment failed for subscription ${invoice.subscription}`
      );
      // Stripe handles retry logic; we don't cancel immediately
      break;
    }

    default:
      // Unhandled event type
      break;
  }

  return NextResponse.json({ received: true }, { status: 200 });
}
