import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/user/licenses
 * Get licenses linked to the authenticated Clerk user.
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

  // Also check user_profiles for legacy linked accounts
  const { data: userProfile } = await supabase
    .from("user_profiles")
    .select("email")
    .eq("clerk_id", userId)
    .single();

  // Use Clerk email or fall back to user_profiles email
  const userEmail = clerkEmail || userProfile?.email;

  if (!userEmail) {
    // No email found anywhere
    return NextResponse.json({ licenses: [] });
  }

  // Auto-create user_profiles entry if it doesn't exist (for existing users)
  if (!userProfile && clerkEmail) {
    await supabase.from("user_profiles").upsert({
      clerk_id: userId,
      email: clerkEmail,
      created_at: new Date().toISOString(),
    }, { onConflict: "clerk_id" });
  }

  // Get licenses linked to this user via user_licenses table
  const { data: userLicenses } = await supabase
    .from("user_licenses")
    .select("license_key, role")
    .eq("user_id", userEmail);

  if (!userLicenses || userLicenses.length === 0) {
    // Try getting licenses by email directly from licenses table
    // This handles existing users who purchased before the dashboard existed
    // Use ilike for case-insensitive matching
    const { data: licenses } = await supabase
      .from("licenses")
      .select("key, tier, status, trial_ends_at")
      .ilike("email", userEmail);

    return NextResponse.json({
      licenses: (licenses || []).map((l) => ({
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
    .select("key, tier, status, trial_ends_at")
    .in("key", licenseKeys);

  return NextResponse.json({
    licenses: (licenses || []).map((l) => {
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
