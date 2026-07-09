import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getTokenLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";
import { logOAuthRefresh } from "@/lib/event-logger";

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
  // Rate limit: 10 requests per minute per IP
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getTokenLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

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

    // Refresh any expired tokens (single-flight per row via a DB lock)
    const refreshedTokens: OAuthTokenRow[] = [];
    for (const token of tokens as OAuthTokenRow[]) {
      refreshedTokens.push(
        await refreshTokenIfNeeded(supabase, licenseKey, token)
      );
    }

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

interface OAuthTokenRow {
  id: string;
  license_key: string;
  realm_id: string;
  company_name: string | null;
  access_token: string;
  refresh_token: string;
  token_expires_at: string;
  refresh_locked_at?: string | null;
}

const REFRESH_WINDOW_MS = 5 * 60 * 1000; // Refresh if token expires within 5 minutes
const LOCK_POLL_ATTEMPTS = 3;
const LOCK_POLL_INTERVAL_MS = 700;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Refreshes a token if it's close to expiry, coordinating across concurrent
 * requests via the claim_token_refresh() Postgres function (single-flight):
 * only the request that claims the row lock hits Intuit; other requests
 * poll for the refreshed row instead of firing duplicate refresh calls.
 *
 * Requires migrations/2026-07-oauth-refresh-lock.sql to be applied.
 */
async function refreshTokenIfNeeded(
  supabase: ReturnType<typeof getSupabase>,
  licenseKey: string,
  token: OAuthTokenRow
): Promise<OAuthTokenRow> {
  const expiresAt = new Date(token.token_expires_at);

  // Token is still fresh — nothing to do
  if (expiresAt.getTime() - Date.now() >= REFRESH_WINDOW_MS) {
    return token;
  }

  // Try to claim the refresh lock (stale locks > 30s are re-claimable)
  let claimed = true;
  const { data: claimResult, error: claimError } = await supabase.rpc(
    "claim_token_refresh",
    { p_id: token.id }
  );

  if (claimError) {
    // Function missing or RPC failure — fall back to refreshing directly
    console.error("claim_token_refresh RPC failed, refreshing without lock:", claimError);
  } else {
    claimed = claimResult === true;
  }

  if (claimed) {
    const refreshed = await refreshAccessToken(token);
    if (refreshed) {
      // Write back new tokens and release the lock
      await supabase
        .from("oauth_tokens")
        .update({
          access_token: refreshed.access_token,
          refresh_token: refreshed.refresh_token,
          token_expires_at: refreshed.token_expires_at,
          refresh_locked_at: null,
        })
        .eq("id", token.id);

      // Log successful token refresh
      await logOAuthRefresh(licenseKey, token.realm_id, true);

      return {
        ...token,
        access_token: refreshed.access_token,
        refresh_token: refreshed.refresh_token,
        token_expires_at: refreshed.token_expires_at,
      };
    }

    // Refresh failed — release the lock so another request can retry
    await supabase
      .from("oauth_tokens")
      .update({ refresh_locked_at: null })
      .eq("id", token.id);

    // Log failed token refresh
    await logOAuthRefresh(licenseKey, token.realm_id, false, "Refresh request failed");

    return token;
  }

  // Another request holds the lock — poll for the refreshed row
  let latest: OAuthTokenRow = token;
  for (let attempt = 0; attempt < LOCK_POLL_ATTEMPTS; attempt++) {
    await sleep(LOCK_POLL_INTERVAL_MS);

    const { data: row } = await supabase
      .from("oauth_tokens")
      .select("*")
      .eq("id", token.id)
      .maybeSingle();

    if (row) {
      latest = row as OAuthTokenRow;
      // If the stored token now expires in the future, the other request
      // finished refreshing — return the stored tokens
      if (new Date(latest.token_expires_at).getTime() > Date.now()) {
        return latest;
      }
    }
  }

  // Lock holder didn't finish in time — return the stored row as-is
  return latest;
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
