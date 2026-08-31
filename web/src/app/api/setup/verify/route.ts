import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * POST /api/setup/verify
 * Called by Claude MCP server to verify setup is complete.
 * Records that the user has successfully configured Claude Desktop.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { licenseKey } = body;

    if (!licenseKey) {
      return NextResponse.json(
        { error: "Missing licenseKey" },
        { status: 400 },
      );
    }

    const supabase = getSupabase();

    // Verify the license exists
    const { data: license, error: licenseError } = await supabase
      .from("licenses")
      .select("key, email, tier, status")
      .eq("key", licenseKey)
      .single();

    if (licenseError || !license) {
      return NextResponse.json(
        { error: "Invalid license key" },
        { status: 404 },
      );
    }

    // Record the milestone
    const { error: milestoneError } = await supabase
      .from("user_milestones")
      .upsert(
        {
          license_key: licenseKey,
          milestone: "claude_configured",
          completed_at: new Date().toISOString(),
        },
        {
          onConflict: "license_key,milestone",
        },
      );

    if (milestoneError) {
      console.error("Failed to record milestone:", milestoneError);
      // Don't fail the request, just log it
    }

    // Check QB connection status
    const { data: tokens } = await supabase
      .from("oauth_tokens")
      .select("realm_id, company_name")
      .eq("license_key", licenseKey);

    const hasQBConnected = tokens && tokens.length > 0;

    return NextResponse.json({
      success: true,
      message: "Setup verified successfully!",
      license: {
        tier: license.tier,
        status: license.status,
      },
      setup: {
        claudeConfigured: true,
        qbConnected: hasQBConnected,
        companies:
          tokens?.map((t) => ({
            realmId: t.realm_id,
            name: t.company_name,
          })) || [],
      },
      nextStep: hasQBConnected
        ? "You're all set! Try asking: 'Show me my P&L for last quarter'"
        : "Great! Now connect QuickBooks to start using AccountingQB.",
    });
  } catch (error) {
    console.error("Setup verify error:", error);
    return NextResponse.json(
      { error: "Failed to verify setup" },
      { status: 500 },
    );
  }
}

/**
 * GET /api/setup/verify
 * Check setup status without recording milestone.
 */
export async function GET(req: NextRequest) {
  const licenseKey = req.nextUrl.searchParams.get("license_key");

  if (!licenseKey) {
    return NextResponse.json(
      { error: "Missing license_key parameter" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();

  // Get license
  const { data: license, error: licenseError } = await supabase
    .from("licenses")
    .select("key, tier, status")
    .eq("key", licenseKey)
    .single();

  if (licenseError || !license) {
    return NextResponse.json({ error: "Invalid license key" }, { status: 404 });
  }

  // Check milestones
  const { data: milestones } = await supabase
    .from("user_milestones")
    .select("milestone, completed_at")
    .eq("license_key", licenseKey);

  const claudeConfigured =
    milestones?.some((m) => m.milestone === "claude_configured") || false;

  // Check QB connection
  const { data: tokens } = await supabase
    .from("oauth_tokens")
    .select("realm_id, company_name")
    .eq("license_key", licenseKey);

  const hasQBConnected = tokens && tokens.length > 0;

  return NextResponse.json({
    license: {
      tier: license.tier,
      status: license.status,
    },
    setup: {
      claudeConfigured,
      qbConnected: hasQBConnected,
      companies:
        tokens?.map((t) => ({
          realmId: t.realm_id,
          name: t.company_name,
        })) || [],
    },
  });
}
