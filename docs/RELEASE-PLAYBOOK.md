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
| Support KB lists **every** manifest tool, no ghosts, header + section counts correct | `test_channel_parity.py` | the "130 Total / 21 tools missing" drift |
| Newest changelog entry matches the shipping minor | `test_channel_parity.py` | feature releases with no public release notes |
| Desktop's two version files agree | `test_channel_parity.py` | half-bumped desktop versions |
| Tool-count copy everywhere (web, README, llms.txt, plugin, **CONNECTOR-SUBMISSION.md**) | `test_tax_data_policy.py` copy gate | stale "N tools" marketing copy |
| Web tools catalog == manifest; every tool categorized once; write flags match | `web` vitest | /tools page drift |
| Latest `desktop-v*` bundles the just-shipped server, else **issue opened** | `release.yml` `channel-parity` job | the desktop lag itself |

## Adding a new tool — the full checklist

Most of this is CI-enforced (the gates above will fail the PR if skipped):

1. Tool in `mcpb/src/accountingqb/server.py` (+ tests; region-gate if jurisdictional).
2. `python3 scripts/generate-schemas.py` (regenerates `mcpb/manifest.json`).
3. Bump versions: `mcpb/pyproject.toml`, `__init__.py`, manifest, 2× plugin.json.
4. Web wiring: `tools-catalog.json`, `tools-categories.ts`, `time-saved.ts`.
5. `web/src/lib/support-kb/tools.md`: add the tool to its section, bump the
   section count and the `(N Total)` header.
6. Tool-count copy: bump "N tools" strings repo-wide (the copy gate lists offenders).
7. Changelog entry in `web/src/lib/changelog.ts` (newest-first).
8. Merge → tag `vX.Y.Z` → after release, cut the desktop release (above).
