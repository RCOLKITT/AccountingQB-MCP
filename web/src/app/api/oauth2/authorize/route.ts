import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import {
  AUTH_CODE_TTL_MS,
  McpOAuthClient,
  oauthError,
  randomToken,
  sha256Hex,
} from "@/lib/mcp-oauth";

/**
 * POST /api/oauth2/authorize
 * Called by the /oauth/authorize consent page after the signed-in user
 * approves access for a specific license. Issues a single-use authorization
 * code (10-minute expiry; only its sha256 is stored) and returns the
 * redirect URL the page should navigate to.
 *
 * Body: { client_id, redirect_uri, state?, code_challenge,
 *         code_challenge_method?, scope?, license_key }
 */
export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: {
    client_id?: string;
    redirect_uri?: string;
    state?: string;
    code_challenge?: string;
    code_challenge_method?: string;
    scope?: string;
    license_key?: string;
  };
  try {
    body = await req.json();
  } catch {
    return oauthError("invalid_request", "Request body must be JSON");
  }

  const {
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: codeChallengeMethod,
    scope,
    license_key: licenseKey,
  } = body;

  if (!clientId || !redirectUri || !codeChallenge || !licenseKey) {
    return oauthError(
      "invalid_request",
      "client_id, redirect_uri, code_challenge and license_key are required"
    );
  }
  // OAuth 2.1: PKCE S256 only.
  if (codeChallengeMethod && codeChallengeMethod !== "S256") {
    return oauthError("invalid_request", "code_challenge_method must be S256");
  }

  const supabase = getSupabase();

  // Validate the client and the exact redirect URI.
  const { data: client } = await supabase
    .from("mcp_oauth_clients")
    .select("client_id, client_secret_hash, client_name, redirect_uris, created_at")
    .eq("client_id", clientId)
    .maybeSingle<McpOAuthClient>();

  if (!client) {
    return oauthError("invalid_request", "Unknown client_id");
  }
  const registeredUris: string[] = Array.isArray(client.redirect_uris)
    ? client.redirect_uris
    : [];
  if (!registeredUris.includes(redirectUri)) {
    return oauthError("invalid_request", "redirect_uri is not registered for this client");
  }

  // Validate the license belongs to the signed-in user (same resolution as
  // /api/user/licenses: user_licenses by profile id, else licenses.email).
  const clerkUser = await currentUser();
  const clerkEmail = clerkUser?.emailAddresses[0]?.emailAddress?.toLowerCase();

  const { data: profile } = await supabase
    .from("user_profiles")
    .select("id")
    .eq("clerk_id", userId)
    .maybeSingle();

  let owned = false;
  if (profile) {
    const { data: link } = await supabase
      .from("user_licenses")
      .select("license_key")
      .eq("user_id", String(profile.id))
      .eq("license_key", licenseKey)
      .maybeSingle();
    owned = !!link;
  }
  if (!owned && clerkEmail) {
    const { data: license } = await supabase
      .from("licenses")
      .select("key")
      .eq("key", licenseKey)
      .ilike("email", clerkEmail)
      .maybeSingle();
    owned = !!license;
  }
  if (!owned) {
    return oauthError("access_denied", "License does not belong to this user", 403);
  }

  // License must be usable (mirrors /api/oauth/token's status check).
  const { data: license } = await supabase
    .from("licenses")
    .select("key, status")
    .eq("key", licenseKey)
    .maybeSingle();
  if (!license || license.status === "canceled" || license.status === "expired") {
    return oauthError("access_denied", "License is not active", 403);
  }

  // Issue the code: 32 random bytes; only the sha256 hex is stored.
  const code = randomToken(32);
  const { error: insertError } = await supabase.from("mcp_oauth_codes").insert({
    code_hash: sha256Hex(code),
    client_id: clientId,
    license_key: licenseKey,
    user_clerk_id: userId,
    code_challenge: codeChallenge,
    redirect_uri: redirectUri,
    scope: scope || null,
    expires_at: new Date(Date.now() + AUTH_CODE_TTL_MS).toISOString(),
  });

  if (insertError) {
    console.error("Failed to store authorization code:", insertError);
    return NextResponse.json({ error: "server_error" }, { status: 500 });
  }

  const redirect = new URL(redirectUri);
  redirect.searchParams.set("code", code);
  if (state) {
    redirect.searchParams.set("state", state);
  }

  return NextResponse.json(
    { redirect: redirect.toString() },
    { headers: { "Cache-Control": "no-store" } }
  );
}
