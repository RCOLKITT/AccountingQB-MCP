import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * POST /api/validate
 * Validates a license key. Called by the MCP server every 24 hours.
 * Returns: { valid: boolean, tier: string, reason?: string }
 */
export async function POST(req: NextRequest) {
  try {
    const { key } = await req.json();

    if (!key) {
      return NextResponse.json(
        { valid: false, tier: "free", reason: "no_key" },
        { status: 200 },
      );
    }

    const supabase = getSupabase();

    const { data: license, error } = await supabase
      .from("licenses")
      .select("*")
      .eq("key", key)
      .single();

    if (error || !license) {
      return NextResponse.json(
        { valid: false, tier: "free", reason: "invalid_key" },
        { status: 200 },
      );
    }

    // Check status
    if (license.status === "canceled" || license.status === "expired") {
      return NextResponse.json(
        { valid: false, tier: "free", reason: "subscription_ended" },
        { status: 200 },
      );
    }

    // Check trial expiry
    if (
      license.status === "trialing" &&
      license.trial_ends_at &&
      new Date(license.trial_ends_at) < new Date()
    ) {
      // Trial expired — update status
      await supabase
        .from("licenses")
        .update({ status: "expired", updated_at: new Date().toISOString() })
        .eq("id", license.id);

      return NextResponse.json(
        { valid: false, tier: "free", reason: "trial_expired" },
        { status: 200 },
      );
    }

    return NextResponse.json(
      { valid: true, tier: license.tier },
      { status: 200 },
    );
  } catch (err) {
    console.error("License validation error:", err);
    // On error, allow access (offline resilience)
    return NextResponse.json(
      { valid: true, tier: "grace", reason: "validation_error" },
      { status: 200 },
    );
  }
}
