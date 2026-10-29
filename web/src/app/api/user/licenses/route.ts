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
 * Resolution:
 * 1. Resolve (or create) the user_profiles row by clerk_id.
 * 2. Look up user_licenses by user_id = profile.id.
 * 3. ALWAYS also match licenses by email (licenses are issued email-keyed with
 *    no user_licenses row) and persist the union — email matching is not a
 *    fallback; treating it as one stranded a user's new trial behind their old
 *    expired license.
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

  // ALWAYS also match licenses by email — not only when user_licenses is empty.
  // Licenses are issued keyed by email (trial start, download trial, Stripe
  // checkout) without a user_licenses row, so a user with an OLD linked license
  // who started a NEW trial never saw it: the dashboard showed only the expired
  // license and the OAuth consent page said "No active license found" (real
  // incident, 2026-10). Email matches are persisted so the union is durable.
  let emailLicenses: {
    key: string;
    tier: string;
    status: string;
    trial_ends_at: string | null;
    stripe_subscription_id: string | null;
  }[] = [];
  if (userEmail) {
    const { data } = await supabase
      .from("licenses")
      .select("key, tier, status, trial_ends_at, stripe_subscription_id")
      .ilike("email", userEmail);
    emailLicenses = data || [];
  }

  const linkedKeys = new Set(userLicenses.map((ul) => ul.license_key));
  const discovered = emailLicenses.filter((l) => !linkedKeys.has(l.key));
  if (userProfile && discovered.length > 0) {
    await supabase.from("user_licenses").upsert(
      discovered.map((l) => ({
        user_id: String(userProfile.id),
        license_key: l.key,
        role: "owner",
      })),
      { onConflict: "user_id,license_key" },
    );
  }

  if (userLicenses.length === 0 && emailLicenses.length === 0) {
    return NextResponse.json({ licenses: [] });
  }

  // Full info for linked licenses the email query didn't already cover
  // (e.g. a license shared with this user under a different email).
  const linkedOnlyKeys = [...linkedKeys].filter(
    (k) => !emailLicenses.some((l) => l.key === k),
  );
  let linkedOnly: typeof emailLicenses = [];
  if (linkedOnlyKeys.length > 0) {
    const { data } = await supabase
      .from("licenses")
      .select("key, tier, status, trial_ends_at, stripe_subscription_id")
      .in("key", linkedOnlyKeys);
    linkedOnly = data || [];
  }

  const reconciled = await withReconciledStatus([
    ...emailLicenses,
    ...linkedOnly,
  ]);
  // Usable licenses first (active/trialing before expired/canceled) so UIs
  // that preselect the first entry pick one the user can actually use.
  const usable = (s: string) => s !== "expired" && s !== "canceled";
  reconciled.sort(
    (a, b) => Number(usable(b.status)) - Number(usable(a.status)),
  );
  return NextResponse.json({
    licenses: reconciled.map((l) => {
      const link = userLicenses.find((ul) => ul.license_key === l.key);
      return {
        key: l.key,
        tier: l.tier,
        status: l.status,
        trial_ends_at: l.trial_ends_at,
        role: link?.role ?? "owner",
      };
    }),
  });
}
