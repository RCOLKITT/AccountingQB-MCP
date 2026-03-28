import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * POST /api/oauth/token
 * Returns OAuth tokens for a license key.
 * Used by the MCP server to fetch tokens on startup.
 *
 * Body: { licenseKey: string, realmId?: string }
 *
 * If realmId is provided, returns tokens for that specific company.
 * Otherwise, returns tokens for all connected companies.
 *
 * Automatically refreshes expired access tokens before returning.
 */
export async function POST(req: NextRequest) {
  try {
    const { licenseKey, realmId } = await req.json();

    if (!licenseKey) {
      return NextResponse.json(
        { error: "License key is required" },
        { status: 400 }
      );
    }

    const supabase = getSupabase();

    // Validate license
    const { data: license, error: licenseError } = await supabase
      .from("licenses")
      .select("key, tier, status")
      .eq("key", licenseKey)
      .single();

    if (licenseError || !license) {
      return NextResponse.json(
        { error: "Invalid license key" },
        { status: 401 }
      );
    }

    if (license.status === "canceled" || license.status === "expired") {
      return NextResponse.json(
        { error: "License is no longer active", status: license.status },
        { status: 403 }
      );
    }

    // Fetch tokens
    let query = supabase
      .from("oauth_tokens")
      .select("*")
      .eq("license_key", licenseKey);

    if (realmId) {
      query = query.eq("realm_id", realmId);
    }

    const { data: tokens, error: tokensError } = await query;

    if (tokensError) {
      console.error("Failed to fetch tokens:", tokensError);
      return NextResponse.json(
        { error: "Failed to fetch tokens" },
        { status: 500 }
      );
    }

    if (!tokens || tokens.length === 0) {
      return NextResponse.json(
        { error: "No QuickBooks companies connected", companies: [] },
        { status: 404 }
      );
    }

    // Refresh any expired tokens
    const refreshedTokens = await Promise.all(
      tokens.map(async (token) => {
        const expiresAt = new Date(token.token_expires_at);
        const now = new Date();

        // Refresh if token expires in less than 5 minutes
        if (expiresAt.getTime() - now.getTime() < 5 * 60 * 1000) {
          const refreshed = await refreshAccessToken(token);
          if (refreshed) {
            // Update in database
            await supabase
              .from("oauth_tokens")
              .update({
                access_token: refreshed.access_token,
                refresh_token: refreshed.refresh_token,
                token_expires_at: refreshed.token_expires_at,
              })
              .eq("id", token.id);

            return {
              ...token,
              access_token: refreshed.access_token,
              refresh_token: refreshed.refresh_token,
              token_expires_at: refreshed.token_expires_at,
            };
          }
        }
        return token;
      })
    );

    // Return tokens (strip internal fields)
    const companies = refreshedTokens.map((t) => ({
      realmId: t.realm_id,
      companyName: t.company_name,
      accessToken: t.access_token,
      refreshToken: t.refresh_token,
      expiresAt: t.token_expires_at,
    }));

    return NextResponse.json({
      license: {
        key: license.key,
        tier: license.tier,
        status: license.status,
      },
      companies,
    });
  } catch (err) {
    console.error("Token endpoint error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

/**
 * Refreshes an expired access token using the refresh token.
 */
async function refreshAccessToken(token: {
  refresh_token: string;
}): Promise<{
  access_token: string;
  refresh_token: string;
  token_expires_at: string;
} | null> {
  const clientId = process.env.QB_CLIENT_ID;
  const clientSecret = process.env.QB_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    console.error("Missing QB_CLIENT_ID or QB_CLIENT_SECRET");
    return null;
  }

  const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  try {
    const res = await fetch("https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Basic ${basicAuth}`,
        "Accept": "application/json",
      },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: token.refresh_token,
      }),
    });

    if (!res.ok) {
      console.error("Token refresh failed:", await res.text());
      return null;
    }

    const data = await res.json();
    const expiresAt = new Date(Date.now() + (data.expires_in || 3600) * 1000).toISOString();

    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      token_expires_at: expiresAt,
    };
  } catch (err) {
    console.error("Token refresh error:", err);
    return null;
  }
}
