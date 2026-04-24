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

-- ============================================================
-- Event Logs: stores webhook and OAuth events for audit trail
-- ============================================================

CREATE TABLE IF NOT EXISTS event_logs (
  id                     UUID DEFAULT gen_random_uuid() PRIMARY KEY,

  -- Event identification
  event_type             TEXT NOT NULL,  -- 'stripe_webhook' | 'oauth_connect' | 'oauth_disconnect' | 'oauth_refresh'
  event_id               TEXT,           -- External event ID (e.g., Stripe event ID)

  -- Context
  license_key            TEXT REFERENCES licenses(key) ON DELETE SET NULL,
  realm_id               TEXT,           -- QuickBooks company ID (for OAuth events)
  stripe_subscription_id TEXT,           -- For Stripe events

  -- Event details
  action                 TEXT NOT NULL,  -- e.g., 'checkout.session.completed' or 'quickbooks_connected'
  payload                JSONB,          -- Sanitized event payload

  -- Result
  success                BOOLEAN NOT NULL DEFAULT true,
  error_message          TEXT,

  -- Timestamps
  processed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying by event type
CREATE INDEX IF NOT EXISTS idx_event_logs_event_type
  ON event_logs (event_type);

-- Index for querying by license key
CREATE INDEX IF NOT EXISTS idx_event_logs_license_key
  ON event_logs (license_key)
  WHERE license_key IS NOT NULL;

-- Index for time-based queries (most recent first)
CREATE INDEX IF NOT EXISTS idx_event_logs_processed_at
  ON event_logs (processed_at DESC);

-- Unique constraint for Stripe event idempotency (prevent duplicate processing logs)
CREATE UNIQUE INDEX IF NOT EXISTS idx_event_logs_stripe_idempotent
  ON event_logs (event_id)
  WHERE event_type = 'stripe_webhook' AND event_id IS NOT NULL;

-- Row-Level Security
ALTER TABLE event_logs ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- User Profiles: linked to Supabase Auth for magic link login
-- ============================================================

CREATE TABLE IF NOT EXISTS user_profiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT NOT NULL,
  display_name  TEXT,

  -- Timestamps
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_email
  ON user_profiles (email);

-- Row-Level Security (users can only see their own profile)
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON user_profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  USING (auth.uid() = id);

-- Updated-at trigger for user_profiles
CREATE TRIGGER set_user_profiles_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- User Licenses: links users to licenses (many-to-many)
-- Supports agencies with multiple licenses per user
-- ============================================================

CREATE TABLE IF NOT EXISTS user_licenses (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id       UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
  license_key   TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  role          TEXT NOT NULL DEFAULT 'owner'
                  CHECK (role IN ('owner', 'member')),

  -- Timestamps
  created_at    TIMESTAMPTZ DEFAULT NOW(),

  -- One link per user per license
  UNIQUE(user_id, license_key)
);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_user_licenses_user_id
  ON user_licenses (user_id);

-- Index for license lookups
CREATE INDEX IF NOT EXISTS idx_user_licenses_license_key
  ON user_licenses (license_key);

-- Row-Level Security (users can only see their own license links)
ALTER TABLE user_licenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own license links"
  ON user_licenses FOR SELECT
  USING (auth.uid() = user_id);

-- ============================================================
-- Tool Usage: tracks MCP tool invocations for analytics
-- ============================================================

CREATE TABLE IF NOT EXISTS tool_usage (
  id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key         TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id            TEXT,           -- QuickBooks company ID
  tool_name           TEXT NOT NULL,
  time_saved_minutes  INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  invoked_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index for license lookups
CREATE INDEX IF NOT EXISTS idx_tool_usage_license_key
  ON tool_usage (license_key);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_tool_usage_invoked_at
  ON tool_usage (invoked_at DESC);

-- Index for tool analytics
CREATE INDEX IF NOT EXISTS idx_tool_usage_tool_name
  ON tool_usage (tool_name);

-- Row-Level Security (service role only - MCP server writes via API)
ALTER TABLE tool_usage ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Usage Stats Cache: aggregate stats for landing page
-- Refreshed every 5 minutes via cron job
-- ============================================================

CREATE TABLE IF NOT EXISTS usage_stats_cache (
  id                TEXT PRIMARY KEY DEFAULT 'global',
  total_tool_calls  BIGINT DEFAULT 0,
  total_hours_saved DECIMAL(10,1) DEFAULT 0,
  calls_this_week   BIGINT DEFAULT 0,
  active_licenses   INTEGER DEFAULT 0,

  -- Timestamps
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize with default row
INSERT INTO usage_stats_cache (id) VALUES ('global') ON CONFLICT (id) DO NOTHING;

-- Row-Level Security (service role only)
ALTER TABLE usage_stats_cache ENABLE ROW LEVEL SECURITY;
