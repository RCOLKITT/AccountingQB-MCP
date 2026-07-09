import Stripe from "stripe";
import crypto from "crypto";
import { getSupabase } from "@/lib/supabase";
import { sendLicenseEmail } from "@/lib/resend";
import { scheduleOnboardingEmails } from "@/lib/emails/schedule-email";

export interface EnsureLicenseResult {
  licenseKey: string;
  email: string;
  tier: string;
  /** true if a new license was created, false if one already existed */
  created: boolean;
}

/**
 * Ensure a license exists for a completed Stripe Checkout session.
 *
 * Idempotent — keyed on stripe_subscription_id: if a license already exists
 * for the session's subscription, it's returned without side effects.
 * Otherwise creates the license, records the signup milestone, schedules
 * the onboarding email sequence, and sends the license email.
 *
 * Used by the Stripe webhook (checkout.session.completed) and as a
 * reconciliation path by /api/stripe/session when the webhook was missed.
 */
export async function ensureLicenseForSession(
  stripe: Stripe,
  supabase: ReturnType<typeof getSupabase>,
  session: Stripe.Checkout.Session
): Promise<EnsureLicenseResult | null> {
  const subscriptionId =
    typeof session.subscription === "string"
      ? session.subscription
      : session.subscription?.id;

  if (!subscriptionId) {
    return null;
  }

  const tier = session.metadata?.tier || "solopreneur";
  const email = session.customer_email || session.customer_details?.email || "";

  // Check if license already exists (idempotent — safe for replayed webhook
  // events and concurrent reconciliation)
  const { data: existing } = await supabase
    .from("licenses")
    .select("key, email, tier")
    .eq("stripe_subscription_id", subscriptionId)
    .maybeSingle();

  if (existing) {
    return {
      licenseKey: existing.key,
      email: existing.email,
      tier: existing.tier,
      created: false,
    };
  }

  const licenseKey = `LK-${crypto.randomBytes(16).toString("hex").toUpperCase()}`;
  const trialEndsAt = new Date(
    Date.now() + 14 * 24 * 60 * 60 * 1000
  ).toISOString();

  const { error: insertError } = await supabase.from("licenses").insert({
    key: licenseKey,
    email,
    tier,
    stripe_customer_id: session.customer as string,
    stripe_subscription_id: subscriptionId,
    status: "trialing",
    trial_ends_at: trialEndsAt,
  });

  if (insertError) {
    // A concurrent request may have created the license first (unique on
    // stripe_subscription_id in practice) — re-check before failing
    const { data: raced } = await supabase
      .from("licenses")
      .select("key, email, tier")
      .eq("stripe_subscription_id", subscriptionId)
      .maybeSingle();

    if (raced) {
      return {
        licenseKey: raced.key,
        email: raced.email,
        tier: raced.tier,
        created: false,
      };
    }

    console.error("Failed to insert license:", insertError);
    return null;
  }

  // Track signup milestone
  await supabase.from("user_milestones").insert({
    license_key: licenseKey,
    milestone: "signup",
    metadata: { email, tier },
  });

  // Schedule onboarding email sequence
  try {
    await scheduleOnboardingEmails(licenseKey, email, tier, new Date(trialEndsAt));
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

  return { licenseKey, email, tier, created: true };
}
