# Flag & Gate Registry (VASPERA-SPINE §2 layer 4, gap G1)

Every governance/policy control: name → designed state → where enforced → owner. If a control's
real behavior drifts from its designed state, that's a bug — fix the code or update this row.

## Safety gates (block on violation)
| Control | Designed state | Enforced in | Owner |
|---------|----------------|-------------|-------|
| Write confirm-gate | Any book-mutating tool via the shim `/mcp` requires `confirmed:true` | `accountingqb-local/serve.py` `_is_write_tool` | Platform |
| Region gating | Every jurisdiction-specific tool refuses the wrong region (US↔CA) | `_get_region` / `require_region` (server.py) | Tax |
| License gating | Licensed tools require an active/trialing license | `require_license` (server.py), web license routes | Platform |
| Chat read-only allowlist | `/chat` agentic loop exposes ONLY read-only tools (never a write) | `_CHAT_ALLOW` / `_anthropic_tools()` (serve.py) | Platform |
| Coffer pairing gate | The Coffer structured dialect on the 3 contract tools requires the identity-verified pairing secret; a secret-less call gets the normal (confirm-gated) tool, so the app's own UI is never locked out | `_load_pairing` + `x-aqb-pairing` (serve.py `mcp_call`) | Platform |
| `MCP_JWT_SECRET` fail-closed | Remote connector refuses all requests if unset | `remote.py` | Platform |
| `TOKEN_ENCRYPTION_KEY` fail-closed | Production refuses to run without it | server.py / web | Platform |
| Branch protection | `main` requires PR + pytest + secret-scan + theater + web-checks | GitHub settings | Owner |
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
| Hosted vs local tier | Data-locality promise differs by tier (Constitution §"Books Data Locality") | connector + marketing copy | Owner |
| Two-door (`in_app=1`) | Desktop shell affordances only in the packaged app | `accountingqb-local/artifact.html` | Platform |

Missing an owner column entry = a decision to make, not a blank to ignore.
