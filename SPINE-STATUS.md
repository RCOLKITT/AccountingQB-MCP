# Spine Status — AccountingQB — 2026-08-28
Spec version: 2026-08-26 (v1) · see VASPERA-SPINE.md · Constitution wins on conflicts (§7)

Repo type: hybrid — MCP server (`mcpb/`) + Next.js/Vercel app (`web/`) + remote connector +
Tauri desktop (`accountingqb-local/`, `accountingqb-desktop-tauri/`) + Claude plugin (`cowork-plugin/`).

This is a **Phase-0 audit** — an honest snapshot, not a claim of completion. Declared gaps below
are real work, each with a rough cost to close. Some rows are marked **VERIFY** where the state is
inferred from code and needs a live check (that check is itself the gap).

## Layers inventory

| Layer | Present? | Evidence | Notes / gaps |
|-------|----------|----------|--------------|
| 1 Presentation | ✅ | `web/src/app/*`, `accountingqb-local/artifact.html`, `cowork-plugin/skills/*`, README | Marketing, dashboard, admin, desktop app, 5 plugin skills |
| 2 API | ✅ | `web/src/app/api/*`, `web/src/middleware.ts` (isPublicRoute), MCP tools | Public routes are explicitly listed + commented; license/JWT gated elsewhere |
| 3 Domain/execution | ✅ | `mcpb/src/accountingqb/server.py` (131 tools), `tax_tables.py`, `remote.py`, `accountingqb-local/serve.py` | The real work; one canonical server |
| 4 Governance/policy | ✅ | Upstash rate limiters (`web/src/lib/ratelimit.ts`), region gating (`_get_region`/`require_region`), license gating, write confirm-gate (`_is_write_tool`) | Flag registry now at **`docs/FLAGS.md`** (G1 closed) |
| 5 Autonomous response | 🟡 | Token single-flight (`claim_token_refresh`), `/healthz`, `_bootstrap_pairing` self-heal on boot; **email watchdog** (`api/cron/watchdog` → connector + site, G2 mostly done) | Stateless connector; **Gap G2 remainder:** external dead-man for a full web-platform outage |
| 6 Data | 🟡 | `web/supabase-schema.sql` mirror + dated `web/migrations/*`; RLS deny-by-default; **schema-drift check** (`scripts/check-schema-drift.mjs`, G3 closed, report-only in CI) | **Gap G4:** no documented backup restore drill |
| 7 Intelligence | 🟡 | Read-only-only `/chat` loop (`_CHAT_ALLOW`), `/sample`, report narrative, campaign composer; never-fabricate (Constitution); `escapeHtml` render; untrusted-data tags on MCP results | Golden tax tests exist; **Gap G5:** no rerunnable eval for the chat/narrative AI |
| 8 Scheduling & ops | 🟡 VERIFY | `web/src/app/api/cron/*` (Vercel cron) | **Gap G6:** confirm UTC + add heartbeat + alert-on-silence + external dead-man switch |
| 9 Secrets & supply chain | 🟡 | Doppler (`accountingqb-mcp/prd`); `scripts/scan-secrets.sh` CI gate; `requirements.txt`, `web/package-lock.json` | **Gap G7:** no automated dependency audit |

## Gate status

| Gate | Status | Command | Notes |
|------|--------|---------|-------|
| Typecheck (web) | 🟢 | `cd web && npx tsc --noEmit` | **In CI (blocking)** — `web-checks` job |
| Typecheck (py) | N/A | — | Python; type hints present, no mypy gate (optional) |
| Lint | 🟢 | `ruff check` (py) + `npm run lint` (web), both BLOCKING | Python ruff F+I; web ESLint errors-only (compiler-era rules are visible warnings — G9 backlog). |
| Format | 🟢 | `prettier --check` (web) + `black --check` (py), both in CI | **BLOCKING** — G10 done: 139 web files reformatted + prettier gate in `web-checks`; 43 py files reformatted + `black --check` in the `pytest` job. |
| Tests (py) | 🟢 | `python3 -m pytest tests/ -q` | **412 pass**; in CI (`tests.yml`) |
| Tests (web) | 🟢 | `cd web && npm run test:e2e` (Playwright) | Public-route smoke + **auth-boundary** (protected API/admin routes reject anon; no anon writes) + **authed happy-path** (a real signed-in Clerk user renders the dashboard) on a real prod build; in CI (`web-e2e`, required). Authed spec uses a Clerk **dev-instance** `+clerk_test` user via `@clerk/testing` (creds: Doppler → GitHub secrets); it skips cleanly when creds are absent (fork PRs), never touches the `pk_live_` prod instance. |
| Secret scan | 🟢 | `bash scripts/scan-secrets.sh` | In CI; also blocks real QBO realm ids in tracked files |
| Theater scan | 🟢 | `bash scripts/scan-theater.sh` | **In CI (blocking)** — clean; demo mode + UI placeholders excluded with reasons |
| Branch protection | 🟢 | GitHub settings | `main` requires PR + **pytest, secret-scan, theater, web-checks, web-e2e**; admins keep emergency-merge |

## Progress (Phase 1, 2026-08-28)
Closed: **G1** (docs/FLAGS.md), **G8** (web tsc in CI, blocking), **G12** (theater gate in CI,
blocking). Installed report-only (VISIBLE, not yet blocking — real counts): prettier (~137 web
files), ruff (~144), pip-audit — **G7/G9/G10** cleanup remains. Enforcement added: `main` now also
requires `theater` + `web-checks`. (Correction: an earlier note claimed prettier was clean — a bad
grep; the real run finds 137 files. Fixed here per ZERO THEATER.)

## Progress (Phase 2, 2026-08-30)
Closed **G10** (format gate blocking): one-time `prettier --write` (139 web files) + `black`
(43 py files), then flipped both to blocking — prettier in `web-checks`, `black --check` in the
`pytest` job, each with a pinned config (`.prettierrc.json`, `[tool.black]`). Also shipped desktop
**auto-update** (Tauri v2 updater, signed, + in-app What's new) and its **signed release pipeline**
(latest.json + beta prerelease lane). **G9 python half**: ruff curated to correctness (F+I) and made
blocking — the gate immediately paid for itself, catching a real `NameError` (`acct_list` undefined
in the create-bill success message, F821) plus several dead fetches/assignments. Remaining: **G9
ESLint** (web; `next lint` is deprecated → needs migration to the ESLint CLI, its own decision).

## Progress (Phase 3, 2026-09-07)
**G9 ESLint** (web) closed and blocking (`npm run lint` in `web-checks`) — caught + fixed a real
conditional-hooks bug (SupportWidget) and 2 unescaped entities; compiler-era rules left VISIBLE as
warnings. **G7** closed (`npm audit --audit-level=high` blocking). **G11** advanced to the
authenticated happy-path: `@clerk/testing` global setup fetches a Testing Token once (guarded — a
no-op without creds), and `dashboard.auth.spec.ts` signs in a real Clerk **dev-instance**
`+clerk_test` user (email_code magic-code strategy — no password provisioning) and asserts the
signed-in dashboard renders. Dev-instance Clerk + Supabase creds flow Doppler (`accountingqb-mcp/dev`)
→ GitHub Actions secrets; the `web-e2e` job injects them with dummy-key fallbacks so fork PRs (no
secret access) skip the authed spec and still run smoke + auth-boundary. Never uses the `pk_live_`
prod instance; creates no book data. Verified locally: 24/24 pass with creds, authed spec skips
cleanly without them. Pre-scale: `tool_usage` composite index `(license_key, invoked_at DESC)`
shipped (#89); retention/rollup window remains an owner decision (OPS).

## Progress (Phase 4, 2026-09-07)
Closed the deferred **tool_usage retention** decision (was flagged in OPS as owner-gated). Policy:
**90-day raw retention + a permanent daily rollup** (`tool_usage_daily`, grain license×tool×UTC-day).
Shipped: the rollup table + `rollup_tool_usage()`/`prune_tool_usage()` + 3 read RPCs
(`rollup_by_tool`, `rollup_by_license`, `engagement_by_license`), applied to the live DB and
backfilled (verified rollup SUM == raw at every license/tool grain). A 15-min `rollup-usage` cron
keeps it fresh; **all six usage reads** (update-stats, usage/stats, admin/users[/key], engagement,
usage-analytics) now aggregate server-side over the rollup — which also **fixed a live correctness
bug**: those reads full-fetched raw rows and silently capped at PostgREST's ~1000 rows, undercounting
all-time calls/hours (prod was already at ~1141 rows). Prune is gated OFF (`TOOL_USAGE_PRUNE_ENABLED`)
until the read rewire is verified in prod, then it's a config flip — no rows are >90d old yet anyway.

## Declared gaps (with rough cost to close)

1. ~~**G1 flag registry**~~ — DONE: `docs/FLAGS.md`.
2. **G2 watchdog/alerting** — MOSTLY DONE: `/api/cron/watchdog` (every 5 min) probes the connector
   `/healthz` + marketing site and emails `WATCHDOG_ALERT_EMAIL` on DOWN (after 2 consecutive
   fails), re-alerts ≤6h while down, and on RECOVERED — transition-based, no per-tick spam
   (`watchdog_state` table). REMAINING: an EXTERNAL dead-man switch (e.g. healthchecks.io) to catch
   a full Vercel/platform outage of the web app itself — a Vercel-hosted watchdog can't self-report
   that. Ties to **G6**. *~1-2h once a dead-man provider is chosen.*
3. ~~**G3 schema-drift check**~~ — DONE (report-only): `web/scripts/check-schema-drift.mjs` diffs the
   LIVE public schema (columns + indexes, via the `schema_snapshot()` RPC — service-role, no DB
   password) against the committed `web/schema-snapshot.json`; `--update` regenerates it after an
   intentional change. CI `schema-drift` job runs it with the existing Supabase secrets, VISIBLE but
   `continue-on-error: true` for now — flip to blocking once trusted. Skips cleanly when creds absent.
4. **G4 backup restore drill** — perform one restore of the Supabase DB to a scratch project and
   write it up in RUNBOOK.md. *~2h.*
5. **G5 AI eval** — a rerunnable eval for the `/chat` loop + report narrative (golden Q→A over a
   fixed fixture; assert never-fabricate + no write-tool exposure). *~half day.*
6. **G6 cron heartbeat + dead-man** — confirm Vercel crons pin UTC; add a heartbeat row per run +
   an external dead-man switch (healthchecks.io). *~3-4h.*
7. ~~**G7 dependency audit**~~ — DONE: `npm audit --audit-level=high` is BLOCKING in `web-checks` (0 vulnerabilities after the Next.js 16 upgrade cleared the sharp/libvips highs + `npm audit fix` cleared the rest). `pip-audit` (python) remains report-only.
8. ~~**G8 web typecheck in CI**~~ — DONE: `web-checks` job runs `tsc --noEmit` (blocking).
9. **G9 lint gate** — PYTHON DONE (ruff F+I blocking). WEB: ESLint (flat config) now BLOCKING in `web-checks` (`npm run lint`) — errors only. It caught + fixed a real conditional-hooks bug (SupportWidget) and 2 unescaped entities. The React-19.2 compiler-era rules (immutability, purity, set-state-in-effect, exhaustive-deps — 64 warnings) are VISIBLE but non-blocking; clearing them is the remaining G9 backlog, best done under the new web e2e suite (G11). *~half day under e2e cover.*
10. ~~**G10 format gate**~~ — DONE: one-time `prettier --write` (139 web files) + `black` (43 py
    files), both now blocking in CI with pinned configs (prettier in `web-checks`, `black --check`
    in `pytest`).
11. **G11 web tests** — LARGELY DONE: a Playwright suite (`web/tests/e2e/`) runs on a real
    `next build` + `next start` in CI (`web-e2e` job, required) — every public route returns <400
    with real content, plus security headers, robots/sitemap, the download redirect, the
    auth-boundary net (protected API/admin routes reject anon; no anon writes), and now the
    **authenticated happy-path** (a real signed-in Clerk `+clerk_test` user renders the dashboard,
    via `@clerk/testing` global setup + Testing Token; dev-instance creds Doppler→GitHub secrets;
    guarded to skip on fork PRs). The build itself is a regression check. REMAINING (thinner):
    deeper authed flows — license verify with a seeded `is_test` license, OAuth connect, checkout.
    *~2-3h.*
12. ~~**G12 theater-scan gate**~~ — DONE: `scripts/scan-theater.sh` in CI (blocking), clean.

**Not a gap (already strong):** the Constitution's Product Laws (workpapers-not-filings, region
gating, sourced rate tables, write-safety, data-locality tiers), the `event_logs` audit trail,
golden tax-math tests, offline respx tests, encrypted+rotated token handling, the secret-scan gate,
and now branch protection.

## History note
This audit was created after a run of production incidents were fixed live (see INCIDENTS.md):
pairing persistence (#51), a test wiping live pairing (#52), missing booking accounts in fresh
companies (#53), and a rate-limiter question — each a real bug that would have hit a paying user.
The gaps above are the next layer of "make the claim true."
