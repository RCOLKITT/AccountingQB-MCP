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
  session: Stripe.Checkout.Session,
): Promise<EnsureLicenseResult | null> {
  const subscriptionId =
    typeof session.subscription === "string"
      ? session.subscription
      : session.subscription?.id;

  if (!subscriptionId) {
    return null;
  }

  const tier = session.metadata?.tier || "solopreneur";
  // Stripe always collects an email for subscription-mode Checkout, so this is
  // effectively always present; trim + the empty-case log below make a missing
  // one visible instead of a silent "customer paid but got no key" failure.
  const email = (
    session.customer_email ||
    session.customer_details?.email ||
    ""
  ).trim();

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
    Date.now() + 14 * 24 * 60 * 60 * 1000,
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
    await scheduleOnboardingEmails(
      licenseKey,
      email,
      tier,
      new Date(trialEndsAt),
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
  } else {
    // Should be unreachable for subscription checkout — surface it loudly so a
    // paying customer without a key email is caught, not silently lost.
    console.error(
      `⚠️ License ${licenseKey} issued with NO email (session ${session.id}) — ` +
        `key email not sent; customer must retrieve it from the success page or dashboard.`,
    );
  }

  console.log(`New license created: ${licenseKey} for ${email} (${tier})`);

  return { licenseKey, email, tier, created: true };
}

export interface TrialLicenseResult {
  licenseKey: string;
  email: string;
  tier: string;
  /** true if a new trial was created, false if an existing live license was reused */
  created: boolean;
}

/**
 * Ensure a NO-CREDIT-CARD trial license exists for an email — the self-serve /
 * download trial path. Mirrors ensureLicenseForSession but keyed on EMAIL with
 * no Stripe objects (null stripe ids are allowed by the schema; the partial
 * unique index only applies to non-null subscriptions).
 *
 * Idempotent by email: if the address already has a live (active/trialing)
 * license it is reused rather than issuing a duplicate — so a user who
 * downloads twice, or downloads then checks out, never ends up with two
 * trials. Nurture + the key email are best-effort (a send failure never rolls
 * back the license). Returns null only if the license row itself could not be
 * created, so callers can still capture the lead and let the download proceed.
 */
export async function ensureTrialLicenseForEmail(
  supabase: ReturnType<typeof getSupabase>,
  rawEmail: string,
  tier: string = "solopreneur",
  source: string = "download",
): Promise<TrialLicenseResult | null> {
  const email = rawEmail.trim().toLowerCase();
  if (!email) return null;

  // Idempotent: reuse a live license for this email (case-insensitive).
  const { data: existing } = await supabase
    .from("licenses")
    .select("key, email, tier")
    .ilike("email", email)
    .in("status", ["active", "trialing"])
    .order("created_at", { ascending: false })
    .limit(1)
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
    Date.now() + 14 * 24 * 60 * 60 * 1000,
  ).toISOString();

  const { error: insertError } = await supabase.from("licenses").insert({
    key: licenseKey,
    email,
    tier,
    status: "trialing",
    trial_ends_at: trialEndsAt,
    // No stripe_customer_id / stripe_subscription_id — a card-free trial. If the
    // user later converts, checkout attaches a subscription then.
  });

  if (insertError) {
    // A concurrent request for the same email may have won the race — re-check.
    const { data: raced } = await supabase
      .from("licenses")
      .select("key, email, tier")
      .ilike("email", email)
      .in("status", ["active", "trialing"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (raced) {
      return {
        licenseKey: raced.key,
        email: raced.email,
        tier: raced.tier,
        created: false,
      };
    }
    console.error("Failed to insert trial license:", insertError);
    return null;
  }

  // Signup milestone (source distinguishes download-trials from Stripe-trials).
  await supabase.from("user_milestones").insert({
    license_key: licenseKey,
    milestone: "signup",
    metadata: { email, tier, source },
  });

  // Nurture sequence + key email — best-effort; never roll back the license.
  try {
    await scheduleOnboardingEmails(
      licenseKey,
      email,
      tier,
      new Date(trialEndsAt),
    );
  } catch (emailErr) {
    console.error("Failed to schedule onboarding emails:", emailErr);
  }
  try {
    await sendLicenseEmail({ to: email, licenseKey, tier, trialEndsAt });
  } catch (emailErr) {
    console.error("Failed to send trial license email:", emailErr);
  }

  console.log(
    `New no-CC trial license: ${licenseKey} for ${email} (${tier}, source=${source})`,
  );
  return { licenseKey, email, tier, created: true };
}
