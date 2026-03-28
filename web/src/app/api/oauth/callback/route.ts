import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/oauth/callback
 * Handles the QuickBooks OAuth 2.0 callback.
 *
 * This endpoint:
 * 1. Exchanges the authorization code for access + refresh tokens
 * 2. Validates the license key
 * 3. Stores tokens in Supabase (encrypted at rest via Supabase)
 * 4. Redirects to success page
 */
export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code");
  const realmId = req.nextUrl.searchParams.get("realmId");
  const stateParam = req.nextUrl.searchParams.get("state");
  const errorParam = req.nextUrl.searchParams.get("error");

  // Handle OAuth errors
  if (errorParam) {
    const errorDesc = req.nextUrl.searchParams.get("error_description") || "Unknown error";
    return redirectWithError(`QuickBooks authorization failed: ${errorDesc}`);
  }

  if (!code || !realmId) {
    return redirectWithError("Missing authorization code or realm ID.");
  }

  // Decode state to get license key
  let licenseKey = "";
  if (stateParam) {
    try {
      const decoded = JSON.parse(
        Buffer.from(stateParam, "base64url").toString()
      );
      licenseKey = decoded.licenseKey || "";
    } catch {
      return redirectWithError("Invalid state parameter.");
    }
  }

  if (!licenseKey) {
    return redirectWithError("No license key provided. Please start the connection from your account dashboard.");
  }

  // Validate license key exists and is active
  const supabase = getSupabase();
  const { data: license, error: licenseError } = await supabase
    .from("licenses")
    .select("key, tier, status")
    .eq("key", licenseKey)
    .single();

  if (licenseError || !license) {
    return redirectWithError("Invalid license key. Please check your license and try again.");
  }

  if (license.status === "canceled" || license.status === "expired") {
    return redirectWithError("Your license is no longer active. Please renew your subscription.");
  }

  // Exchange code for tokens
  const clientId = process.env.QB_CLIENT_ID!;
  const clientSecret = process.env.QB_CLIENT_SECRET!;
  const redirectUri = process.env.QB_REDIRECT_URI!;

  const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  let tokenData;
  try {
    const tokenRes = await fetch("https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Basic ${basicAuth}`,
        "Accept": "application/json",
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code,
        redirect_uri: redirectUri,
      }),
    });

    if (!tokenRes.ok) {
      const errBody = await tokenRes.text();
      console.error("Token exchange failed:", errBody);
      return redirectWithError("Failed to exchange authorization code for tokens.");
    }

    tokenData = await tokenRes.json();
  } catch (err) {
    console.error("Token exchange error:", err);
    return redirectWithError("Network error during token exchange.");
  }

  // Fetch company info for display name
  let companyName = null;
  try {
    const companyRes = await fetch(
      `https://quickbooks.api.intuit.com/v3/company/${realmId}/companyinfo/${realmId}?minorversion=65`,
      {
        headers: {
          "Authorization": `Bearer ${tokenData.access_token}`,
          "Accept": "application/json",
        },
      }
    );
    if (companyRes.ok) {
      const companyData = await companyRes.json();
      companyName = companyData.CompanyInfo?.CompanyName || null;
    }
  } catch {
    // Non-critical — continue without company name
  }

  // Calculate token expiration (access tokens expire in 1 hour)
  const tokenExpiresAt = new Date(Date.now() + (tokenData.expires_in || 3600) * 1000).toISOString();

  // Store tokens in Supabase (upsert to handle reconnections)
  const { error: upsertError } = await supabase
    .from("oauth_tokens")
    .upsert(
      {
        license_key: licenseKey,
        realm_id: realmId,
        company_name: companyName,
        access_token: tokenData.access_token,
        refresh_token: tokenData.refresh_token,
        token_expires_at: tokenExpiresAt,
      },
      { onConflict: "license_key,realm_id" }
    );

  if (upsertError) {
    console.error("Failed to store OAuth tokens:", upsertError);
    return redirectWithError("Failed to save connection. Please try again.");
  }

  // Redirect to success page
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";
  const successUrl = new URL("/oauth/success", baseUrl);
  successUrl.searchParams.set("company", companyName || realmId);

  return NextResponse.redirect(successUrl.toString(), 303);
}

function redirectWithError(message: string) {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";
  const errorUrl = new URL("/oauth/error", baseUrl);
  errorUrl.searchParams.set("message", message);
  return NextResponse.redirect(errorUrl.toString(), 303);
}
