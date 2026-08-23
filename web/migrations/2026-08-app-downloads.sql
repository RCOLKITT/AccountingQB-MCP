-- Desktop app download tracking (macOS vs Windows).
-- Recorded by the /api/download/[platform] redirect endpoint when a visitor clicks a
-- download link on the site, then 302s to the signed GitHub release asset. Privacy:
-- we store only a salted hash of IP + a hash of user-agent (for dedup/geo), never raw.
-- RLS enabled, no policy → deny-by-default (service-role only), same posture as oauth_tokens.

CREATE TABLE IF NOT EXISTS app_downloads (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  platform        TEXT NOT NULL CHECK (platform IN ('macos', 'windows')),
  version         TEXT,                                    -- release tag if provided (e.g. desktop-v0.1.0)
  license_key     TEXT REFERENCES licenses(key) ON DELETE SET NULL,  -- only when downloaded from the dashboard
  ip_hash         TEXT,                                    -- SHA-256(ip + salt)
  user_agent_hash TEXT,                                    -- SHA-256(user-agent)
  referrer        TEXT,                                    -- where the click came from (path only)
  downloaded_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_downloads_platform      ON app_downloads (platform);
CREATE INDEX IF NOT EXISTS idx_app_downloads_downloaded_at ON app_downloads (downloaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_downloads_platform_time ON app_downloads (platform, downloaded_at DESC);

ALTER TABLE app_downloads ENABLE ROW LEVEL SECURITY;
