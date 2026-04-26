import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import { sendLicenseEmail } from "@/lib/resend";
import { createStripeEventLogger, logEvent } from "@/lib/event-logger";
import { scheduleOnboardingEmails } from "@/lib/emails/schedule-email";
import { scheduleEmail } from "@/lib/emails/schedule-email";
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

  // Create event logger for this webhook
  const subscriptionId = (event.data.object as { subscription?: string; id?: string }).subscription
    || (event.data.object as { id?: string }).id;
  const eventLogger = createStripeEventLogger(event.id, event.type, subscriptionId);

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

        // Track signup milestone
        await supabase.from("user_milestones").insert({
          license_key: licenseKey,
          milestone: "signup",
          metadata: { email, tier },
        });

        // Schedule onboarding email sequence
        try {
          await scheduleOnboardingEmails(
            licenseKey,
            email,
            tier,
            new Date(trialEndsAt)
          );
          console.log(`Onboarding emails scheduled for ${email}`);
        } catch (emailErr) {
          console.error("Failed to schedule onboarding emails:", emailErr);
        }

        // Send license email (immediate)
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

        // Log successful license creation
        await eventLogger.success(licenseKey, { email, tier });
      } else {
        // Log duplicate event (idempotent)
        await eventLogger.success(existing.key, { note: "Duplicate event - already processed" });
      }
      break;
    }

    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      const status = sub.status === "active" ? "active" :
                     sub.status === "trialing" ? "trialing" :
                     sub.status === "canceled" ? "canceled" : "expired";

      const { data: license } = await supabase
        .from("licenses")
        .select("key")
        .eq("stripe_subscription_id", sub.id)
        .maybeSingle();

      // Build update object with billing info if available
      const updateData: Record<string, unknown> = {
        status,
        updated_at: new Date().toISOString(),
      };

      // Capture next billing date
      if (sub.current_period_end) {
        updateData.next_billing_date = new Date(sub.current_period_end * 1000).toISOString();
      }

      // Capture billing amount
      if (sub.items?.data?.[0]?.price?.unit_amount) {
        updateData.billing_amount_cents = sub.items.data[0].price.unit_amount;
      }

      // Get card info from default payment method
      if (sub.default_payment_method && typeof sub.default_payment_method === "string") {
        try {
          const pm = await getStripe().paymentMethods.retrieve(sub.default_payment_method);
          if (pm.card) {
            updateData.card_last_four = pm.card.last4;
            updateData.card_brand = pm.card.brand;
          }
        } catch {
          // Payment method retrieval failed, continue without card info
        }
      }

      await supabase
        .from("licenses")
        .update(updateData)
        .eq("stripe_subscription_id", sub.id);

      await eventLogger.success(license?.key, { newStatus: status });
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;

      const { data: license } = await supabase
        .from("licenses")
        .select("key")
        .eq("stripe_subscription_id", sub.id)
        .maybeSingle();

      await supabase
        .from("licenses")
        .update({ status: "canceled", updated_at: new Date().toISOString() })
        .eq("stripe_subscription_id", sub.id);

      await eventLogger.success(license?.key, { newStatus: "canceled" });
      break;
    }

    case "invoice.payment_succeeded": {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription) {
        // Get the license for this subscription
        const { data: license } = await supabase
          .from("licenses")
          .select("key, email, tier, status")
          .eq("stripe_subscription_id", invoice.subscription as string)
          .maybeSingle();

        const wasTrialing = license?.status === "trialing";

        // Trial converted to paid — activate license
        await supabase
          .from("licenses")
          .update({
            status: "active",
            trial_ends_at: null,
            updated_at: new Date().toISOString(),
          })
          .eq("stripe_subscription_id", invoice.subscription as string);

        // Track trial conversion milestone
        if (wasTrialing && license?.key) {
          await supabase.from("user_milestones").upsert(
            {
              license_key: license.key,
              milestone: "trial_converted",
              metadata: { amountCents: invoice.amount_paid },
            },
            { onConflict: "license_key,milestone", ignoreDuplicates: true }
          );

          // Cancel any pending trial warning emails
          await supabase
            .from("email_schedules")
            .update({ cancelled: true })
            .eq("license_key", license.key)
            .in("email_type", ["trial_warning_4day", "trial_warning_1day", "trial_expired"])
            .is("sent_at", null);
        }

        // Schedule subscription renewed (receipt) email
        if (license?.key && license?.email) {
          const nextBillingDate = invoice.lines?.data?.[0]?.period?.end
            ? new Date(invoice.lines.data[0].period.end * 1000).toISOString()
            : "";

          await scheduleEmail({
            licenseKey: license.key,
            emailType: "subscription_renewed",
            scheduledFor: new Date(),
            metadata: {
              email: license.email,
              tier: license.tier,
              amountCents: invoice.amount_paid,
              nextBillingDate,
              invoiceUrl: invoice.hosted_invoice_url,
            },
          });
        }

        await eventLogger.success(license?.key, { note: wasTrialing ? "Trial converted to paid" : "Subscription renewed" });
      }
      break;
    }

    case "invoice.payment_failed": {
      const invoice = event.data.object as Stripe.Invoice;
      console.warn(
        `Payment failed for subscription ${invoice.subscription}`
      );

      // Get the license for this subscription
      const { data: license } = await supabase
        .from("licenses")
        .select("key, email, tier")
        .eq("stripe_subscription_id", invoice.subscription as string)
        .maybeSingle();

      // Schedule payment failed email
      if (license?.key && license?.email) {
        await scheduleEmail({
          licenseKey: license.key,
          emailType: "payment_failed",
          scheduledFor: new Date(),
          metadata: {
            email: license.email,
            tier: license.tier,
            attemptCount: invoice.attempt_count || 1,
          },
        });
      }

      // Stripe handles retry logic; we don't cancel immediately
      await eventLogger.failure("Payment failed");
      break;
    }

    default:
      // Log unhandled event types for monitoring
      await logEvent({
        eventType: "stripe_webhook",
        eventId: event.id,
        action: event.type,
        payload: { note: "Unhandled event type" },
        success: true,
      });
      break;
  }

  return NextResponse.json({ received: true }, { status: 200 });
}
