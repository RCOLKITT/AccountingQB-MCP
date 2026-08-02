-- Monthly MRR-by-account snapshots. Current subscription state is all we store
-- today, so Net Revenue Retention / expansion / MRR-over-time were not
-- computable. This captures one row per paying license per month (real billed
-- MRR from Stripe, annual normalized to monthly), which the admin Revenue page
-- reads to compute NRR/GRR and the MRR trend.

CREATE TABLE IF NOT EXISTS mrr_snapshots (
  month        TEXT NOT NULL,             -- 'YYYY-MM' (the snapshot period)
  license_key  TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  mrr_cents    INTEGER NOT NULL,          -- normalized monthly recurring revenue
  tier         TEXT,
  status       TEXT,
  captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (month, license_key)
);

CREATE INDEX IF NOT EXISTS idx_mrr_snapshots_month ON mrr_snapshots(month);

-- Server-role only (all admin reads go through the service key, bypassing RLS).
ALTER TABLE mrr_snapshots ENABLE ROW LEVEL SECURITY;
