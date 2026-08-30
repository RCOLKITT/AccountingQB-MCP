# Phase 2c — signing & release checklist (needs you)

The code is scaffolded and the sidecar is verified. To produce **signed installers** you
need to add secrets and run the release once. This is the part I can't do from the repo.

## 1. Releases repo
Releases publish to **this repo** (`RELEASES_REPO: RCOLKITT/AccountingQB-MCP` in
`.github/workflows/release-desktop.yml`); the site's `/api/download/*` and the updater's
`releases/latest/download/latest.json` both resolve against it. Already configured.

## 2. Add GitHub Actions secrets (to THIS repo)

**macOS (Apple Developer ID — you already registered Apple):**
| Secret | What |
|--------|------|
| `APPLE_CERTIFICATE_B64` | Your "Developer ID Application" cert exported as `.p12`, then `base64 -i cert.p12 | pbcopy` |
| `APPLE_CERTIFICATE_PASSWORD` | the `.p12` export password |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Vaspera Capital LLC (TEAMID)` |
| `APPLE_ID` | your Apple ID email |
| `APPLE_APP_PASSWORD` | an app-specific password (appleid.apple.com → Sign-In & Security) |
| `APPLE_TEAM_ID` | your 10-char Team ID |

**Windows (Azure Trusted Signing — reuse Hearth 1:1):** the workflow reads all Azure values
from secrets (nothing hardcoded), using the **same secret names Hearth already has**. Copy these
six from the Hearth repo into this repo — same values:
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SIGNING_ENDPOINT`,
`AZURE_SIGNING_ACCOUNT`, `AZURE_CERT_PROFILE`. (The Trusted Signing cert validates your org —
Vaspera Capital — so the same profile signs AccountingQB; end users see the Vaspera publisher,
not the profile name.)

**Updater (auto-update signing — minisign, already set):** the release also signs Tauri updater
artifacts so the app can verify an update before installing it.
| Secret | What |
|--------|------|
| `TAURI_SIGNING_PRIVATE_KEY` | the minisign private key from `tauri signer generate` |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | its password |

Both are already set in this repo's Actions secrets **and** backed up in Doppler
(`accountingqb-mcp/prd`). The matching **public** key is committed in `tauri.conf.json`
(`plugins.updater.pubkey`). ⚠️ If you ever rotate this key, existing installs can no longer
verify updates and must be reinstalled by hand — treat it like the Apple cert.

**Publish:** uses the built-in `GITHUB_TOKEN` (`permissions: contents: write`) to publish to this
repo's Releases — no PAT needed.

## 3. Release (deliberate, batched — not per-merge)
Work merges to `main` continuously (gated + QA'd). Cut a desktop release only when a batch is
ready, by pushing a tag. **Validate with a beta first:**
```bash
# 1. Beta lane — published as a GitHub *prerelease*; the auto-updater ignores it.
git tag desktop-v0.2.0-beta.1 && git push origin desktop-v0.2.0-beta.1
#    Install the beta by hand, validate on real data.
# 2. Ship it — the stable tag is the one users auto-update to.
git tag desktop-v0.2.0 && git push origin desktop-v0.2.0
```
The workflow builds the PyInstaller sidecar, generates icons from `app-icon.png`, builds + signs
the `.dmg` (notarized/stapled) and the Windows `-setup.exe`, signs the updater artifacts, and — for
a stable tag — assembles `latest.json` (the updater manifest) and attaches it to the release.
Because `releases/latest` skips prereleases, a `-beta`/`-rc` tag never reaches the auto-updater.
Bump `version` in `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, and `package.json`, and add
a `## <version> — <date>` entry to `CHANGELOG.md` (the in-app "What's new") before tagging.

## 4. Verify on clean machines (your hands)
- A Mac with no dev tools: download the `.dmg`, open, drag to Applications, launch → the app
  window opens the local UI with **no Gatekeeper warning**.
- A Windows box: run the installer → **no SmartScreen block**; app launches.
- First real end-to-end run: add your **Anthropic API key** in Settings, **Connect QuickBooks**,
  then use Chat + Dashboard on live data.

## Known risk to watch
PyInstaller **onefile** extracts a bundled CPython at runtime; notarization of onefile apps
occasionally rejects the extracted, unsigned inner files even with the relaxed entitlements in
`entitlements.plist`. If notarization fails, the fix is to switch the spec to **onedir** and
bundle the folder (Tauri `resources`) instead of `externalBin` — a known, documented change.
Test the macOS notarization path first.
