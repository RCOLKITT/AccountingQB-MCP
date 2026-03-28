-- ============================================================
-- QuickBooks Accounting MCP — Supabase Schema
-- Run this in the Supabase SQL Editor to set up the database.
-- ============================================================

-- Licenses table: stores subscription and trial information
CREATE TABLE IF NOT EXISTS licenses (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  key           TEXT NOT NULL UNIQUE,
  email         TEXT NOT NULL DEFAULT '',
  tier          TEXT NOT NULL DEFAULT 'solopreneur'
                  CHECK (tier IN ('solopreneur', 'business', 'firm')),
  status        TEXT NOT NULL DEFAULT 'trialing'
                  CHECK (status IN ('active', 'trialing', 'canceled', 'expired')),

  -- Stripe references
  stripe_customer_id     TEXT,
  stripe_subscription_id TEXT,

  -- Trial tracking
  trial_ends_at TIMESTAMPTZ,

  -- Timestamps
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast license key lookups (the primary query path)
CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses (key);

-- Index for Stripe subscription lookups (webhook handler path)
CREATE INDEX IF NOT EXISTS idx_licenses_stripe_sub
  ON licenses (stripe_subscription_id)
  WHERE stripe_subscription_id IS NOT NULL;

-- Index for email lookups (customer support)
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses (email);

-- Row-Level Security: only the service role can access licenses
-- (our Vercel API routes use the service role key)
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;

-- No public access — all operations go through the service role
-- which bypasses RLS. This ensures the anon key can't read licenses.
-- If you need anon access later, add specific policies here.

-- Updated-at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON licenses
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- OAuth Tokens: stores QuickBooks OAuth tokens for each license
-- ============================================================

CREATE TABLE IF NOT EXISTS oauth_tokens (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key       TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id          TEXT NOT NULL,
  company_name      TEXT,

  -- Tokens (will be encrypted in production)
  access_token      TEXT NOT NULL,
  refresh_token     TEXT NOT NULL,
  token_expires_at  TIMESTAMPTZ NOT NULL,

  -- Timestamps
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),

  -- One connection per company per license
  UNIQUE(license_key, realm_id)
);

-- Index for token lookups by license key
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_license_key
  ON oauth_tokens (license_key);

-- Row-Level Security
ALTER TABLE oauth_tokens ENABLE ROW LEVEL SECURITY;

-- Updated-at trigger for oauth_tokens
CREATE TRIGGER set_oauth_tokens_updated_at
  BEFORE UPDATE ON oauth_tokens
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
