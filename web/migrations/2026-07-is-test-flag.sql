-- Internal/demo account flag so admin funnel + campaigns exclude non-real users.
-- Applied to production 2026-07-24.

ALTER TABLE licenses ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;

-- Backfill obvious internal/demo accounts. Real friends/family testers stay
-- is_test=false (they're genuine trials); flag them manually in admin if needed.
UPDATE licenses
SET is_test = true
WHERE email ILIKE '%@vasperacapital.com'
   OR key LIKE 'LK-DEMO-%'
   OR email ILIKE '%example.com';

CREATE INDEX IF NOT EXISTS idx_licenses_is_test ON licenses (is_test) WHERE NOT is_test;
