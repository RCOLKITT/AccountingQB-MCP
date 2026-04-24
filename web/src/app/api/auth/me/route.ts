import { NextResponse } from "next/server";
import { createServerComponentClient } from "@/lib/supabase-server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/auth/me
 * Returns the authenticated user and their linked licenses.
 */
export async function GET() {
  try {
    const supabase = await createServerComponentClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 }
      );
    }

    const serviceSupabase = getSupabase();

    // Get linked licenses with full license info
    const { data: userLicenses } = await serviceSupabase
      .from("user_licenses")
      .select(
        `
        license_key,
        role,
        licenses (
          key,
          tier,
          status,
          email,
          trial_ends_at,
          created_at
        )
      `
      )
      .eq("user_id", user.id);

    // Get user profile
    const { data: profile } = await serviceSupabase
      .from("user_profiles")
      .select("display_name")
      .eq("id", user.id)
      .single();

    return NextResponse.json({
      user: {
        id: user.id,
        email: user.email,
        displayName: profile?.display_name || null,
      },
      licenses:
        userLicenses?.map((ul) => ({
          ...(ul.licenses as object),
          role: ul.role,
        })) || [],
    });
  } catch (err) {
    console.error("Auth me error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
