import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getStripe } from "@/lib/stripe";
import { currentUser } from "@clerk/nextjs/server";
import { rescheduleTrialEmails } from "@/lib/emails/schedule-email";

/**
 * POST /api/admin/users/[key]/extend-trial
 * Extend a user's trial period.
 *
 * When the license has a Stripe subscription, Stripe's `trial_end` is moved
 * FIRST — Stripe is what actually starts billing, and the reconcile job syncs
 * our status FROM Stripe, so extending only `licenses.trial_ends_at` would
 * promise the user one date while Stripe bills (or kills the sub) on the old
 * one and then overwrites our extension. If Stripe refuses, nothing is
 * changed and the error is returned.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const adminEmail = user.emailAddresses[0]?.emailAddress || "admin";

  const { key } = await params;
  const { days, reason } = await req.json();

  if (!days || days < 1 || days > 365) {
    return NextResponse.json(
      { error: "Invalid extension period" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();

  // Get current license
  const { data: license, error } = await supabase
    .from("licenses")
    .select("key, email, tier, status, trial_ends_at, stripe_subscription_id")
    .eq("key", key)
    .single();

  if (error || !license) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  // Only trials can be extended. Never silently flip a paying ('active') or a
  // canceled paid subscription into 'trialing'.
  if (license.status !== "trialing" && license.status !== "expired") {
    return NextResponse.json(
      { error: `Cannot extend a trial for a '${license.status}' license.` },
      { status: 400 },
    );
  }

  // Anchor off whichever is later — a long-expired trial must still land in the
  // future, not "+N days" from an old, already-past date.
  const anchor = new Date();
  const currentTrialEnd =
    license.trial_ends_at && new Date(license.trial_ends_at) > anchor
      ? new Date(license.trial_ends_at)
      : anchor;
  const newTrialEnd = new Date(
    currentTrialEnd.getTime() + days * 24 * 60 * 60 * 1000,
  );

  // Move Stripe's trial_end FIRST — it is what actually starts billing, and
  // the reconcile job syncs our status FROM Stripe. If this fails, abort with
  // nothing changed rather than promise a date Stripe won't honor.
  if (license.stripe_subscription_id) {
    try {
      await getStripe().subscriptions.update(license.stripe_subscription_id, {
        trial_end: Math.floor(newTrialEnd.getTime() / 1000),
        proration_behavior: "none",
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("Stripe trial_end update failed:", msg);
      return NextResponse.json(
        {
          error: `Stripe refused the trial extension (nothing was changed): ${msg}`,
        },
        { status: 502 },
      );
    }
  }

  // Update license
  const { error: updateError } = await supabase
    .from("licenses")
    .update({
      trial_ends_at: newTrialEnd.toISOString(),
      status: "trialing", // Reset to trialing if expired
      updated_at: new Date().toISOString(),
    })
    .eq("key", key);

  if (updateError) {
    console.error("Failed to extend trial:", updateError);
    return NextResponse.json(
      { error: "Failed to extend trial" },
      { status: 500 },
    );
  }

  // Record the extension
  await supabase.from("trial_extensions").insert({
    license_key: key,
    extended_by: adminEmail,
    extension_days: days,
    old_trial_end: currentTrialEnd.toISOString(),
    new_trial_end: newTrialEnd.toISOString(),
    reason: reason || null,
  });

  // Reschedule trial warning emails
  await rescheduleTrialEmails(key, license.email, license.tier, newTrialEnd);

  console.log(`Trial extended for ${key}: +${days} days by ${adminEmail}`);

  return NextResponse.json({
    success: true,
    newTrialEnd: newTrialEnd.toISOString(),
  });
}
