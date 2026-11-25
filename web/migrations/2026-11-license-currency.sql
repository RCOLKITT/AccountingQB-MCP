-- Multi-currency revenue accuracy: store the billing CURRENCY alongside
-- billing_amount_cents so MRR is never computed by adding CAD cents to USD
-- cents. Backfilled from Stripe (subscription.currency) for existing paid
-- rows; the Stripe webhook writes it going forward. NULL = unknown/none yet;
-- readers treat NULL as 'usd' only for display fallback, never for summing
-- across currencies.
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS currency TEXT;
