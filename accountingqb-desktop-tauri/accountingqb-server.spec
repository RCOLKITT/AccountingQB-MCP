# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AccountingQB Door-2 sidecar.

Bundles the local shim (accountingqb-local/serve.py) + the canonical connector
(mcpb/src/accountingqb) + its data (tax_ledger.jsonl) + manifest.json + artifact.html
into ONE self-contained binary — the Python analog of Hearth's Node SEA. No Python
required on the user's machine. Output name: accountingqb-server (the build script
renames it with the Rust target triple for Tauri's externalBin).

Run from the repo root:
    pyinstaller accountingqb-desktop-tauri/accountingqb-server.spec
"""
import os
from PyInstaller.utils.hooks import collect_submodules

REPO = os.path.dirname(SPECPATH)  # SPECPATH = .../accountingqb-desktop-tauri  # noqa: F821
SRC = os.path.join(REPO, "mcpb", "src")

datas = [
    (os.path.join(REPO, "mcpb", "manifest.json"), "."),
    (os.path.join(REPO, "accountingqb-local", "artifact.html"), "."),
    # Vendored front-end libs (pdfmake) served by the shim's /vendor route for branded PDF reports.
    (os.path.join(REPO, "accountingqb-local", "vendor"), "vendor"),
    # Loaded by the connector via Path(__file__).parent / "tax_ledger.jsonl".
    (os.path.join(SRC, "accountingqb", "tax_ledger.jsonl"), "accountingqb"),
]

hiddenimports = (
    collect_submodules("accountingqb")
    + collect_submodules("uvicorn")
    + collect_submodules("mcp")
    + collect_submodules("openpyxl")   # lazy-imported by /export/xlsx (Client Package Excel)
    + ["httpx", "starlette", "cryptography", "openpyxl", "et_xmlfile"]
)

a = Analysis(
    [os.path.join(REPO, "accountingqb-local", "serve.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="accountingqb-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
