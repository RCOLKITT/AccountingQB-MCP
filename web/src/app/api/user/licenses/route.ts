import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
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

  // Get user's email from Clerk (stored when they linked their license)
  const { data: userProfile } = await supabase
    .from("user_profiles")
    .select("email")
    .eq("clerk_id", userId)
    .single();

  if (!userProfile) {
    // User hasn't linked any licenses yet
    return NextResponse.json({ licenses: [] });
  }

  // Get licenses linked to this user
  const { data: userLicenses } = await supabase
    .from("user_licenses")
    .select("license_key, role")
    .eq("user_id", userProfile.email);

  if (!userLicenses || userLicenses.length === 0) {
    // Try getting licenses by email directly
    const { data: licenses } = await supabase
      .from("licenses")
      .select("key, tier, status, trial_ends_at")
      .eq("email", userProfile.email);

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
