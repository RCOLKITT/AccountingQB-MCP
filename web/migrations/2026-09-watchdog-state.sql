-- Watchdog state (VASPERA-SPINE G2: alert on connector/web failure beyond /healthz).
--
-- One row per monitored check. The /api/cron/watchdog job probes each target every
-- few minutes and uses this table to alert only on STATE TRANSITIONS (healthy→down
-- after N consecutive failures, a periodic re-alert while still down, and a recovery
-- notice) — so a paging email fires on real outages, not every tick. Service-role
-- only (matches usage_stats_cache).

CREATE TABLE IF NOT EXISTS watchdog_state (
  check_name           TEXT PRIMARY KEY,
  healthy              BOOLEAN NOT NULL DEFAULT true,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  last_status          TEXT,
  last_change          TIMESTAMPTZ DEFAULT now(),
  last_alert_at        TIMESTAMPTZ,
  updated_at           TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE watchdog_state ENABLE ROW LEVEL SECURITY;
