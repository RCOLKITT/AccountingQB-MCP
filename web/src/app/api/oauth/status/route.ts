import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/oauth/status
 * Checks if a license has any connected QuickBooks companies.
 * Used by the setup wizard to detect when OAuth completes.
 */
export async function GET(req: NextRequest) {
  const licenseKey = req.nextUrl.searchParams.get("license_key");

  if (!licenseKey) {
    return NextResponse.json({ error: "Missing license_key" }, { status: 400 });
  }

  try {
    const supabase = getSupabase();

    // Check if this license has any tokens (connected companies)
    const { data: tokens, error } = await supabase
      .from("oauth_tokens")
      .select("realm_id, company_name")
      .eq("license_key", licenseKey)
      .limit(1);

    if (error) {
      console.error("OAuth status check error:", error);
      return NextResponse.json({ connected: false });
    }

    const connected = tokens && tokens.length > 0;

    return NextResponse.json({
      connected,
      companies: connected ? tokens.map(t => ({
        realmId: t.realm_id,
        companyName: t.company_name,
      })) : [],
    });
  } catch (err) {
    console.error("OAuth status error:", err);
    return NextResponse.json({ connected: false });
  }
}
