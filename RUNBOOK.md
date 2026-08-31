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
  `main` is branch-protected; never push directly. Verify live after: `curl -s https://accountingqb.com/api/health`.
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
- **Restore drill:** NOT YET PERFORMED — see SPINE-STATUS.md gap G4. Supabase has managed backups;
  a documented restore-to-scratch drill is owed.

## Desktop shim (local, "Door 2")
- Run from source: `ACCOUNTINGQB_PORT=4318 python accountingqb-local/serve.py` (binds 127.0.0.1 only).
- On boot it: loads the saved license → hosted QuickBooks company (`_bootstrap_profile`), and
  re-pulls the Coffer pairing from the web (`_bootstrap_pairing`, survives restarts).
- **Pairing lost after restart:** `curl -X POST 127.0.0.1:4318/link/refresh` re-pulls it from the
  web (the source of truth is `account_links`, keyed by license). See INCIDENTS.md #1.

## "It's down at 3am"
1. `curl -s https://accountingqb.com/api/health` and the Fly connector's health.
2. Vercel dashboard → latest deployment status + runtime logs; Fly `fly logs`.
3. Supabase → project health + `get_advisors`.
4. If a bad deploy: roll back (above). If a data issue: check `event_logs` for the failing action.
5. QuickBooks-side errors surface as QBO Fault code+message in tool responses — check the realm's
   QBO status page for Intuit outages.

## Gates (run before merge)
`python3 -m pytest tests/ -q` · `cd web && npx tsc --noEmit` · `bash scripts/scan-secrets.sh`.
CI runs pytest + secret-scan on every PR (web tsc gate is a pending gap, G8).
