import { NextResponse } from "next/server";
import { issuerUrl } from "@/lib/mcp-oauth";

/**
 * GET /.well-known/oauth-authorization-server
 * RFC 8414 authorization-server metadata for the remote MCP connector.
 * MCP clients discover this via the resource server's RFC 9728 document
 * (https://mcp.accountingqb.com/.well-known/oauth-protected-resource).
 */
export async function GET() {
  const issuer = issuerUrl();
  return NextResponse.json(
    {
      issuer,
      authorization_endpoint: `${issuer}/oauth/authorize`,
      token_endpoint: `${issuer}/api/oauth2/token`,
      registration_endpoint: `${issuer}/api/oauth2/register`,
      response_types_supported: ["code"],
      grant_types_supported: ["authorization_code", "refresh_token"],
      code_challenge_methods_supported: ["S256"],
      token_endpoint_auth_methods_supported: ["none", "client_secret_post"],
      scopes_supported: ["quickbooks"],
    },
    { headers: { "Cache-Control": "public, max-age=3600" } },
  );
}
