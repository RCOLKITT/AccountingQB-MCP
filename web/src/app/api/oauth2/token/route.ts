import { NextRequest, NextResponse } from "next/server";
import { SignJWT } from "jose";
import { getSupabase } from "@/lib/supabase";
import {
  getOAuth2TokenLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";
import {
  ACCESS_TOKEN_TTL_SECONDS,
  REFRESH_TOKEN_TTL_MS,
  McpOAuthClient,
  issuerUrl,
  oauthError,
  randomToken,
  resourceUrl,
  sha256Base64Url,
  sha256Hex,
} from "@/lib/mcp-oauth";

/**
 * POST /api/oauth2/token — OAuth 2.1 token endpoint (form-encoded).
 *
 * grant_type=authorization_code:
 *   code + code_verifier (PKCE S256) + client_id + redirect_uri
 *   -> { access_token (15-min HS256 JWT, aud = MCP_RESOURCE_URL),
 *        refresh_token (opaque, 90-day, sha256-stored), ... }
 *
 * grant_type=refresh_token:
 *   rotating refresh tokens — each use revokes the presented token and
 *   issues a new one linked via rotated_from. Presenting an already-revoked
 *   token is treated as theft: the whole rotation chain is revoked.
 */
export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getOAuth2TokenLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  if (!process.env.MCP_JWT_SECRET) {
    console.error("MCP_JWT_SECRET is not configured");
    return oauthError("server_error", "Token service is not configured", 500);
  }

  // OAuth requires application/x-www-form-urlencoded; accept JSON too for
  // lenient clients.
  let params: URLSearchParams;
  const contentType = req.headers.get("content-type") || "";
  try {
    if (contentType.includes("application/json")) {
      params = new URLSearchParams(
        Object.entries((await req.json()) as Record<string, string>)
      );
    } else {
      params = new URLSearchParams(await req.text());
    }
  } catch {
    return oauthError("invalid_request", "Malformed request body");
  }

  const grantType = params.get("grant_type");
  if (grantType === "authorization_code") {
    return handleAuthorizationCode(params);
  }
  if (grantType === "refresh_token") {
    return handleRefreshToken(params);
  }
  return oauthError("unsupported_grant_type", `Unsupported grant_type: ${grantType}`);
}

// ---------------------------------------------------------------------------
// Client authentication (public clients: "none"; confidential: secret_post)
// ---------------------------------------------------------------------------
async function loadAndAuthenticateClient(
  params: URLSearchParams
): Promise<McpOAuthClient | NextResponse> {
  const clientId = params.get("client_id");
  if (!clientId) {
    return oauthError("invalid_client", "client_id is required", 401);
  }

  const supabase = getSupabase();
  const { data: client } = await supabase
    .from("mcp_oauth_clients")
    .select("client_id, client_secret_hash, client_name, redirect_uris, created_at")
    .eq("client_id", clientId)
    .maybeSingle<McpOAuthClient>();

  if (!client) {
    return oauthError("invalid_client", "Unknown client", 401);
  }

  if (client.client_secret_hash) {
    const secret = params.get("client_secret");
    if (!secret || sha256Hex(secret) !== client.client_secret_hash) {
      return oauthError("invalid_client", "Client authentication failed", 401);
    }
  }
  return client;
}

// ---------------------------------------------------------------------------
// Token minting
// ---------------------------------------------------------------------------
async function mintAccessToken(licenseKey: string, userClerkId: string | null) {
  const secret = new TextEncoder().encode(process.env.MCP_JWT_SECRET);
  return new SignJWT({ license_key: licenseKey })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(userClerkId || licenseKey)
    .setAudience(resourceUrl())
    .setIssuer(issuerUrl())
    .setIssuedAt()
    .setExpirationTime(`${ACCESS_TOKEN_TTL_SECONDS}s`)
    .sign(secret);
}

async function issueTokenPair(
  clientId: string,
  licenseKey: string,
  userClerkId: string | null,
  scope: string | null,
  rotatedFrom: string | null
): Promise<NextResponse> {
  const supabase = getSupabase();

  const refreshToken = randomToken(48);
  const { error } = await supabase.from("mcp_refresh_tokens").insert({
    token_hash: sha256Hex(refreshToken),
    client_id: clientId,
    license_key: licenseKey,
    user_clerk_id: userClerkId,
    expires_at: new Date(Date.now() + REFRESH_TOKEN_TTL_MS).toISOString(),
    rotated_from: rotatedFrom,
    revoked: false,
  });
  if (error) {
    console.error("Failed to store refresh token:", error);
    return oauthError("server_error", "Could not issue tokens", 500);
  }

  const accessToken = await mintAccessToken(licenseKey, userClerkId);

  return NextResponse.json(
    {
      access_token: accessToken,
      token_type: "Bearer",
      expires_in: ACCESS_TOKEN_TTL_SECONDS,
      refresh_token: refreshToken,
      ...(scope ? { scope } : {}),
    },
    { headers: { "Cache-Control": "no-store", Pragma: "no-cache" } }
  );
}

// ---------------------------------------------------------------------------
// grant_type=authorization_code
// ---------------------------------------------------------------------------
async function handleAuthorizationCode(params: URLSearchParams): Promise<NextResponse> {
  const clientOrError = await loadAndAuthenticateClient(params);
  if (clientOrError instanceof NextResponse) return clientOrError;
  const client = clientOrError;

  const code = params.get("code");
  const codeVerifier = params.get("code_verifier");
  const redirectUri = params.get("redirect_uri");
  if (!code || !codeVerifier || !redirectUri) {
    return oauthError(
      "invalid_request",
      "code, code_verifier and redirect_uri are required"
    );
  }

  const supabase = getSupabase();
  const codeHash = sha256Hex(code);
  const { data: row } = await supabase
    .from("mcp_oauth_codes")
    .select("*")
    .eq("code_hash", codeHash)
    .maybeSingle();

  if (!row) {
    return oauthError("invalid_grant", "Unknown or already-used authorization code");
  }

  // Single-use: delete immediately so a replay can never succeed, even if
  // one of the later validations fails.
  await supabase.from("mcp_oauth_codes").delete().eq("code_hash", codeHash);

  if (new Date(row.expires_at).getTime() < Date.now()) {
    return oauthError("invalid_grant", "Authorization code has expired");
  }
  if (row.client_id !== client.client_id) {
    return oauthError("invalid_grant", "Code was issued to a different client");
  }
  if (row.redirect_uri !== redirectUri) {
    return oauthError("invalid_grant", "redirect_uri does not match");
  }
  // PKCE S256: BASE64URL(SHA256(code_verifier)) must equal the stored challenge.
  if (sha256Base64Url(codeVerifier) !== row.code_challenge) {
    return oauthError("invalid_grant", "PKCE verification failed");
  }

  return issueTokenPair(
    client.client_id,
    row.license_key,
    row.user_clerk_id ?? null,
    row.scope ?? null,
    null
  );
}

// ---------------------------------------------------------------------------
// grant_type=refresh_token (rotation + basic reuse detection)
// ---------------------------------------------------------------------------
interface RefreshTokenRow {
  token_hash: string;
  client_id: string | null;
  license_key: string;
  user_clerk_id: string | null;
  expires_at: string;
  rotated_from: string | null;
  revoked: boolean;
}

/**
 * Revoke the entire rotation chain that `hash` belongs to: walk ancestors via
 * rotated_from, then revoke every descendant. Bounded to avoid pathological
 * chains.
 */
async function revokeChain(startHash: string): Promise<void> {
  const supabase = getSupabase();

  // Walk back to the chain root.
  let rootHash = startHash;
  for (let i = 0; i < 50; i++) {
    const { data: node } = await supabase
      .from("mcp_refresh_tokens")
      .select("rotated_from")
      .eq("token_hash", rootHash)
      .maybeSingle();
    if (!node?.rotated_from) break;
    rootHash = node.rotated_from;
  }

  // Revoke root + all descendants breadth-first.
  let frontier = [rootHash];
  for (let depth = 0; depth < 50 && frontier.length > 0; depth++) {
    await supabase
      .from("mcp_refresh_tokens")
      .update({ revoked: true })
      .in("token_hash", frontier);
    const { data: children } = await supabase
      .from("mcp_refresh_tokens")
      .select("token_hash")
      .in("rotated_from", frontier);
    frontier = (children || []).map((c) => c.token_hash);
  }
}

async function handleRefreshToken(params: URLSearchParams): Promise<NextResponse> {
  const clientOrError = await loadAndAuthenticateClient(params);
  if (clientOrError instanceof NextResponse) return clientOrError;
  const client = clientOrError;

  const refreshToken = params.get("refresh_token");
  if (!refreshToken) {
    return oauthError("invalid_request", "refresh_token is required");
  }

  const supabase = getSupabase();
  const tokenHash = sha256Hex(refreshToken);
  const { data: row } = await supabase
    .from("mcp_refresh_tokens")
    .select("*")
    .eq("token_hash", tokenHash)
    .maybeSingle<RefreshTokenRow>();

  if (!row) {
    return oauthError("invalid_grant", "Unknown refresh token");
  }

  if (row.revoked) {
    // Reuse of a rotated-out token = likely theft. Kill the whole chain.
    console.warn("Refresh token reuse detected; revoking chain", {
      client_id: row.client_id,
      license_key: row.license_key,
    });
    await revokeChain(tokenHash);
    return oauthError("invalid_grant", "Refresh token has been revoked");
  }

  if (row.client_id && row.client_id !== client.client_id) {
    return oauthError("invalid_grant", "Token was issued to a different client");
  }

  if (new Date(row.expires_at).getTime() < Date.now()) {
    return oauthError("invalid_grant", "Refresh token has expired");
  }

  // Rotate: revoke the presented token, then issue a new pair linked to it.
  await supabase
    .from("mcp_refresh_tokens")
    .update({ revoked: true })
    .eq("token_hash", tokenHash);

  return issueTokenPair(
    client.client_id,
    row.license_key,
    row.user_clerk_id,
    null,
    tokenHash
  );
}
