import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getLicenseVerifyLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";
import { randomBytes } from "crypto";

function generateLicenseKey(): string {
  const bytes = randomBytes(16);
  const key = bytes.toString("hex").toUpperCase();
  // Format: XXXX-XXXX-XXXX-XXXX
  return `${key.slice(0, 4)}-${key.slice(4, 8)}-${key.slice(8, 12)}-${key.slice(12, 16)}`;
}

function logRotation(
  supabase: ReturnType<typeof getSupabase>,
  oldKey: string,
  newKey: string,
  success: boolean,
  ip: string,
  reason?: string
) {
  supabase
    .from("event_logs")
    .insert({
      event_type: "license_rotation",
      license_key: newKey,
      action: "rotate",
      payload: { old_key: oldKey, ip, reason },
      success,
    })
    .then(() => {})
    .catch(() => {});
}

/**
 * POST /api/license/rotate
 * Rotate a license key - generates a new key and invalidates the old one.
 * Requires the current license key for authentication.
 */
export async function POST(req: NextRequest) {
  const ip = getClientIP(req);

  // Stricter rate limit for rotation (1 per hour per IP)
  if (isRateLimitingEnabled()) {
    const { success, reset } = await getLicenseVerifyLimiter().limit(`rotate:${ip}`);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const { license_key, reason } = body;

  if (!license_key) {
    return NextResponse.json(
      { error: "Current license key required" },
      { status: 400 }
    );
  }

  const supabase = getSupabase();

  // Verify current license exists and is active
  const { data: license, error: licenseError } = await supabase
    .from("licenses")
    .select("id, key, email, tier, status")
    .eq("key", license_key)
    .single();

  if (licenseError || !license) {
    logRotation(supabase, license_key, "", false, ip, "not_found");
    return NextResponse.json(
      { error: "License key not found" },
      { status: 404 }
    );
  }

  if (license.status !== "active" && license.status !== "trial") {
    logRotation(supabase, license_key, "", false, ip, "inactive_license");
    return NextResponse.json(
      { error: "Cannot rotate inactive license" },
      { status: 400 }
    );
  }

  // Generate new key
  const newKey = generateLicenseKey();

  // Update license with new key
  const { error: updateError } = await supabase
    .from("licenses")
    .update({
      key: newKey,
      rotated_at: new Date().toISOString(),
      previous_key: license_key,
    })
    .eq("id", license.id);

  if (updateError) {
    logRotation(supabase, license_key, newKey, false, ip, "update_failed");
    return NextResponse.json(
      { error: "Failed to rotate key" },
      { status: 500 }
    );
  }

  // Update any OAuth tokens to use the new key
  await supabase
    .from("oauth_tokens")
    .update({ license_key: newKey })
    .eq("license_key", license_key);

  // Update milestones to use the new key
  await supabase
    .from("user_milestones")
    .update({ license_key: newKey })
    .eq("license_key", license_key);

  logRotation(supabase, license_key, newKey, true, ip, reason || "user_requested");

  return NextResponse.json({
    success: true,
    new_key: newKey,
    message: "License key rotated successfully. Update your local config with the new key.",
  });
}
