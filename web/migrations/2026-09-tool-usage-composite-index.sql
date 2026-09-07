-- Pre-scale hardening (SPINE admin-perf follow-up).
--
-- tool_usage grows unbounded with adoption. The two hottest reads —
--   • admin "last active per license"  (WHERE license_key IN (...) ORDER BY invoked_at DESC)
--   • usage stats                       (WHERE license_key = ... AND invoked_at >= ...)
-- both filter by license_key AND order/range by invoked_at. The current single-column
-- indexes (license_key) and (invoked_at DESC) each serve only half of that; a composite
-- (license_key, invoked_at DESC) serves the whole access pattern and lets Postgres walk
-- the newest rows per license without a wide scan.
--
-- Non-breaking: purely additive, IF NOT EXISTS, no code depends on it. Safe to apply
-- before or after a deploy. It makes idx_tool_usage_license_key redundant (the composite
-- covers the license_key prefix) — left in place to keep this migration risk-free; drop
-- it in a later cleanup if desired.
--
-- NOT addressed here (deliberately — an owner decision): a RETENTION / ROLLUP policy to
-- bound raw-row growth (e.g. roll old rows into a monthly aggregate + prune, or a
-- time-window delete). That changes what "all-time" stats mean, so it needs a chosen
-- window — see private-docs/OPS.md.

CREATE INDEX IF NOT EXISTS idx_tool_usage_license_invoked
  ON tool_usage (license_key, invoked_at DESC);
