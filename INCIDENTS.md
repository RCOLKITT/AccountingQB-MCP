# INCIDENTS — AccountingQB

Post-mortem log. One entry per incident: timeline, blast radius, ALL root causes, what detected it,
what responded, and the **structural change that makes the CLASS impossible**. Corrections are new
entries; entries are not rewritten.

Seeded 2026-08-28 from evidence in git history + memory. Older incidents predating this log are
reconstructed from PRs/commits and marked *(reconstructed)*.

---

## 2026-08-27 · Coffer→AccountingQB booking failed: missing clearing account
- **What:** `qb_record_owner_paid_expense` booked `DR "Owner-Paid Expenses (review)" / CR "Owner's
  Equity"` but never ensured those accounts existed. NutriFitAI (a fresh company) had neither → the
  journal entry was refused and nothing booked. Would fail in **every** fresh QuickBooks company.
- **Blast radius:** the Coffer integration's write path for any first-use / fresh-company user. No
  data corruption (the write correctly refused).
- **Root causes:** (1) hardcoded account names with no ensure-create; (2) assumed a standard chart
  of accounts that fresh companies don't have.
- **Detected:** the Coffer side, during the maiden-voyage Send (attempt 4).
- **Responded:** `_int_owner_paid_expense` now ensure-creates the Expense clearing account and
  reuses an existing owner-equity account before creating one (PR #53).
- **Structural fix (kills the class):** the wrapper provisions its own booking accounts on first
  use; no integration write assumes chart-of-accounts contents.

## 2026-08-27 · `pytest` wiped a developer's live Coffer pairing
- **What:** `test_pair_and_unpair` drove the real `/pair` and `/unpair` routes, which persist to
  `~/.accountingqb/pairing.json` — so running the suite on a machine with a live pairing emptied it
  (whoami → paired:false until re-pulled).
- **Blast radius:** any developer running the full suite locally while paired; no prod impact.
- **Root cause:** the test used the real pairing-file path instead of an isolated tmp path.
- **Detected:** observed live — whoami flipped to false right after a full `pytest` run.
- **Responded:** the test monkeypatches `PAIRING_FILE` to a tmp path (PR #52).
- **Structural fix:** state-mutating route tests must isolate their on-disk paths (the other pairing
  tests already did; this one was the outlier).

## 2026-08-27 · Desktop shim came up unpaired after restart
- **What:** the Coffer pairing lived only in the local `~/.accountingqb/pairing.json` cache; a
  restart / fresh install / stray unpair emptied it, so `whoami` reported `paired:false` while the
  web (`account_links`, keyed by license) still held the link. Coffer then fired a Send into an
  inert peer and nothing booked.
- **Blast radius:** any restart of a paired desktop shim.
- **Root causes:** (1) the local file was treated as the source of truth; (2) boot restored QB
  tokens (`_bootstrap_profile`) but not the pairing.
- **Detected:** the Coffer side, on a post-restart Send.
- **Responded:** `_bootstrap_pairing()` re-pulls the pairing from `/api/link/status` on every boot
  (PR #51). Immediate unblock: `POST /link/refresh`.
- **Structural fix:** the web is the source of truth; the shim restores from it on boot, so a restart
  can never come up inert while the account is linked.

## 2026-07 · tool_usage empty in production *(reconstructed)*
- **What:** tool-usage telemetry was empty in prod because the MCP server's usage POSTs were bounced
  to sign-in by Clerk middleware (the endpoint authenticates by license key in the body, not a
  session).
- **Root cause:** `/api/usage(.*)` was not in the middleware public-route allowlist.
- **Responded:** added `/api/usage(.*)` to `isPublicRoute` (fixed v3.5.2).
- **Structural fix:** API routes that authenticate by license-key-in-body are explicitly listed as
  public in `middleware.ts` with a comment; new such routes follow the pattern.

## 2026-06/07 · MCP version + transport landmines *(reconstructed)*
- **What:** two build-time landmines that crash the connector: `mcp` 2.0.0 removed
  `mcp.server.fastmcp` (must stay `<2.0.0`), and transport allowed-hosts must be explicit (1.29's
  default 421s the prod host).
- **Structural fix:** `mcp[cli]>=1.0.0,<2.0.0` pinned in `requirements.txt`/`pyproject.toml` with a
  comment; allowed-hosts set explicitly. Captured in memory `accountingqb-mcp-version-landmines`.

---

_Add new incidents at the top. If you fixed a class of bug, the entry isn't done until the
"structural fix" line names why the class can't recur._
