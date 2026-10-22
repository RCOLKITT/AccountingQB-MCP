-- Legal acceptances: a first-party consent ledger for Terms of Service / Privacy
-- Policy clickwrap. Paid checkout already records affirmative ToS consent inside
-- Stripe (consent_collection); this table unifies that with the no-credit-card
-- trial/download path (which previously captured only the email lead) so every
-- acceptance — who, which document, which VERSION, when, from where — is held
-- first-party and auditable. One row per (email, document) acceptance event;
-- re-acceptances (new policy version) append new rows, never overwrite.
-- Service-role only (writes come from server routes using the service key;
-- matches watchdog_state / usage_stats_cache).

CREATE TABLE IF NOT EXISTS legal_acceptances (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email        TEXT NOT NULL,
  clerk_id     TEXT,                     -- when the acceptor is a signed-in user
  document     TEXT NOT NULL CHECK (document IN ('tos', 'privacy')),
  version      TEXT NOT NULL,            -- POLICY_VERSION at time of acceptance
  accepted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  ip           TEXT,
  user_agent   TEXT,
  context      TEXT,                     -- 'checkout' | 'trial_download' | ...
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legal_acceptances_email_idx
  ON legal_acceptances (email, document);

ALTER TABLE legal_acceptances ENABLE ROW LEVEL SECURITY;
