# Release Playbook — every channel, same capability

Users reach AccountingQB four ways. A release is not done until **all four**
carry the same server (and the doc surfaces describe it). This page is the
human-readable companion to the mechanical gates in `tests/test_channel_parity.py`,
`tests/test_version_parity.py`, and the `channel-parity` job in `release.yml`.

## The channels and how each one ships

| Channel | Ships when | Automated? |
|---|---|---|
| **Hosted connector** (mcp.accountingqb.com) | `git tag vX.Y.Z && git push origin vX.Y.Z` → Fly deploy, smoke-gated | ✅ by `release.yml` |
| **PyPI** (`pip install accountingqb`, self-hosted) | same `v*` tag → PyPI publish | ✅ by `release.yml` (same tag) |
| **Cowork plugin** | merge to `main` (plugin is served from the public repo) | ✅ version-parity-tested |
| **Desktop app** (macOS/Windows) | `git tag desktop-vA.B.C` → signed builds + auto-updater | ⚠️ **THE ONE MANUAL STEP** |
| Web app (site, dashboard, docs pages) | merge to `main` → Vercel | ✅ continuous |

## The one manual step: the desktop release

The desktop app **bundles the server at build time** (PyInstaller). A `v*`
release does NOT reach desktop users until a `desktop-v*` tag rebuilds it.
This lagged a full month once (desktop-v0.3.2 shipped a pre-class server while
hosted/PyPI were six releases ahead).

**After any `v*` release that users should get on desktop:**

1. Bump the version in **both** `accountingqb-desktop-tauri/src-tauri/tauri.conf.json`
   and `accountingqb-desktop-tauri/package.json` (patch bump) — branch → PR → merge.
2. `git tag desktop-vA.B.C && git push origin desktop-vA.B.C`
   → signed/notarized macOS + Windows builds, `releases/latest` flips, existing
   installs auto-update via `latest.json`.

If you forget, the `channel-parity` job on the next connector release **opens a
tracking issue**; the desktop release flow closes it automatically once parity
is restored.

## What CI enforces mechanically (don't re-check by hand)

| Gate | Where | Catches |
|---|---|---|
| pyproject == manifest == both plugin.json == `__version__` | `test_version_parity.py` | connector-artifact version drift |
| Tag `vX.Y.Z` == pyproject | `release.yml` verify step | tagging the wrong commit |
| Live `/version` == tag after deploy | `release.yml` smoke gate | partial deploys |
| **Tool docs are build artifacts**: `tools-catalog.json` + `support-kb/tools.md` must equal regeneration **byte-for-byte** | `generate-tools-catalog.mjs --check` in web-checks | hand-edited or stale tool docs — descriptions included, not just counts |
| Support KB lists **every** manifest tool, no ghosts, header + section counts correct | `test_channel_parity.py` | the "130 Total / 21 tools missing" drift (belt to the byte-check's suspenders) |
| Newest changelog entry matches the shipping minor | `test_channel_parity.py` | feature releases with no public release notes |
| Desktop's two version files agree | `test_channel_parity.py` | half-bumped desktop versions |
| Tool-count copy everywhere (web, README, llms.txt, plugin, **CONNECTOR-SUBMISSION.md**) | `test_tax_data_policy.py` copy gate | stale "N tools" marketing copy |
| Web tools catalog == manifest; every tool categorized once; write flags match | `web` vitest | /tools page drift |
| Latest `desktop-v*` bundles the just-shipped server, else **issue opened** | `release.yml` `channel-parity` job | the desktop lag itself |

### The tool-docs pipeline (nothing is prose)

```
server.py docstrings ──generate-schemas.py──▶ mcpb/manifest.json (source of truth)
                                                    │
tools-categories.json (the ONE human input:         │ generate-tools-catalog.mjs
a name→category mapping — data, not prose) ─────────┤
                                                    ▼
                              tools-catalog.json  +  support-kb/tools.md
                              (GENERATED — CI fails on any hand edit)
```

To change a tool's description anywhere, change its **docstring** and regenerate —
the manifest, /tools page, and support KB all update together and cannot disagree.
The changelog is the one deliberately-prose surface (release notes are narrative);
its gate enforces existence-per-release, not wording.

## Adding a new tool — the full checklist

Most of this is CI-enforced (the gates above will fail the PR if skipped):

1. Tool in `mcpb/src/accountingqb/server.py` with a good first docstring sentence —
   it becomes the tool's description on the /tools page and in the support KB
   (+ tests; region-gate if jurisdictional).
2. `python3 scripts/generate-schemas.py` (regenerates `mcpb/manifest.json`).
3. Add the tool's name to **one** category in `web/src/lib/tools-categories.json`
   (the single human input — a mapping, not prose). Optionally a minutes entry in
   `time-saved.ts` (defaults to 5).
4. `node scripts/generate-tools-catalog.mjs` (regenerates `tools-catalog.json` +
   `support-kb/tools.md` — never edit those by hand; CI byte-checks them).
5. Bump versions: `mcpb/pyproject.toml`, `__init__.py`, manifest, 2× plugin.json.
6. Tool-count copy: bump "N tools" strings repo-wide (the copy gate lists offenders).
7. Changelog entry in `web/src/lib/changelog.ts` (newest-first).
8. Merge → tag `vX.Y.Z` → after release, cut the desktop release (above).

## Regression testing — the incident→test rule

**Every customer-reported bug gets a test that reproduces the exact incident
shape, written BEFORE the fix and named after the failure mode.** Not a nearby
test — the shape the user actually hit. Three incidents in one week each mapped
to a missing test *class*; these lanes now exist and new work should extend the
right one:

| Test class | Where | The incident that created it |
|---|---|---|
| **Contract tests** — assert real QBO behavior, not our assumptions | `scripts/contract-canary.py`, weekly via `contract-canary.yml` (drift → auto-issue) | Mocked tests asserted a class column on TransactionList that the real API silently drops |
| **Route-logic tests** — auth/license-critical API routes | `web/src/app/api/**/route.test.ts` (vitest; chainable supabase/Clerk mocks — follow `user/licenses/route.test.ts`) | `/api/user/licenses` treated email matching as a fallback; a new trial was invisible behind an old linked license |
| **Multi-instance simulation** — anything cached per-machine | `tests/test_remote.py` (model machine B explicitly: no write-through, TTL expiry) | Company switch: write-through fixed machine A while machine B served the old company for the full TTL |

Mock-fidelity rule: a mocked QBO response shape used in tests must either come
from a captured real response or be covered by a canary contract. If you mock a
behavior the canary doesn't probe, add the probe.

The canary needs `CANARY_LICENSE_KEY` (owner-controlled license, read-only
probes only — never a customer's). NOTE: an Intuit *sandbox* company cannot
connect to the hosted connector (the API base is production-wide via
`QB_ENVIRONMENT`); the way to a class-tracked canary realm is to enable class
tracking on the owner's production company — `qb_enable_class_tracking` +
`qb_create_class` do it through the product (QBO Plus/Advanced required). The
canary detects class tracking per realm and upgrades its assertions
automatically.
