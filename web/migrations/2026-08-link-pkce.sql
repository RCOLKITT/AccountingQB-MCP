-- OAuth-style ("Connect with…") account linking: PKCE binds a link code to the
-- browser session that started the authorize flow, so redeem no longer needs the
-- same-email identity match. A code carrying a code_challenge is redeemed by
-- presenting the matching code_verifier (S256); legacy codes (no challenge) keep
-- the identity-hash path. redirect_uri is recorded for audit + exact-match return.
ALTER TABLE link_codes ADD COLUMN IF NOT EXISTS code_challenge TEXT;
ALTER TABLE link_codes ADD COLUMN IF NOT EXISTS redirect_uri   TEXT;
