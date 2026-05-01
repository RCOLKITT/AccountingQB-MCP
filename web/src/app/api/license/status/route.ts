import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getLicenseVerifyLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

// Log status check (fire-and-forget)
function logStatusCheck(
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
      event_type: "license_status",
      license_key: licenseKey,
      action,
      payload: { ip, tier },
      success,
    })
    .then(() => {})
    .catch(() => {});
}

/**
 * GET /api/license/status
 * Get license status including QuickBooks connections.
 */
export async function GET(req: NextRequest) {
  const ip = getClientIP(req);

  // Rate limit by IP
  if (isRateLimitingEnabled()) {
    const { success, reset } = await getLicenseVerifyLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  const { searchParams } = req.nextUrl;
  const licenseKey = searchParams.get("license_key");

  if (!licenseKey) {
    return NextResponse.json(
      { error: "License key required" },
      { status: 400 }
    );
  }

  const supabase = getSupabase();

  // Get license
  const { data: license, error: licenseError } = await supabase
    .from("licenses")
    .select("key, email, tier, status, trial_ends_at")
    .eq("key", licenseKey)
    .single();

  if (licenseError || !license) {
    logStatusCheck(supabase, licenseKey, "not_found", false, ip);
    return NextResponse.json(
      { error: "License key not found" },
      { status: 404 }
    );
  }

  // Get QuickBooks connections
  const { data: connections } = await supabase
    .from("oauth_tokens")
    .select("realm_id, company_name, created_at")
    .eq("license_key", licenseKey);

  // Get milestones
  const { data: milestones } = await supabase
    .from("user_milestones")
    .select("milestone, completed_at")
    .eq("license_key", licenseKey);

  logStatusCheck(supabase, licenseKey, "status_retrieved", true, ip, license.tier);
  return NextResponse.json({
    license: {
      tier: license.tier,
      status: license.status,
      trial_ends_at: license.trial_ends_at,
    },
    companies: connections || [],
    milestones: milestones || [],
  });
}
