-- Taxpayer allocation profiles: per-realm, per-tax-year business-use percentages
-- (home-office %, vehicle %, per-account internet/phone %) plus their documented
-- basis/provenance. This is TAXPAYER data (inputs), deliberately stored OUTSIDE the
-- tax_ledger (which holds statutory facts only). Apply once, before deploying the
-- /api/allocations/profile endpoint. RLS is enabled with no policy = deny-by-default;
-- only the service role (server API routes) can read/write, same as oauth_tokens.

CREATE TABLE IF NOT EXISTS allocation_profiles (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  license_key  TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id     TEXT NOT NULL,
  tax_year     INT  NOT NULL,

  -- { home_office:{...}, vehicle:{...}, account_allocations:{...}, provenance:{...} }
  profile      JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),

  -- One profile per company per tax year
  UNIQUE(license_key, realm_id, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_allocation_profiles_license_key
  ON allocation_profiles (license_key);

ALTER TABLE allocation_profiles ENABLE ROW LEVEL SECURITY;

CREATE TRIGGER set_allocation_profiles_updated_at
  BEFORE UPDATE ON allocation_profiles
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
