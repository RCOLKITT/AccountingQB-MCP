import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/license/status
 * Get license status including QuickBooks connections.
 */
export async function GET(req: NextRequest) {
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
