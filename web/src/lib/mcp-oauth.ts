/**
 * Shared helpers for the OAuth 2.1 authorization server that fronts the
 * remote MCP connector (Phase 6).
 *
 * Endpoints: /.well-known/oauth-authorization-server, /api/oauth2/register,
 * /oauth/authorize (+ /api/oauth2/authorize), /api/oauth2/token,
 * /api/oauth2/client-info. Tables: mcp_oauth_clients, mcp_oauth_codes,
 * mcp_refresh_tokens (web/migrations/2026-07-mcp-oauth.sql).
 */
import { createHash, randomBytes } from "crypto";
import { NextResponse } from "next/server";

/** Issuer / base URL of the authorization server. */
export function issuerUrl(): string {
  return (process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com").replace(/\/$/, "");
}

/** Audience for minted access tokens = the remote MCP resource URL. */
export function resourceUrl(): string {
  return (process.env.MCP_RESOURCE_URL || "https://mcp.accountingqb.com").replace(/\/$/, "");
}

/** sha256 hex digest — used to store codes / refresh tokens at rest. */
export function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

/** sha256 base64url digest — used for PKCE S256 verification. */
export function sha256Base64Url(input: string): string {
  return createHash("sha256").update(input).digest("base64url");
}

/** Cryptographically random base64url token. */
export function randomToken(bytes: number): string {
  return randomBytes(bytes).toString("base64url");
}

/**
 * OAuth 2.1 redirect URI rules: https required, except loopback for dev.
 * Exact-match comparison is done against the stored registration.
 */
export function isValidRedirectUri(uri: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(uri);
  } catch {
    return false;
  }
  if (parsed.protocol === "https:") return true;
  if (
    parsed.protocol === "http:" &&
    (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1")
  ) {
    return true;
  }
  return false;
}

/** RFC 6749-style OAuth error JSON. */
export function oauthError(
  error: string,
  description?: string,
  status = 400
): NextResponse {
  return NextResponse.json(
    { error, ...(description ? { error_description: description } : {}) },
    {
      status,
      headers: { "Cache-Control": "no-store", Pragma: "no-cache" },
    }
  );
}

export const ACCESS_TOKEN_TTL_SECONDS = 15 * 60; // 15 minutes
export const AUTH_CODE_TTL_MS = 10 * 60 * 1000; // 10 minutes
export const REFRESH_TOKEN_TTL_MS = 90 * 24 * 60 * 60 * 1000; // 90 days

export interface McpOAuthClient {
  client_id: string;
  client_secret_hash: string | null;
  client_name: string | null;
  redirect_uris: string[];
  created_at: string;
}
