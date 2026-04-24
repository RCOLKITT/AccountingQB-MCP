import { NextRequest, NextResponse } from "next/server";
import { createServerComponentClient } from "@/lib/supabase-server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /auth/callback
 * Handles the magic link redirect from Supabase Auth.
 *
 * This endpoint:
 * 1. Exchanges the code for a session
 * 2. Creates/updates the user profile
 * 3. Auto-links existing licenses by matching email
 * 4. Redirects to the dashboard
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const code = searchParams.get("code");
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://accountingqb.com";

  if (!code) {
    return NextResponse.redirect(`${baseUrl}/login?error=missing_code`);
  }

  try {
    const supabase = await createServerComponentClient();

    // Exchange code for session
    const {
      data: { user },
      error,
    } = await supabase.auth.exchangeCodeForSession(code);

    if (error || !user) {
      console.error("Auth callback error:", error);
      return NextResponse.redirect(`${baseUrl}/login?error=auth_failed`);
    }

    const serviceSupabase = getSupabase();

    // Create or update user profile
    const { error: profileError } = await serviceSupabase
      .from("user_profiles")
      .upsert(
        {
          id: user.id,
          email: user.email!,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "id" }
      );

    if (profileError) {
      console.error("Failed to create user profile:", profileError);
      // Continue anyway - profile creation is not critical
    }

    // Auto-link existing licenses by email
    const { data: existingLicenses } = await serviceSupabase
      .from("licenses")
      .select("key")
      .eq("email", user.email!.toLowerCase());

    if (existingLicenses && existingLicenses.length > 0) {
      // Check if links already exist
      const { data: existingLinks } = await serviceSupabase
        .from("user_licenses")
        .select("license_key")
        .eq("user_id", user.id);

      const existingLinkKeys = new Set(
        existingLinks?.map((l) => l.license_key) || []
      );

      // Only insert links that don't already exist
      const newLinks = existingLicenses
        .filter((l) => !existingLinkKeys.has(l.key))
        .map((l) => ({
          user_id: user.id,
          license_key: l.key,
          role: "owner" as const,
        }));

      if (newLinks.length > 0) {
        const { error: linkError } = await serviceSupabase
          .from("user_licenses")
          .insert(newLinks);

        if (linkError) {
          console.error("Failed to link licenses:", linkError);
        } else {
          console.log(
            `Auto-linked ${newLinks.length} licenses for ${user.email}`
          );
        }
      }
    }

    // Redirect to dashboard
    return NextResponse.redirect(`${baseUrl}/dashboard`);
  } catch (err) {
    console.error("Auth callback exception:", err);
    return NextResponse.redirect(`${baseUrl}/login?error=server_error`);
  }
}
