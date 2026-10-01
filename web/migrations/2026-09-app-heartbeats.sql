-- Local desktop-app activation + heartbeat (Phase 2 of the download→trial funnel).
--
-- The downloadable desktop app runs locally (BYO Anthropic key) and previously
-- sent NOTHING back, so 206 downloads were completely invisible — no identity,
-- no key, no usage. With a license attached (entered or minted via an in-app
-- trial), the app now sends a small periodic ACTIVATION PING — license key, app
-- version, platform, last-seen. No per-tool usage and NO financial data ever
-- leaves the machine (that promise is unchanged). One row per license/install,
-- upserted atomically. Service-role only (matches watchdog_state).

CREATE TABLE IF NOT EXISTS app_heartbeats (
  license_key     TEXT PRIMARY KEY,
  app_version     TEXT,
  platform        TEXT,
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  heartbeat_count INTEGER NOT NULL DEFAULT 1
);

ALTER TABLE app_heartbeats ENABLE ROW LEVEL SECURITY;

-- Atomic upsert — avoids a racy read-modify-write for the count. Called by
-- POST /api/app/heartbeat via the service role.
CREATE OR REPLACE FUNCTION record_app_heartbeat(
  p_license_key TEXT,
  p_app_version TEXT,
  p_platform    TEXT
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  INSERT INTO app_heartbeats (license_key, app_version, platform)
  VALUES (p_license_key, p_app_version, p_platform)
  ON CONFLICT (license_key) DO UPDATE SET
    app_version     = EXCLUDED.app_version,
    platform        = EXCLUDED.platform,
    last_seen_at    = now(),
    heartbeat_count = app_heartbeats.heartbeat_count + 1;
$$;
