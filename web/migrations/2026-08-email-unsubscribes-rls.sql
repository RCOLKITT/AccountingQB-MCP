-- Enable Row Level Security on email_unsubscribes (was the only table with RLS off).
-- Deny-by-default with no policy → service-role only, matching every other table
-- (oauth_tokens, tool_usage, etc.). The app writes/reads this table with the Supabase
-- service role (see /api/unsubscribe), which bypasses RLS, so access is unaffected;
-- this closes off anon-key read/write that the Supabase advisor flagged.

ALTER TABLE public.email_unsubscribes ENABLE ROW LEVEL SECURITY;
