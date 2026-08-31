-- Cross-app pairing (AccountingQB ↔ Coffer/Hearth), identity-anchored.
-- link_codes: short-lived one-time codes minted by /api/link/issue; redeemed by the peer
-- product via /api/link/redeem ONLY when the presented identity_hash matches the one the code
-- was minted for (same verified account email) — a different user cannot redeem your code.
-- account_links: the resulting pairing (pairing_secret) for an account; the desktop app fetches
-- it via /api/link/status?key=<license> and hands it to its local shim. RLS deny-by-default
-- (service-role only), same posture as oauth_tokens; no book data is ever stored here.

CREATE TABLE IF NOT EXISTS link_codes (
  code            TEXT PRIMARY KEY,
  identity_hash   TEXT NOT NULL,                 -- sha256("aqb-coffer-link:v1:"+lower(email))
  pairing_secret  TEXT NOT NULL,
  license_key     TEXT REFERENCES licenses(key) ON DELETE CASCADE,
  peer_product    TEXT NOT NULL DEFAULT 'coffer',
  expires_at      TIMESTAMPTZ NOT NULL,
  redeemed_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_link_codes_expires ON link_codes (expires_at);
ALTER TABLE link_codes ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS account_links (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key     TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  identity_hash   TEXT NOT NULL,
  peer_product    TEXT NOT NULL DEFAULT 'coffer',
  peer_identity   TEXT,
  pairing_secret  TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  revoked_at      TIMESTAMPTZ,
  UNIQUE (license_key, peer_product)
);
CREATE INDEX IF NOT EXISTS idx_account_links_key ON account_links (license_key);
ALTER TABLE account_links ENABLE ROW LEVEL SECURITY;
