-- Phase 6: OAuth 2.1 authorization server for the remote MCP connector.
-- Run in the Supabase SQL editor (or via supabase db push). NOT auto-applied.
--
-- Tables:
--   mcp_oauth_clients   — dynamically registered OAuth clients (RFC 7591)
--   mcp_oauth_codes     — short-lived authorization codes (PKCE S256); the
--                         code itself is never stored, only its sha256 hex
--   mcp_refresh_tokens  — rotating opaque refresh tokens (sha256 hex hashes)
--                         with a rotated_from chain for reuse detection
--
-- Also adds licenses.default_realm_id: the QuickBooks company the remote MCP
-- service should activate for a license (falls back to first connected
-- company when NULL). See web/src/app/api/license/default-realm/route.ts.

CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
  client_id           TEXT PRIMARY KEY,
  client_secret_hash  TEXT,                 -- NULL for public clients (PKCE-only)
  client_name         TEXT,
  redirect_uris       JSONB NOT NULL,       -- array of exact-match redirect URIs
  created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_oauth_codes (
  code_hash       TEXT PRIMARY KEY,         -- sha256 hex of the authorization code
  client_id       TEXT REFERENCES mcp_oauth_clients (client_id),
  license_key     TEXT NOT NULL,
  user_clerk_id   TEXT,
  code_challenge  TEXT NOT NULL,            -- PKCE S256 challenge
  redirect_uri    TEXT NOT NULL,
  scope           TEXT,
  expires_at      TIMESTAMPTZ NOT NULL,     -- ~10 minutes after issuance
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_refresh_tokens (
  token_hash     TEXT PRIMARY KEY,          -- sha256 hex of the opaque token
  client_id      TEXT,
  license_key    TEXT NOT NULL,
  user_clerk_id  TEXT,
  expires_at     TIMESTAMPTZ NOT NULL,      -- 90 days after issuance
  rotated_from   TEXT,                      -- token_hash this one replaced (reuse-detection chain)
  revoked        BOOLEAN DEFAULT false,
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- Rotation/reuse-detection walks the rotated_from chain.
CREATE INDEX IF NOT EXISTS idx_mcp_refresh_tokens_rotated_from
  ON mcp_refresh_tokens (rotated_from);

-- Codes/tokens are looked up by hash (PK); cleanup jobs sweep by expiry.
CREATE INDEX IF NOT EXISTS idx_mcp_oauth_codes_expires_at
  ON mcp_oauth_codes (expires_at);
CREATE INDEX IF NOT EXISTS idx_mcp_refresh_tokens_expires_at
  ON mcp_refresh_tokens (expires_at);

-- Active company for the remote MCP service (NULL = first connected company).
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS default_realm_id TEXT;
