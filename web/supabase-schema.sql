-- ============================================================
-- QuickBooks Accounting MCP — Supabase Schema
-- Run this in the Supabase SQL Editor to set up the database.
--
-- NOTE: This file reflects the LIVE production schema as of 2026-07.
-- Notable divergences from earlier versions:
--   * user_profiles.id is a standalone uuid (no FK to auth.users);
--     auth is handled by Clerk via user_profiles.clerk_id.
--   * user_licenses.user_id is TEXT and stores user_profiles.id as text.
--   * oauth_tokens.refresh_locked_at supports single-flight token refresh.
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

  -- Internal/demo account flag: excluded from admin funnel + campaigns
  is_test       BOOLEAN NOT NULL DEFAULT false,

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

  -- Single-flight refresh lock (claimed via claim_token_refresh();
  -- see migrations/2026-07-oauth-refresh-lock.sql)
  refresh_locked_at TIMESTAMPTZ,

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
-- Allocation profiles: per-realm, per-tax-year taxpayer business-use %
-- (home office, vehicle, per-account). TAXPAYER inputs — stored here, never in
-- the tax_ledger. See migrations/2026-08-allocation-profiles.sql.
-- ============================================================
CREATE TABLE IF NOT EXISTS allocation_profiles (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key  TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id     TEXT NOT NULL,
  tax_year     INT  NOT NULL,
  profile      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(license_key, realm_id, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_allocation_profiles_license_key
  ON allocation_profiles (license_key);

ALTER TABLE allocation_profiles ENABLE ROW LEVEL SECURITY;

CREATE TRIGGER set_allocation_profiles_updated_at
  BEFORE UPDATE ON allocation_profiles
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
-- User Profiles: linked to Clerk via clerk_id (no auth.users FK)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_profiles (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id      TEXT UNIQUE,    -- Clerk user ID (nullable for legacy rows)
  email         TEXT NOT NULL,
  display_name  TEXT,

  -- Timestamps
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_email
  ON user_profiles (email);

-- Row-Level Security (service role only — all access goes through API routes)
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

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
  -- Stores user_profiles.id as text (live prod uses TEXT, no FK)
  user_id       TEXT NOT NULL,
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

-- Row-Level Security (service role only — all access goes through API routes)
ALTER TABLE user_licenses ENABLE ROW LEVEL SECURITY;

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

-- ============================================================
-- Support Conversations: stores chat history for continuity
-- ============================================================

CREATE TABLE IF NOT EXISTS support_conversations (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key       TEXT REFERENCES licenses(key) ON DELETE SET NULL,
  anonymous_id      TEXT,           -- For non-authenticated users
  status            TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved', 'escalated')),
  metadata          JSONB,          -- tier, companies, page context

  -- Timestamps
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user conversations
CREATE INDEX IF NOT EXISTS idx_support_conversations_license_key
  ON support_conversations (license_key)
  WHERE license_key IS NOT NULL;

-- Index for anonymous conversations (cleanup)
CREATE INDEX IF NOT EXISTS idx_support_conversations_anonymous
  ON support_conversations (anonymous_id)
  WHERE anonymous_id IS NOT NULL;

-- Row-Level Security (service role only)
ALTER TABLE support_conversations ENABLE ROW LEVEL SECURITY;

-- Updated-at trigger
CREATE TRIGGER set_support_conversations_updated_at
  BEFORE UPDATE ON support_conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Support Messages: individual messages in a conversation
-- ============================================================

CREATE TABLE IF NOT EXISTS support_messages (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id   UUID NOT NULL REFERENCES support_conversations(id) ON DELETE CASCADE,
  role              TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content           TEXT NOT NULL,

  -- Timestamps
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Index for loading conversation history
CREATE INDEX IF NOT EXISTS idx_support_messages_conversation_id
  ON support_messages (conversation_id, created_at);

-- Row-Level Security (service role only)
ALTER TABLE support_messages ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Support Analytics: tracks common issues for KB improvement
-- ============================================================

CREATE TABLE IF NOT EXISTS support_analytics (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  topic             TEXT NOT NULL,  -- 'installation', 'oauth', 'tools', etc.
  resolved_self     BOOLEAN DEFAULT true,
  escalated         BOOLEAN DEFAULT false,

  -- Timestamps
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Index for analytics queries
CREATE INDEX IF NOT EXISTS idx_support_analytics_topic
  ON support_analytics (topic);

-- Row-Level Security (service role only)
ALTER TABLE support_analytics ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Email Unsubscribes: marketing suppression list (CAN-SPAM / CASL).
-- Transactional email ignores this; only campaigns/marketing check it.
-- ============================================================

CREATE TABLE IF NOT EXISTS email_unsubscribes (
  email           TEXT PRIMARY KEY,
  scope           TEXT NOT NULL DEFAULT 'marketing',  -- marketing | all
  reason          TEXT,
  source          TEXT,                                -- 'link' | 'admin' | 'bounce'
  unsubscribed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Deny-by-default (service-role only), like every other table.
ALTER TABLE email_unsubscribes ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Email Schedules: queue for scheduled/automated emails
-- ============================================================

CREATE TABLE IF NOT EXISTS email_schedules (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key     TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  email_type      TEXT NOT NULL,  -- 'welcome', 'day_3_checkin', 'trial_warning_4day', etc.
  scheduled_for   TIMESTAMPTZ NOT NULL,
  sent_at         TIMESTAMPTZ,
  cancelled       BOOLEAN DEFAULT false,
  metadata        JSONB,          -- Template variables (email, name, tier, etc.)
  error_message   TEXT,           -- If sending failed

  -- Timestamps
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for processing pending emails
CREATE INDEX IF NOT EXISTS idx_email_schedules_pending
  ON email_schedules (scheduled_for)
  WHERE sent_at IS NULL AND cancelled = false;

-- Index for license lookups
CREATE INDEX IF NOT EXISTS idx_email_schedules_license_key
  ON email_schedules (license_key);

-- Index for email type queries
CREATE INDEX IF NOT EXISTS idx_email_schedules_type
  ON email_schedules (email_type);

-- Row-Level Security (service role only)
ALTER TABLE email_schedules ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- User Milestones: tracks user progress through setup
-- ============================================================

CREATE TABLE IF NOT EXISTS user_milestones (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key     TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  milestone       TEXT NOT NULL,  -- 'signup', 'qb_connected', 'first_tool_used', 'trial_converted'
  completed_at    TIMESTAMPTZ DEFAULT NOW(),
  metadata        JSONB,          -- Additional context (realm_id, tool_name, etc.)

  -- One milestone per type per license
  UNIQUE(license_key, milestone)
);

-- Index for license lookups
CREATE INDEX IF NOT EXISTS idx_user_milestones_license_key
  ON user_milestones (license_key);

-- Index for milestone type queries
CREATE INDEX IF NOT EXISTS idx_user_milestones_type
  ON user_milestones (milestone);

-- Row-Level Security (service role only)
ALTER TABLE user_milestones ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Trial Extensions: audit trail for admin-granted extensions
-- ============================================================

CREATE TABLE IF NOT EXISTS trial_extensions (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key     TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  extended_by     TEXT NOT NULL,  -- Admin email who granted extension
  extension_days  INTEGER NOT NULL,
  old_trial_end   TIMESTAMPTZ NOT NULL,
  new_trial_end   TIMESTAMPTZ NOT NULL,
  reason          TEXT,           -- Optional reason for extension

  -- Timestamps
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for license lookups
CREATE INDEX IF NOT EXISTS idx_trial_extensions_license_key
  ON trial_extensions (license_key);

-- Row-Level Security (service role only)
ALTER TABLE trial_extensions ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Admin Users: controls access to /admin dashboard
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_users (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email           TEXT NOT NULL UNIQUE,
  role            TEXT NOT NULL DEFAULT 'admin'
                    CHECK (role IN ('admin', 'super_admin')),

  -- Timestamps
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Row-Level Security (service role only)
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

-- Seed initial admin (update with your email)
INSERT INTO admin_users (email, role)
VALUES ('ryan@vasperacapital.com', 'super_admin')
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- Add billing columns to licenses table (for charge notifications)
-- Run these ALTER statements if the table already exists
-- ============================================================

ALTER TABLE licenses ADD COLUMN IF NOT EXISTS card_last_four TEXT;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS card_brand TEXT;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS next_billing_date TIMESTAMPTZ;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS billing_amount_cents INTEGER;

-- ============================================================
-- Artifacts: stores Claude-generated reports, analyses, exports
-- ============================================================

CREATE TABLE IF NOT EXISTS artifacts (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key     TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id        TEXT,           -- QuickBooks company ID (nullable for cross-company reports)

  -- Artifact metadata
  type            TEXT NOT NULL   -- 'report', 'analysis', 'reconciliation', 'export'
                    CHECK (type IN ('report', 'analysis', 'reconciliation', 'export')),
  name            TEXT NOT NULL,
  description     TEXT,

  -- Content
  data            JSONB NOT NULL, -- Structured data for rendering (tables, charts, summaries)
  format          TEXT DEFAULT 'table'  -- 'table', 'chart', 'summary', 'pdf'
                    CHECK (format IN ('table', 'chart', 'summary', 'pdf')),

  -- Organization
  tags            TEXT[],
  starred         BOOLEAN DEFAULT false,

  -- Provenance
  created_by      TEXT DEFAULT 'claude',  -- 'claude' or user_id

  -- Timestamps
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for license lookups (primary query path)
CREATE INDEX IF NOT EXISTS idx_artifacts_license_key
  ON artifacts (license_key);

-- Index for company-specific queries
CREATE INDEX IF NOT EXISTS idx_artifacts_realm_id
  ON artifacts (realm_id)
  WHERE realm_id IS NOT NULL;

-- Index for type filtering
CREATE INDEX IF NOT EXISTS idx_artifacts_type
  ON artifacts (type);

-- Index for starred items
CREATE INDEX IF NOT EXISTS idx_artifacts_starred
  ON artifacts (license_key, starred)
  WHERE starred = true;

-- Index for recent artifacts
CREATE INDEX IF NOT EXISTS idx_artifacts_created_at
  ON artifacts (license_key, created_at DESC);

-- Row-Level Security (service role only)
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;

-- Updated-at trigger for artifacts
CREATE TRIGGER set_artifacts_updated_at
  BEFORE UPDATE ON artifacts
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- MRR snapshots — monthly MRR-by-account for NRR / expansion / MRR trend
-- (see migrations/2026-08-mrr-snapshots.sql)
-- ============================================================================
CREATE TABLE IF NOT EXISTS mrr_snapshots (
  month        TEXT NOT NULL,
  license_key  TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  mrr_cents    INTEGER NOT NULL,
  tier         TEXT,
  status       TEXT,
  captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (month, license_key)
);
CREATE INDEX IF NOT EXISTS idx_mrr_snapshots_month ON mrr_snapshots(month);
ALTER TABLE mrr_snapshots ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Desktop app downloads — macOS vs Windows download tracking
-- (see migrations/2026-08-app-downloads.sql)
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_downloads (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  platform        TEXT NOT NULL CHECK (platform IN ('macos', 'windows')),
  version         TEXT,
  license_key     TEXT REFERENCES licenses(key) ON DELETE SET NULL,
  ip_hash         TEXT,
  user_agent_hash TEXT,
  referrer        TEXT,
  downloaded_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_downloads_platform      ON app_downloads (platform);
CREATE INDEX IF NOT EXISTS idx_app_downloads_downloaded_at ON app_downloads (downloaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_downloads_platform_time ON app_downloads (platform, downloaded_at DESC);
ALTER TABLE app_downloads ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Cross-app pairing (AccountingQB ↔ Coffer/Hearth), identity-anchored
-- (see migrations/2026-08-account-links.sql)
-- ============================================================================
CREATE TABLE IF NOT EXISTS link_codes (
  code            TEXT PRIMARY KEY,
  identity_hash   TEXT NOT NULL,
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
