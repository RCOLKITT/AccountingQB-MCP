import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import { sendLicenseEmail } from "@/lib/resend";
import { scheduleOnboardingEmails } from "@/lib/emails/schedule-email";

const TIERS = ["solopreneur", "business", "firm"];

/**
 * POST /api/admin/invite
 * Issue a time-limited trial license to a friend/family tester and email it.
 *
 * This is a "comp trial": a normal trialing license with NO Stripe fields.
 * It rides the existing rails exactly — /api/license/verify expires it by
 * trial_ends_at (date-based, Stripe-independent), after which the tester
 * drops to the free read-only tools and must subscribe for full access.
 * Nothing about the Stripe checkout / webhook path is touched.
 *
 * Body: { email, tier?, trialDays? (default 14), dryRun? }
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  const adminEmail = user.emailAddresses[0]?.emailAddress || "admin";

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const email = String(body.email || "")
    .trim()
    .toLowerCase();
  const tier = String(body.tier || "solopreneur");
  const trialDays = Number(body.trialDays ?? 14);
  const dryRun = Boolean(body.dryRun);

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json(
      { error: "A valid email is required" },
      { status: 400 },
    );
  }
  if (!TIERS.includes(tier)) {
    return NextResponse.json({ error: "Invalid tier" }, { status: 400 });
  }
  if (!Number.isFinite(trialDays) || trialDays < 1 || trialDays > 60) {
    return NextResponse.json(
      { error: "trialDays must be between 1 and 60" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();

  // Don't double-issue: if this email already has a license that is still
  // usable (active, or a trial that hasn't ended), return it instead of
  // creating another. Expired/canceled licenses don't block a fresh invite.
  const { data: existing } = await supabase
    .from("licenses")
    .select("key, status, tier, trial_ends_at, stripe_subscription_id")
    .eq("email", email)
    .order("created_at", { ascending: false })
    .limit(5);

  const usable = (existing || []).find((l) => {
    if (l.status === "active") return true;
    if (l.status === "trialing") {
      return !l.trial_ends_at || new Date(l.trial_ends_at) > new Date();
    }
    return false;
  });
  if (usable) {
    return NextResponse.json({
      created: false,
      alreadyHasLicense: true,
      licenseKey: usable.key,
      status: usable.status,
      message:
        usable.status === "active"
          ? `${email} already has a paid license — no invite needed.`
          : `${email} already has an active trial (key ${usable.key}).`,
    });
  }

  const licenseKey = `LK-${crypto.randomBytes(16).toString("hex").toUpperCase()}`;
  const trialEndsAt = new Date(
    Date.now() + trialDays * 24 * 60 * 60 * 1000,
  ).toISOString();

  if (dryRun) {
    return NextResponse.json({
      dryRun: true,
      wouldCreate: { email, tier, trialDays, licenseKey, trialEndsAt },
    });
  }

  const { error: insertError } = await supabase.from("licenses").insert({
    key: licenseKey,
    email,
    tier,
    status: "trialing",
    trial_ends_at: trialEndsAt,
    // No stripe_customer_id / stripe_subscription_id — NULL marks this as a
    // comp invite. The partial unique index only applies to non-null subs.
  });

  if (insertError) {
    console.error("Failed to create invite license:", insertError);
    return NextResponse.json(
      { error: "Failed to create invite license" },
      { status: 500 },
    );
  }

  // Signup milestone (source=invite so analytics can tell comps from Stripe)
  await supabase.from("user_milestones").insert({
    license_key: licenseKey,
    milestone: "signup",
    metadata: { email, tier, source: "invite", invitedBy: adminEmail },
  });

  // Same nurture sequence paying trials get — includes the trial-ending
  // reminders that nudge the tester to subscribe.
  try {
    await scheduleOnboardingEmails(
      licenseKey,
      email,
      tier,
      new Date(trialEndsAt),
    );
  } catch (e) {
    console.error("Failed to schedule onboarding emails for invite:", e);
  }

  // Immediate license email with the key + setup instructions
  try {
    await sendLicenseEmail({ to: email, licenseKey, tier, trialEndsAt });
  } catch (e) {
    console.error("Failed to send invite license email:", e);
    return NextResponse.json({
      created: true,
      emailSent: false,
      licenseKey,
      trialEndsAt,
      message:
        "License created, but the email failed to send. Share the key manually.",
    });
  }

  console.log(
    `Invite trial ${licenseKey} (${tier}, ${trialDays}d) issued to ${email} by ${adminEmail}`,
  );

  return NextResponse.json({
    created: true,
    emailSent: true,
    licenseKey,
    email,
    tier,
    trialEndsAt,
  });
}
