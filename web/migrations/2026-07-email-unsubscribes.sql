-- Marketing suppression list (CAN-SPAM / CASL). Transactional email ignores
-- this; only campaigns/marketing check it. Applied to production 2026-07-24.

CREATE TABLE IF NOT EXISTS email_unsubscribes (
  email           TEXT PRIMARY KEY,
  scope           TEXT NOT NULL DEFAULT 'marketing',  -- marketing | all
  reason          TEXT,
  source          TEXT,                                -- 'link' | 'admin' | 'bounce'
  unsubscribed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
