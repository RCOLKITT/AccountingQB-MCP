import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import { reconcileSubscriptionStatus } from "@/lib/subscription";

/** Reconcile only licenses that actually have a Stripe subscription (bounded — keeps
 *  no-credit-card trials fast) so the dashboard shows an accurate status for payers. */
async function withReconciledStatus<
  T extends {
    key: string;
    status: string;
    stripe_subscription_id?: string | null;
  },
>(licenses: T[]): Promise<T[]> {
  return Promise.all(
    licenses.map(async (l) => {
      if (!l.stripe_subscription_id) return l;
      const r = await reconcileSubscriptionStatus(l.key);
      return r ? { ...l, status: r.status } : l;
    }),
  );
}

/**
 * GET /api/user/licenses
 * Get licenses linked to the authenticated Clerk user.
 *
 * Resolution order:
 * 1. Resolve (or create) the user_profiles row by clerk_id.
 * 2. Look up user_licenses by user_id = profile.id.
 * 3. Fall back to matching licenses by email — and persist any matches
 *    into user_licenses so they're durable for future requests.
 */
export async function GET() {
  const { userId } = await auth();

  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabase();

  // Get user's email directly from Clerk
  const clerkUser = await currentUser();
  const clerkEmail = clerkUser?.emailAddresses[0]?.emailAddress?.toLowerCase();

  // Resolve the user profile by clerk_id
  let { data: userProfile } = await supabase
    .from("user_profiles")
    .select("id, email")
    .eq("clerk_id", userId)
    .maybeSingle();

  // Auto-create user_profiles entry if it doesn't exist (for existing users)
  if (!userProfile && clerkEmail) {
    const { data: created } = await supabase
      .from("user_profiles")
      .upsert(
        {
          clerk_id: userId,
          email: clerkEmail,
        },
        { onConflict: "clerk_id" },
      )
      .select("id, email")
      .single();

    userProfile = created;
  }

  const userEmail = clerkEmail || userProfile?.email;

  if (!userProfile && !userEmail) {
    // No profile and no email found anywhere
    return NextResponse.json({ licenses: [] });
  }

  // Get licenses linked to this user via user_licenses table
  // (user_licenses.user_id stores user_profiles.id as text)
  let userLicenses: { license_key: string; role: string }[] = [];
  if (userProfile) {
    const { data } = await supabase
      .from("user_licenses")
      .select("license_key, role")
      .eq("user_id", String(userProfile.id));
    userLicenses = data || [];
  }

  if (userLicenses.length === 0) {
    if (!userEmail) {
      return NextResponse.json({ licenses: [] });
    }

    // Try getting licenses by email directly from licenses table
    // This handles existing users who purchased before the dashboard existed
    // Use ilike for case-insensitive matching
    const { data: licenses } = await supabase
      .from("licenses")
      .select("key, tier, status, trial_ends_at, stripe_subscription_id")
      .ilike("email", userEmail);

    // Persist fallback matches into user_licenses so they're durable
    if (userProfile && licenses && licenses.length > 0) {
      await supabase.from("user_licenses").upsert(
        licenses.map((l) => ({
          user_id: String(userProfile.id),
          license_key: l.key,
          role: "owner",
        })),
        { onConflict: "user_id,license_key" },
      );
    }

    const reconciled = await withReconciledStatus(licenses || []);
    return NextResponse.json({
      licenses: reconciled.map((l) => ({
        key: l.key,
        tier: l.tier,
        status: l.status,
        trial_ends_at: l.trial_ends_at,
      })),
    });
  }

  // Get full license info
  const licenseKeys = userLicenses.map((ul) => ul.license_key);
  const { data: licenses } = await supabase
    .from("licenses")
    .select("key, tier, status, trial_ends_at, stripe_subscription_id")
    .in("key", licenseKeys);

  const reconciled = await withReconciledStatus(licenses || []);
  return NextResponse.json({
    licenses: reconciled.map((l) => {
      const link = userLicenses.find((ul) => ul.license_key === l.key);
      return {
        key: l.key,
        tier: l.tier,
        status: l.status,
        trial_ends_at: l.trial_ends_at,
        role: link?.role,
      };
    }),
  });
}
