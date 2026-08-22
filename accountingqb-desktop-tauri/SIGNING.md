# Phase 2c — signing & release checklist (needs you)

The code is scaffolded and the sidecar is verified. To produce **signed installers** you
need to add secrets and run the release once. This is the part I can't do from the repo.

## 1. Create the releases repo
Create a public repo **`accountingqb-releases`** (or edit `RELEASES_REPO` in
`.github/workflows/release-desktop.yml`). Downloads/links point at its Releases.

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

**Windows (Azure Trusted Signing — you already registered Azure):**
| Secret | What |
|--------|------|
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | a service principal with the "Trusted Signing Certificate Profile Signer" role |

Then set your account/cert names in **two places** (currently placeholders `AccountingQB` /
`AccountingQBPublic`): `src-tauri/tauri.conf.json` → `bundle.windows.signCommand`, and the
"Sign the sidecar" step in `release-desktop.yml`.

**Publish:** `RELEASES_TOKEN` — a PAT with `contents:write` on `accountingqb-releases`.

## 3. Release
```bash
git tag desktop-v0.1.0 && git push origin desktop-v0.1.0
```
The workflow builds the PyInstaller sidecar, generates icons from `web/public/logo-512.png`,
builds + signs the `.dmg` (notarized/stapled) and the Windows `-setup.exe`, and publishes both.

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
