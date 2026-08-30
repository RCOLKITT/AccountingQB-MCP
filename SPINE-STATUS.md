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
| 5 Autonomous response | 🟡 | Token single-flight (`claim_token_refresh`), `/healthz`, `_bootstrap_pairing` self-heal on boot | Stateless connector; **Gap G2:** no watchdog/sentinel alerting on failures |
| 6 Data | 🟡 | `web/supabase-schema.sql` mirror + dated `web/migrations/*`; RLS deny-by-default | **Gap G3:** no schema-drift-check command; **Gap G4:** no documented backup restore drill |
| 7 Intelligence | 🟡 | Read-only-only `/chat` loop (`_CHAT_ALLOW`), `/sample`, report narrative, campaign composer; never-fabricate (Constitution); `escapeHtml` render; untrusted-data tags on MCP results | Golden tax tests exist; **Gap G5:** no rerunnable eval for the chat/narrative AI |
| 8 Scheduling & ops | 🟡 VERIFY | `web/src/app/api/cron/*` (Vercel cron) | **Gap G6:** confirm UTC + add heartbeat + alert-on-silence + external dead-man switch |
| 9 Secrets & supply chain | 🟡 | Doppler (`accountingqb-mcp/prd`); `scripts/scan-secrets.sh` CI gate; `requirements.txt`, `web/package-lock.json` | **Gap G7:** no automated dependency audit |

## Gate status

| Gate | Status | Command | Notes |
|------|--------|---------|-------|
| Typecheck (web) | 🟢 | `cd web && npx tsc --noEmit` | **In CI (blocking)** — `web-checks` job |
| Typecheck (py) | N/A | — | Python; type hints present, no mypy gate (optional) |
| Lint | 🟡 | `ruff check` in CI (report-only) | Python ruff runs VISIBLE (~144 issues) — cleanup = **Gap G9**; ESLint not configured = **Gap G9** |
| Format | 🟢 | `prettier --check` (web) + `black --check` (py), both in CI | **BLOCKING** — G10 done: 139 web files reformatted + prettier gate in `web-checks`; 43 py files reformatted + `black --check` in the `pytest` job. |
| Tests (py) | 🟢 | `python3 -m pytest tests/ -q` | **412 pass**; in CI (`tests.yml`) |
| Tests (web) | 🔴 | (none) | **Gap G11:** no web unit/e2e suite |
| Secret scan | 🟢 | `bash scripts/scan-secrets.sh` | In CI; also blocks real QBO realm ids in tracked files |
| Theater scan | 🟢 | `bash scripts/scan-theater.sh` | **In CI (blocking)** — clean; demo mode + UI placeholders excluded with reasons |
| Branch protection | 🟢 | GitHub settings | `main` requires PR + **pytest, secret-scan, theater, web-checks**; admins keep emergency-merge |

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
(latest.json + beta prerelease lane). Remaining format/lint work: **G9** (ruff ~144 + ESLint).

## Declared gaps (with rough cost to close)

1. ~~**G1 flag registry**~~ — DONE: `docs/FLAGS.md`.
2. **G2 watchdog/alerting** — an independent check that alerts on connector/web failure (beyond
   `/healthz`). Ties to G6. *~1 day (needs a monitor + alert channel).*
3. **G3 schema-drift check** — a command that diffs `web/supabase-schema.sql` vs live Supabase and
   fails on drift. *~2-3h (Supabase introspection).*
4. **G4 backup restore drill** — perform one restore of the Supabase DB to a scratch project and
   write it up in RUNBOOK.md. *~2h.*
5. **G5 AI eval** — a rerunnable eval for the `/chat` loop + report narrative (golden Q→A over a
   fixed fixture; assert never-fabricate + no write-tool exposure). *~half day.*
6. **G6 cron heartbeat + dead-man** — confirm Vercel crons pin UTC; add a heartbeat row per run +
   an external dead-man switch (healthchecks.io). *~3-4h.*
7. **G7 dependency audit** — `pip-audit` now runs report-only in CI (`quality-report`); add `npm audit`
   and triage/document exceptions to make it blocking. *~2h remaining.*
8. ~~**G8 web typecheck in CI**~~ — DONE: `web-checks` job runs `tsc --noEmit` (blocking).
9. **G9 lint gate** — ruff runs report-only in CI (~144 issues to clear); ESLint (web) not yet
   configured. Fix the ruff findings + add ESLint, then make blocking. *~3-4h.*
10. ~~**G10 format gate**~~ — DONE: one-time `prettier --write` (139 web files) + `black` (43 py
    files), both now blocking in CI with pinned configs (prettier in `web-checks`, `black --check`
    in `pytest`).
11. **G11 web tests** — a starter Playwright e2e against the dashboard + a dedicated test license
    (top-3 riskiest paths: license verify, OAuth connect, checkout). *~1 day.*
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
