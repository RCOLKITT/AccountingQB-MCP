# Flag & Gate Registry (VASPERA-SPINE §2 layer 4, gap G1)

Every governance/policy control: name → designed state → where enforced → owner. If a control's
real behavior drifts from its designed state, that's a bug — fix the code or update this row.

## Safety gates (block on violation)
| Control | Designed state | Enforced in | Owner |
|---------|----------------|-------------|-------|
| Write confirm-gate | Any book-mutating tool via the shim `/mcp` requires `confirmed:true` | `accountingqb-local/serve.py` `_is_write_tool` | Platform |
| Region gating | Every jurisdiction-specific tool refuses the wrong region (US↔CA) | `_get_region` / `require_region` (server.py); regression net: `tests/test_region_gating.py` auto-discovers every `@require_region` tool and asserts it refuses + never fetches on a mismatch | Tax |
| License gating | Licensed tools require an active/trialing license | `require_license` (server.py), web license routes; regression: `tests/test_license_gating.py` (paid tools refuse an invalid license + never run the body; crown-jewel tools stay out of FREE_TOOLS) | Platform |
| Read-only mode (client-selectable) | When `licenses.read_only` is set, the connector refuses every book-mutating tool before it runs AND hides them from tools/list — a hard, server-enforced lock beyond Claude's per-action approval | `require_not_readonly` / `_apply_readonly_gating` + `READ_ONLY_TOOLS` (server.py), `ctx.read_only` set by remote.py; toggle: dashboard → `POST /api/user/read-only`; regression: `tests/test_read_only_mode.py` | Owner/Platform |
| Chat read-only allowlist | `/chat` agentic loop exposes ONLY read-only tools (never a write) | `_CHAT_ALLOW` / `_anthropic_tools()` (serve.py) | Platform |
| Coffer pairing gate | The Coffer structured dialect on the 3 contract tools requires the identity-verified pairing secret; a secret-less call gets the normal (confirm-gated) tool, so the app's own UI is never locked out | `_load_pairing` + `x-aqb-pairing` (serve.py `mcp_call`) | Platform |
| `MCP_JWT_SECRET` fail-closed | Remote connector refuses all requests if unset | `remote.py` | Platform |
| `TOKEN_ENCRYPTION_KEY` fail-closed | Production refuses to run without it | server.py / web | Platform |
| Branch protection | `main` requires PR + pytest + secret-scan + theater + web-checks + web-e2e + schema-drift | GitHub settings | Owner |
| Update signature | Desktop auto-update installs only artifacts signed by the pinned minisign pubkey | `plugins.updater.pubkey` (tauri.conf.json) + CI `TAURI_SIGNING_PRIVATE_KEY` | Owner |

## Rate limits (hard stops on public endpoints — Upstash)
`web/src/lib/ratelimit.ts`. Per IP or per license as noted. Owner: Platform.
| Limiter | Limit |
|---------|-------|
| checkout | 5/min | 
| token | 10/min |
| oauth-start | 5/min/license |
| usage-track | 100/min/license |
| support | 20/min/IP |
| oauth2-register | 5/min/IP |
| download | 60/min/IP |
| link (pairing issue/redeem/status) | 10/min/IP |
| oauth2-token | 20/min/IP |
| default-realm | 30/min/IP |
| license-verify | 10/min/IP |

## Modes / feature flags
| Flag | Designed state | Enforced in | Owner |
|------|----------------|-------------|-------|
| Demo mode (`_demo_active`) | Canned QuickBooks data ONLY when no QB is connected / demo license `LK-DEMO-REVIEW2026`; logs "DEMO MODE" to the user | server.py | Platform |
| `is_test` (licenses) | Test licenses excluded from real metrics/dashboards | web admin/usage queries | Owner |
| tool_usage retention | Raw per-call rows kept `TOOL_USAGE_RETENTION_DAYS` (default **90**) days; a permanent `tool_usage_daily` rollup preserves all-time totals so pruning never shrinks lifetime numbers. Prune runs only when `TOOL_USAGE_PRUNE_ENABLED=true` | `web/src/app/api/cron/rollup-usage/route.ts` + `prune_tool_usage()` / `rollup_tool_usage()` (Supabase) | Owner |
| Watchdog (G2) | Every 5 min, probes the connector `/healthz` + marketing site; emails `WATCHDOG_ALERT_EMAIL` (default ryan@vasperacapital.com) on DOWN (after 2 consecutive fails), re-alerts ≤6h while down, and on RECOVERED. Silent when healthy. Also pings the external dead-man `HEALTHCHECK_PING_URL` each run (base on success, `/fail` on a down check) so a full Vercel/app outage — which this in-Vercel watchdog can't self-report — is caught by healthchecks.io when the pings stop (G6) | `web/src/app/api/cron/watchdog/route.ts` + `watchdog_state` (Supabase) | Owner |
| Hosted vs local tier | Data-locality promise differs by tier (Constitution §"Books Data Locality") | connector + marketing copy | Owner |
| Two-door (`in_app=1`) | Desktop shell affordances only in the packaged app | `accountingqb-local/artifact.html` | Platform |

Missing an owner column entry = a decision to make, not a blank to ignore.
