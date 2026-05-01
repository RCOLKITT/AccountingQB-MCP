import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getLicenseVerifyLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

// Log verification attempt (fire-and-forget)
function logVerification(
  supabase: ReturnType<typeof getSupabase>,
  licenseKey: string | null,
  action: string,
  success: boolean,
  ip: string,
  tier?: string
) {
  supabase
    .from("event_logs")
    .insert({
      event_type: "license_verify",
      license_key: licenseKey,
      action,
      payload: { ip, tier },
      success,
    })
    .then(() => {})
    .catch(() => {});
}

/**
 * POST /api/license/verify
 * Verify a license key is valid.
 */
export async function POST(req: NextRequest) {
  const ip = getClientIP(req);

  // Rate limit by IP
  if (isRateLimitingEnabled()) {
    const { success, reset } = await getLicenseVerifyLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  const body = await req.json();
  const { license_key } = body;

  if (!license_key) {
    return NextResponse.json(
      { valid: false, error: "License key required" },
      { status: 400 }
    );
  }

  const supabase = getSupabase();

  const { data: license, error } = await supabase
    .from("licenses")
    .select("key, email, tier, status, trial_ends_at")
    .eq("key", license_key)
    .single();

  if (error || !license) {
    logVerification(supabase, license_key, "not_found", false, ip);
    return NextResponse.json(
      { valid: false, error: "License key not found" },
      { status: 404 }
    );
  }

  // Check if license is active or trialing
  if (license.status === "expired" || license.status === "canceled") {
    logVerification(supabase, license_key, license.status, false, ip, license.tier);
    return NextResponse.json(
      { valid: false, error: `License is ${license.status}` },
      { status: 401 }
    );
  }

  // Check trial expiration
  if (license.status === "trialing" && license.trial_ends_at) {
    const trialEnd = new Date(license.trial_ends_at);
    if (trialEnd < new Date()) {
      logVerification(supabase, license_key, "trial_expired", false, ip, license.tier);
      return NextResponse.json(
        { valid: false, error: "Trial has expired" },
        { status: 401 }
      );
    }
  }

  logVerification(supabase, license_key, "verified", true, ip, license.tier);
  return NextResponse.json({
    valid: true,
    tier: license.tier,
    status: license.status,
  });
}
