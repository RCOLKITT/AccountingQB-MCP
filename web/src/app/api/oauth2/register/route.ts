import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getOAuth2RegisterLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";
import {
  isValidRedirectUri,
  oauthError,
  randomToken,
  sha256Hex,
} from "@/lib/mcp-oauth";

/**
 * POST /api/oauth2/register
 * RFC 7591 Dynamic Client Registration for the remote MCP connector.
 *
 * MCP clients (Claude web/desktop/mobile) register themselves before running
 * the authorization-code + PKCE flow. Public clients (the default,
 * token_endpoint_auth_method "none") get no secret; "client_secret_post" is
 * also supported and returns a one-time client_secret.
 */
export async function POST(req: NextRequest) {
  // Rate limit by IP — registration is unauthenticated by design.
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getOAuth2RegisterLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return oauthError("invalid_client_metadata", "Request body must be JSON");
  }

  const redirectUris = body.redirect_uris;
  if (!Array.isArray(redirectUris) || redirectUris.length === 0) {
    return oauthError("invalid_redirect_uri", "redirect_uris is required");
  }
  if (redirectUris.length > 10) {
    return oauthError(
      "invalid_redirect_uri",
      "Too many redirect_uris (max 10)",
    );
  }
  for (const uri of redirectUris) {
    if (typeof uri !== "string" || !isValidRedirectUri(uri)) {
      return oauthError(
        "invalid_redirect_uri",
        `redirect_uris must be https (or http://localhost for development): ${String(uri)}`,
      );
    }
  }

  const clientName =
    typeof body.client_name === "string"
      ? body.client_name.slice(0, 200)
      : null;

  const requestedAuthMethod =
    typeof body.token_endpoint_auth_method === "string"
      ? body.token_endpoint_auth_method
      : "none";
  if (
    requestedAuthMethod !== "none" &&
    requestedAuthMethod !== "client_secret_post"
  ) {
    return oauthError(
      "invalid_client_metadata",
      "token_endpoint_auth_method must be 'none' or 'client_secret_post'",
    );
  }

  const clientId = `mcp_${randomToken(24)}`;
  let clientSecret: string | null = null;
  let clientSecretHash: string | null = null;
  if (requestedAuthMethod === "client_secret_post") {
    clientSecret = randomToken(32);
    clientSecretHash = sha256Hex(clientSecret);
  }

  const supabase = getSupabase();
  const { error } = await supabase.from("mcp_oauth_clients").insert({
    client_id: clientId,
    client_secret_hash: clientSecretHash,
    client_name: clientName,
    redirect_uris: redirectUris,
  });

  if (error) {
    console.error("OAuth client registration failed:", error);
    return NextResponse.json({ error: "server_error" }, { status: 500 });
  }

  return NextResponse.json(
    {
      client_id: clientId,
      client_name: clientName,
      redirect_uris: redirectUris,
      token_endpoint_auth_method: requestedAuthMethod,
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      ...(clientSecret ? { client_secret: clientSecret } : {}),
    },
    { status: 201, headers: { "Cache-Control": "no-store" } },
  );
}
