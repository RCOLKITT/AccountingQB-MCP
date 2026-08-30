import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import {
  getLicenseVerifyLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

async function logLink(
  supabase: ReturnType<typeof getSupabase>,
  licenseKey: string | null,
  clerkId: string,
  success: boolean,
  reason?: string,
) {
  try {
    await supabase.from("event_logs").insert({
      event_type: "license_link",
      license_key: licenseKey,
      action: "link",
      payload: { clerk_id: clerkId, reason },
      success,
    });
  } catch {
    // Logging is non-critical
  }
}

/**
 * POST /api/user/link-license
 * Link an existing license key to the authenticated Clerk user.
 *
 * Body: { licenseKey: string }
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Rate limit license lookups (same limiter as license verification)
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getLicenseVerifyLimiter().limit(
      `link:${ip}`,
    );
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const licenseKey =
    typeof body.licenseKey === "string" ? body.licenseKey.trim() : "";

  if (!licenseKey) {
    return NextResponse.json(
      { error: "License key is required" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();

  // Validate the license key exists (exact match)
  const { data: license, error: licenseError } = await supabase
    .from("licenses")
    .select("key, tier, status")
    .eq("key", licenseKey)
    .single();

  if (licenseError || !license) {
    await logLink(supabase, null, user.id, false, "not_found");
    return NextResponse.json(
      { error: "License key not found" },
      { status: 404 },
    );
  }

  const clerkEmail = user.emailAddresses[0]?.emailAddress?.toLowerCase() || "";

  // Upsert user profile by clerk_id (id assigned by DB default)
  const { data: profile, error: profileError } = await supabase
    .from("user_profiles")
    .upsert(
      {
        clerk_id: user.id,
        email: clerkEmail,
      },
      { onConflict: "clerk_id" },
    )
    .select("id")
    .single();

  if (profileError || !profile) {
    console.error("Failed to upsert user profile:", profileError);
    await logLink(
      supabase,
      license.key,
      user.id,
      false,
      "profile_upsert_failed",
    );
    return NextResponse.json(
      { error: "Failed to link license" },
      { status: 500 },
    );
  }

  // Link the license (user_licenses.user_id stores user_profiles.id as text)
  const { error: linkError } = await supabase.from("user_licenses").upsert(
    {
      user_id: String(profile.id),
      license_key: license.key,
      role: "owner",
    },
    { onConflict: "user_id,license_key" },
  );

  if (linkError) {
    console.error("Failed to link license:", linkError);
    await logLink(supabase, license.key, user.id, false, "link_upsert_failed");
    return NextResponse.json(
      { error: "Failed to link license" },
      { status: 500 },
    );
  }

  await logLink(supabase, license.key, user.id, true);

  return NextResponse.json({
    success: true,
    license: {
      key: license.key,
      tier: license.tier,
      status: license.status,
    },
  });
}
