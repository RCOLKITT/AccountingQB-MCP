# Operational Notes

## Deadlines / time-sensitive

- **Aug 31, 2026 — Intuit Reports API modernization cutover.** All report
  responses (P&L, balance sheet, TaxSummary, agings, GL) will be served by
  the modernized service. Re-run the report tools against a US and a CA
  sandbox before that date and fix any parsing drift.

## Recurring maintenance

- **OAuth sweeps:** purge expired rows from `mcp_oauth_codes` (10-min codes)
  and `mcp_refresh_tokens` (90-day, revoked chains) — add a weekly Vercel
  cron or Supabase scheduled function.
- **CRON_SECRET** must be set in Vercel; the cron routes skip auth entirely
  when it's unset. All three crons (process-emails, check-trials,
  update-stats) require middleware to keep `/api/cron(.*)` public.
- **Email backlog:** stale pre-July-2026 scheduled emails were bulk-cancelled
  on 2026-07-09. If the cron ever 404s/dies again, cancel overdue rows
  before re-enabling (`update email_schedules set cancelled=true where
  sent_at is null and cancelled=false and scheduled_for < now()`).

## Environment variables (beyond .env.example basics)

- Vercel: MCP_JWT_SECRET, MCP_RESOURCE_URL, NEXT_PUBLIC_REMOTE_MCP_URL,
  RESEND_API_KEY, UPSTASH_REDIS_REST_URL/TOKEN, CRON_SECRET,
  CLERK_WEBHOOK_SECRET, NEXT_PUBLIC_BASE_URL / NEXT_PUBLIC_SITE_URL.
- Fly (remote service): MCP_JWT_SECRET (identical to Vercel's), QB_API_URL.

## Canada

- Intuit app must whitelist Canada under "countries you accept connections
  from"; keep a CA sandbox company connected to a test license for the
  qb_gst_hst_return / tax-code regression matrix in tests/test_ca_suite.py.
- CA rate tables live as constants in mcpb/src/accountingqb/server.py
  (CPP YMPE/YAMPE, CCA ceilings, CRA km rates) — review annually (December
  CRA announcements).
