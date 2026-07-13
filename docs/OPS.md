# Operational Notes

## Deadlines / time-sensitive

- **Aug 31, 2026 — Intuit Reports API modernization cutover.** All report
  responses (P&L, balance sheet, TaxSummary, agings, GL) will be served by
  the modernized service. Re-run the report tools against a US and a CA
  sandbox before that date and fix any parsing drift.
  - Test v2 today: run the server with `QB_REPORTS_V2_TEST=1` — report
    requests are routed through the modernized service via Intuit's
    temporary `_testing_migration` parameter.
  - **BudgetVsActual is NOT among the 29 reports v2 supports** and will
    stop working at cutover. `qb_budget_vs_actual` already falls back to
    a manual Budget-query + P&L comparison, so it degrades gracefully;
    consider making the fallback the primary path before Aug 31.
  - v2 response drift to watch for: empty values return "" (not 0),
    row ordering changes, child accounts always nest under parents,
    ColTitle is Title Case, StartPeriod/EndPeriod always present,
    summarize_column_by=Days capped at 200 columns.
  - Minorversions 1–74 were retired Aug 1, 2025; everything serves v75
    semantics regardless of the parameter.

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
- **Tax data control plane** (as of 2026-07-13): every jurisdictional tax
  value lives in `mcpb/src/accountingqb/tax_tables.py` (the L2 registry —
  per-table source, verified date, review cadence, sanity bounds) with an
  append-only hash-chained history in `tax_ledger.jsonl` (L4). Policy
  tests in `tests/test_tax_data_policy.py` (L3) gate every commit via CI:
  the freshness tripwire fails every Jan 1 until the new year's tables
  load; changed values without a ledger row fail; the chain must verify.
  A monthly scheduled agent (L1) researches drift and opens draft PRs —
  it never merges; human PR approval is the gate. Users see provenance
  via the footer on every tax tool and `qb_tax_data_info`.
  To update a value: edit tax_tables.py, append a ledger row (new row
  with `supersedes:` — never edit lines), bump TAX_DATA_VERSION, update
  pinned tests, PR.

## Pricing (CAD)

- The three live Stripe prices carry `currency_options.cad` (CA$49/129/399,
  added 2026-07-11). Canadian-IP visitors geo-default to CAD at checkout
  (`x-vercel-ip-country`), and `/canada` links pass `?currency=cad`
  explicitly; `?currency=usd` opts out. If prices are ever recreated,
  re-add the CAD options or CAD checkouts will 500.
