import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * POST /api/license/verify
 * Verify a license key is valid.
 */
export async function POST(req: NextRequest) {
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
    return NextResponse.json(
      { valid: false, error: "License key not found" },
      { status: 404 }
    );
  }

  // Check if license is active or trialing
  if (license.status === "expired" || license.status === "canceled") {
    return NextResponse.json(
      { valid: false, error: `License is ${license.status}` },
      { status: 401 }
    );
  }

  // Check trial expiration
  if (license.status === "trialing" && license.trial_ends_at) {
    const trialEnd = new Date(license.trial_ends_at);
    if (trialEnd < new Date()) {
      return NextResponse.json(
        { valid: false, error: "Trial has expired" },
        { status: 401 }
      );
    }
  }

  return NextResponse.json({
    valid: true,
    tier: license.tier,
    status: license.status,
  });
}
