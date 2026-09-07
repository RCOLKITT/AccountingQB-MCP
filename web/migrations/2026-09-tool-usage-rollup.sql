-- tool_usage retention + daily rollup (SPINE OPS: bound tool_usage growth).
--
-- WHY: tool_usage grows one row per tool call, unbounded. Worse, the hot reads
-- (api/cron/update-stats, api/usage/stats, api/admin/users/[key]) fetch every matching
-- raw row into Node and reduce in JS — and PostgREST caps a select() at ~1000 rows, so
-- all-time "calls"/"hours saved" are ALREADY silently undercounting once a scope crosses
-- 1000 rows (the prod table is already at ~1141). We cannot just prune old rows: lifetime
-- "hours saved" would shrink over time (never-mislead-numbers, Constitution).
--
-- FIX (two parts): (1) a PERMANENT daily rollup that preserves all-time per-license /
-- per-tool totals + per-day activity forever and lets reads aggregate server-side (fixing
-- the undercount); (2) a 90-day retention prune of raw rows, applied only after reads are
-- sourced from the rollup (see phased rollout in the PR).
--
-- This migration is ADDITIVE and safe to apply anytime (no data touched). The destructive
-- prune runs only when the rollup cron calls prune_tool_usage() — deliberately left OFF
-- until the read rewire is verified in production.
--
-- ONE-TIME BACKFILL after applying (rolls up ALL history; idempotent, safe to re-run):
--     select rollup_tool_usage(100000);
-- Verify faithfulness before anything depends on it:
--     select (select coalesce(sum(calls),0) from tool_usage_daily) as rollup_calls,
--            (select count(*) from tool_usage)                     as raw_calls;
--   -- rollup_calls must equal raw_calls (and per-license sums must match).

-- ---------------------------------------------------------------------------
-- Rollup table: one row per (license, tool, UTC day). realm_id is intentionally
-- dropped from the grain — no read groups by realm; raw keeps realm_id for the
-- 90-day forensic window.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool_usage_daily (
  license_key    TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  tool_name      TEXT NOT NULL,
  day            DATE NOT NULL,
  calls          INTEGER NOT NULL DEFAULT 0,
  minutes_saved  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (license_key, tool_name, day)
);

-- Prune + global-by-day scans.
CREATE INDEX IF NOT EXISTS idx_tool_usage_daily_day
  ON tool_usage_daily (day);
-- Per-license window scans (this-week/month, DAU/WAU/MAU, last-active).
CREATE INDEX IF NOT EXISTS idx_tool_usage_daily_license_day
  ON tool_usage_daily (license_key, day DESC);

-- Service-role-only, matching usage_stats_cache (no permissive policy = deny-by-default
-- for anon; every reader uses the service client, which bypasses RLS).
ALTER TABLE tool_usage_daily ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- rollup_tool_usage(lookback_days): idempotent RECOMPUTE of a bounded recent window.
-- Recomputing (not incrementing) means a missed cron run self-heals on the next run and
-- the UTC day boundary is handled correctly. Returns the number of daily rows written.
-- Aggregation stays in Postgres — raw rows are never shipped to the app.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rollup_tool_usage(lookback_days INTEGER DEFAULT 2)
RETURNS BIGINT
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  affected BIGINT;
BEGIN
  INSERT INTO tool_usage_daily (license_key, tool_name, day, calls, minutes_saved)
  SELECT
    license_key,
    tool_name,
    (invoked_at AT TIME ZONE 'UTC')::date AS day,
    count(*)                              AS calls,
    coalesce(sum(time_saved_minutes), 0)  AS minutes_saved
  FROM tool_usage
  WHERE invoked_at >= now() - make_interval(days => lookback_days)
  GROUP BY 1, 2, 3
  ON CONFLICT (license_key, tool_name, day)
  DO UPDATE SET
    calls         = EXCLUDED.calls,
    minutes_saved = EXCLUDED.minutes_saved;

  GET DIAGNOSTICS affected = ROW_COUNT;
  RETURN affected;
END;
$$;

-- ---------------------------------------------------------------------------
-- prune_tool_usage(retention_days): chunked delete of raw rows older than the window,
-- to avoid a long table lock. Returns total rows deleted. DESTRUCTIVE — only invoked once
-- the read rewire is live + verified (the rollup fully backstops the deleted rows).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION prune_tool_usage(retention_days INTEGER DEFAULT 90)
RETURNS BIGINT
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  cutoff    TIMESTAMPTZ := now() - make_interval(days => retention_days);
  chunk     BIGINT;
  total     BIGINT := 0;
BEGIN
  LOOP
    DELETE FROM tool_usage
    WHERE ctid IN (
      SELECT ctid FROM tool_usage WHERE invoked_at < cutoff LIMIT 10000
    );
    GET DIAGNOSTICS chunk = ROW_COUNT;
    total := total + chunk;
    EXIT WHEN chunk = 0;
  END LOOP;
  RETURN total;
END;
$$;

-- ---------------------------------------------------------------------------
-- Read-side aggregation RPCs. Every usage read aggregates server-side over the
-- rollup (bounded output: ≤#tools or ≤#licenses rows) instead of fetching raw rows
-- into Node — this is what fixes the PostgREST >1000-row undercount. p_keys NULL =
-- all licenses; p_since NULL = all time.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rollup_by_tool(p_keys TEXT[] DEFAULT NULL, p_since DATE DEFAULT NULL)
RETURNS TABLE(tool_name TEXT, calls BIGINT, minutes BIGINT, last_day DATE)
LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT tool_name, sum(calls)::bigint, sum(minutes_saved)::bigint, max(day)
  FROM tool_usage_daily
  WHERE (p_keys IS NULL OR license_key = ANY(p_keys))
    AND (p_since IS NULL OR day >= p_since)
  GROUP BY tool_name;
$$;

CREATE OR REPLACE FUNCTION rollup_by_license(p_keys TEXT[] DEFAULT NULL, p_since DATE DEFAULT NULL)
RETURNS TABLE(license_key TEXT, calls BIGINT, minutes BIGINT, distinct_tools BIGINT, last_day DATE)
LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT license_key, sum(calls)::bigint, sum(minutes_saved)::bigint,
         count(DISTINCT tool_name)::bigint, max(day)
  FROM tool_usage_daily
  WHERE (p_keys IS NULL OR license_key = ANY(p_keys))
    AND (p_since IS NULL OR day >= p_since)
  GROUP BY license_key;
$$;

-- Per-license engagement windows for DAU/WAU/MAU + at-risk (calendar-day grain).
CREATE OR REPLACE FUNCTION engagement_by_license(p_today DATE)
RETURNS TABLE(license_key TEXT, last_day DATE, calls_7d BIGINT, calls_prior BIGINT,
              active_1d BOOLEAN, active_7d BOOLEAN, active_30d BOOLEAN)
LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT license_key,
         max(day) AS last_day,
         coalesce(sum(calls) FILTER (WHERE day >= p_today - 6), 0)::bigint AS calls_7d,
         coalesce(sum(calls) FILTER (WHERE day >= p_today - 29 AND day < p_today - 6), 0)::bigint AS calls_prior,
         bool_or(day >= p_today)      AS active_1d,
         bool_or(day >= p_today - 6)  AS active_7d,
         bool_or(day >= p_today - 29) AS active_30d
  FROM tool_usage_daily
  WHERE day >= p_today - 29
  GROUP BY license_key;
$$;
