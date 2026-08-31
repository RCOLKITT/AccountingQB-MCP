# accountingqb-desktop-tauri — Door 2 desktop app (Phase 2c)

A signed desktop app (macOS `.dmg` + Windows installer) that bundles the AccountingQB
connector as a **PyInstaller sidecar** and opens the local UI in a Tauri window — no Python,
no terminal, no Claude required. The Python analog of Hearth's Node-SEA desktop app.

## How it works
1. `src-tauri/src/main.rs` picks a free port (8788→OS), spawns the sidecar
   (`accountingqb-server`) with `ACCOUNTINGQB_PORT`/`ACCOUNTINGQB_NO_OPEN`/`ACCOUNTINGQB_DATA_DIR`,
   waits for `/healthz`, and opens the window on `http://127.0.0.1:<port>/?in_app=1`.
2. The sidecar is `accountingqb-local/serve.py` + the connector, frozen into one binary by
   `accountingqb-server.spec` (bundles `manifest.json`, `artifact.html`, `tax_ledger.jsonl`).
3. On exit, the shell kills the sidecar.

## Build locally
```bash
# 1. Build the sidecar (installs deps + PyInstaller into the current Python):
python3 accountingqb-desktop-tauri/scripts/build_sidecar.py
#    → src-tauri/binaries/accountingqb-server-<target-triple>

# 2. Generate icons once (from the brand logo) + run/build the app:
cd accountingqb-desktop-tauri
npm ci
npm exec -- tauri icon ../web/public/logo-512.png
npm exec -- tauri dev          # or: npm exec -- tauri build --bundles dmg
```
Prereqs: Rust toolchain, Node 22, Python 3.12. The sidecar binary and Tauri output are
git-ignored (never committed).

## Signing & release
See **SIGNING.md** — add Apple/Azure secrets, tag `desktop-v*`, CI publishes signed installers.

## Status
Sidecar bundling verified locally (the frozen binary serves `/healthz`, `/api/status` with 131
tools, the artifact, and runs tools using the bundled tax ledger). Tauri build + signing is the
remaining step and needs the signing secrets + clean-machine testing (SIGNING.md).
