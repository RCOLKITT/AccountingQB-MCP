# RUNBOOK — AccountingQB

Operational procedures. Keep truthful; if a step here doesn't match reality, fix the step.

## Surfaces & where they run
- **Web** (`web/`) — Next.js on **Vercel** (project under the `nutrifitai` team). Deploys on
  merge to `main`. DNS under vaspera-shield.
- **Remote MCP connector** (`mcpb/src/accountingqb/remote.py`) — **Fly** (personal app).
- **PyPI package** (`accountingqb`) — the local/self-hosted MCP server.
- **Desktop app** (`accountingqb-desktop-tauri` + `accountingqb-local`) — signed installers
  published to GitHub Releases via `.github/workflows/release-desktop.yml` (macOS notarized DMG,
  Windows Azure-signed).
- **DB** — Supabase project `zwtejghmhwnwsclliqur` (commercial plane only: licenses, oauth_tokens,
  event_logs, app_downloads, account_links, link_codes, tool_usage — never books data).

## Deploy
- **Web:** open a PR → green pytest + secret-scan → squash-merge to `main` → Vercel auto-deploys.
  `main` is branch-protected; never push directly. Verify live after: `curl -sI https://accountingqb.com/`
  returns 200 (there is no `/api/health` route; the watchdog probes the site root + connector `/healthz`).
- **Desktop release (deliberate, not per-merge):** bump the version in
  `accountingqb-desktop-tauri/src-tauri/tauri.conf.json` + `src-tauri/Cargo.toml` + `package.json`,
  add a `## X.Y.Z — <date>` entry to `CHANGELOG.md` (the in-app "What's new"). **Validate first:**
  tag `desktop-vX.Y.Z-beta.N` → published as a GitHub *prerelease* the auto-updater ignores; install
  + validate by hand. Then tag `desktop-vX.Y.Z` (stable) → CI builds/signs/notarizes, signs the
  updater artifacts, assembles `latest.json`, and publishes. Installed apps auto-update from
  `latest.json` on next launch. Signing secrets: Apple (6) + Azure (6) + updater (2,
  `TAURI_SIGNING_PRIVATE_KEY[_PASSWORD]`) in Doppler + mirrored to GitHub Actions secrets. See
  `accountingqb-desktop-tauri/SIGNING.md`.
- **PyPI:** version bump + changelog; publish token is `UV_PUBLISH_TOKEN` in Doppler.

## Rollback
- **Web:** in Vercel, promote the previous good deployment (Deployments → ⋯ → Promote to Production).
  Or `git revert <sha>` → PR → merge.
- **Desktop:** a bad release also auto-updates users, so act fast — delete/mark the bad GitHub
  Release (so `releases/latest` falls back to the prior good one, which restores `latest.json`), then
  cut a fixed `desktop-vX.Y.(Z+1)`. Downloads auto-resolve to `latest`. Never delete the signing key.
- **DB migration gone wrong:** migrations are forward-only; write a new compensating migration in
  `web/migrations/` and apply. Never edit a shipped migration.

## Secrets (Doppler)
Project `accountingqb-mcp`, config `prd`. Never commit or log. Pipe to GitHub without echoing:
`doppler secrets get NAME --plain --project accountingqb-mcp --config prd | gh secret set NAME`.
Rotation: rotate in Doppler → it flows to Vercel/Fly at next deploy/run.

## Database / migrations
- Source of truth: `web/supabase-schema.sql` (mirror of live). Changes ship as dated
  `web/migrations/YYYY-MM-*.sql`, applied to prod **before** the code that needs them deploys
  (apply via the Supabase MCP `apply_migration` / SQL editor).
- **Disaster recovery + restore drill:** see the **Disaster recovery (DB)** section below.

## Disaster recovery (DB)

**Scope.** Supabase project `zwtejghmhwnwsclliqur` is the only stateful system of record
(licenses, encrypted `oauth_tokens`, `user_profiles`/`user_licenses`, `tool_usage` +
`tool_usage_daily`, `event_logs`, `app_downloads`, `support_*`, `watchdog_state`). **Books data
is never here** — it lives in QuickBooks Online (Constitution data-locality) — so DR covers the
commercial plane only. Upstash Redis (rate limits) is ephemeral; the Fly connector, PyPI package,
and desktop app are stateless / rebuildable from source + signing keys.

**⚠️ The encryption key is part of the backup.** `oauth_tokens.access_token/refresh_token` are
AES-256-GCM encrypted with `TOKEN_ENCRYPTION_KEY` (Doppler `prd`). A perfect DB restore is
**useless if that key is lost** — every token becomes undecryptable and all QuickBooks connections
break, with no recovery. Treat it as **tier-0**: keep an offline copy, and never rotate it without
re-encrypting existing rows first (decrypt-with-old → encrypt-with-new). All currently-connected
companies' tokens are encrypted with the live key.

**Backups — verify the tier.** Supabase managed backups; check Dashboard → project
`qb-mcp-licenses` → **Settings → Database → Backups**:
- **Daily backups** → RPO up to ~24h (a day of licenses/tokens/usage lost in a disaster).
- **PITR** (add-on) → RPO of seconds; restore to any timestamp in the retention window.
  **Recommended** for a financial-records product — enable if currently daily-only.

RTO/RPO **actuals are unmeasured** until the drill below runs.

**Recovery scenarios**
1. **Bad migration / data corruption (most common).** Migrations are forward-only — first prefer a
   compensating forward migration (see Rollback). If data was destroyed: with PITR, restore to a
   timestamp just before the change; without PITR, restore last night's backup (accept ≤24h loss)
   or restore into a scratch project and copy the affected rows back.
2. **Full project loss.** Restore the latest backup into a NEW Supabase project, then repoint the
   app: update `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (+ `NEXT_PUBLIC_SUPABASE_*`) in Doppler
   `prd` → redeploy Vercel + restart Fly. `TOKEN_ENCRYPTION_KEY` is unchanged, so restored tokens
   decrypt normally.

**Restore drill (owed — SPINE G4, NOT YET PERFORMED).** Proves the backup actually restores and
measures RTO/RPO, without touching prod:
1. Create a throwaway Supabase project (scratch).
2. Restore the latest prod backup into it (Dashboard restore, or `pg_restore` from a downloaded
   backup / `supabase db dump`).
3. **Verify:** row counts match prod for `licenses`, `oauth_tokens`, `user_licenses`, `tool_usage`;
   `schema_snapshot()` on the scratch DB matches `web/schema-snapshot.json`; set
   `TOKEN_ENCRYPTION_KEY` in a scratch env and confirm one `oauth_tokens` row round-trip **decrypts**
   (proves key + data + restore all line up).
4. Record wall-clock recovery time (**RTO**) and the restored backup's age (**RPO**) here.
5. Delete the scratch project.

Cost: a scratch project (and the PITR add-on, if testing PITR) — needs owner sign-off. **Until this
is performed, treat the backups as UNVERIFIED** (a backup you have never restored is a hope, not a
guarantee).

## Desktop shim (local, "Door 2")
- Run from source: `ACCOUNTINGQB_PORT=4318 python accountingqb-local/serve.py` (binds 127.0.0.1 only).
- On boot it: loads the saved license → hosted QuickBooks company (`_bootstrap_profile`), and
  re-pulls the Coffer pairing from the web (`_bootstrap_pairing`, survives restarts).
- **Pairing lost after restart:** `curl -X POST 127.0.0.1:4318/link/refresh` re-pulls it from the
  web (the source of truth is `account_links`, keyed by license). See INCIDENTS.md #1.

## "It's down at 3am"
1. `curl -sI https://accountingqb.com/` (expect 200) and the connector `curl -s https://mcp.accountingqb.com/healthz` (expect `ok`). The watchdog already emails on either being down — check inbox / `watchdog_state`.
2. Vercel dashboard → latest deployment status + runtime logs; Fly `fly logs`.
3. Supabase → project health + `get_advisors`.
4. If a bad deploy: roll back (above). If a data issue: check `event_logs` for the failing action.
5. QuickBooks-side errors surface as QBO Fault code+message in tool responses — check the realm's
   QBO status page for Intuit outages.

## Gates (run before merge)
Local: `python3 -m pytest tests/ -q` · `cd web && npx tsc --noEmit && npm run test:unit` ·
`bash scripts/scan-secrets.sh`. CI enforces six **required** checks on every PR to `main`:
**pytest, secret-scan, theater, web-checks** (tsc + prettier + ESLint + vitest + npm audit),
**web-e2e** (Playwright on a real build), and **schema-drift** (live DB vs committed snapshot).
