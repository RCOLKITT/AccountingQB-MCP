-- ============================================================
-- Migration: single-flight OAuth token refresh (2026-07)
--
-- MUST BE APPLIED to the live Supabase project (SQL Editor or
-- supabase migration tooling) before deploying the updated
-- /api/oauth/token route, which calls claim_token_refresh() via
-- supabase.rpc('claim_token_refresh', { p_id: <oauth_tokens.id> }).
-- ============================================================

-- Lock column (already added to live prod; kept here for completeness)
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS refresh_locked_at TIMESTAMPTZ;

-- Attempts to claim the refresh lock for an oauth_tokens row.
-- Returns true if this caller won the lock (and should perform the
-- refresh with Intuit), false if another request currently holds it.
-- A lock older than 30 seconds is considered stale and can be re-claimed.
CREATE OR REPLACE FUNCTION claim_token_refresh(p_id uuid)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  claimed boolean;
BEGIN
  UPDATE oauth_tokens
  SET refresh_locked_at = now()
  WHERE id = p_id
    AND (refresh_locked_at IS NULL OR refresh_locked_at < now() - interval '30 seconds');

  claimed := FOUND;
  RETURN claimed;
END;
$$;
