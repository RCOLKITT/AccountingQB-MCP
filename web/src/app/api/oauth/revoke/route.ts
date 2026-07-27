import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { logOAuthDisconnect } from "@/lib/event-logger";
import { decryptToken } from "@/lib/token-crypto";

/**
 * POST /api/oauth/revoke
 * Disconnects a QuickBooks company from a license.
 *
 * Body: { licenseKey: string, realmId: string }
 */
export async function POST(req: NextRequest) {
  try {
    const { licenseKey, realmId } = await req.json();

    if (!licenseKey || !realmId) {
      return NextResponse.json(
        { error: "License key and realm ID are required" },
        { status: 400 }
      );
    }

    const supabase = getSupabase();

    // Validate license
    const { data: license, error: licenseError } = await supabase
      .from("licenses")
      .select("key")
      .eq("key", licenseKey)
      .single();

    if (licenseError || !license) {
      return NextResponse.json(
        { error: "Invalid license key" },
        { status: 401 }
      );
    }

    // Get the token to revoke with Intuit
    const { data: token } = await supabase
      .from("oauth_tokens")
      .select("refresh_token")
      .eq("license_key", licenseKey)
      .eq("realm_id", realmId)
      .single();

    // Revoke token with Intuit (best effort)
    if (token?.refresh_token) {
      try {
        const clientId = process.env.QB_CLIENT_ID;
        const clientSecret = process.env.QB_CLIENT_SECRET;

        if (clientId && clientSecret) {
          const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

          await fetch("https://developer.api.intuit.com/v2/oauth2/tokens/revoke", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Basic ${basicAuth}`,
            },
            body: JSON.stringify({
              token: decryptToken(token.refresh_token),
            }),
          });
        }
      } catch {
        // Best effort — continue with deletion even if revoke fails
      }
    }

    // Delete from our database
    const { error: deleteError } = await supabase
      .from("oauth_tokens")
      .delete()
      .eq("license_key", licenseKey)
      .eq("realm_id", realmId);

    if (deleteError) {
      console.error("Failed to delete token:", deleteError);
      await logOAuthDisconnect(licenseKey, realmId, false, deleteError.message);
      return NextResponse.json(
        { error: "Failed to disconnect company" },
        { status: 500 }
      );
    }

    // Log successful disconnection
    await logOAuthDisconnect(licenseKey, realmId, true);

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Revoke endpoint error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
