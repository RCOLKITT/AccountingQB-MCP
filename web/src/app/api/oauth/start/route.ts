import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

/**
 * GET /api/oauth/start
 * Initiates the QuickBooks OAuth 2.0 authorization flow.
 * Redirects the user to Intuit's authorization page.
 *
 * Query params:
 *   - license_key (optional): passed through state for post-auth association
 */
export async function GET(req: NextRequest) {
  const clientId = process.env.QB_CLIENT_ID;
  const redirectUri = process.env.QB_REDIRECT_URI;

  if (!clientId || !redirectUri) {
    return NextResponse.json(
      { error: "OAuth not configured. Missing QB_CLIENT_ID or QB_REDIRECT_URI." },
      { status: 500 }
    );
  }

  const licenseKey = req.nextUrl.searchParams.get("license_key") || "";

  // Generate a random state parameter for CSRF protection
  const state = crypto.randomBytes(16).toString("hex");

  // Encode license key and state together so we can verify on callback
  const statePayload = Buffer.from(
    JSON.stringify({ state, licenseKey })
  ).toString("base64url");

  const scopes = [
    "com.intuit.quickbooks.accounting",
  ].join(" ");

  const authUrl = new URL("https://appcenter.intuit.com/connect/oauth2");
  authUrl.searchParams.set("client_id", clientId);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", scopes);
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("state", statePayload);

  return NextResponse.redirect(authUrl.toString(), 303);
}
