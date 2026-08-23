#!/usr/bin/env python3
"""Build the AccountingQB Door-2 sidecar (PyInstaller onefile) and place it where
Tauri's externalBin expects it: src-tauri/binaries/accountingqb-server-<target-triple>.

Cross-platform (macOS / Windows / Linux). Run from anywhere:
    python3 accountingqb-desktop-tauri/scripts/build_sidecar.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TAURI = REPO / "accountingqb-desktop-tauri"


def main() -> None:
    # Install the connector deps + web layer + PyInstaller into the current interpreter.
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q",
         "-r", str(REPO / "requirements.txt"),                       # connector runtime deps
         "-r", str(REPO / "accountingqb-local" / "requirements.txt"),  # shim web layer
         "pyinstaller"]
    )
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--clean", "-y",
         "--distpath", str(TAURI / ".dist"),
         "--workpath", str(TAURI / ".build"),
         str(TAURI / "accountingqb-server.spec")]
    )
    triple = _target_triple()
    exe = ".exe" if os.name == "nt" else ""
    bindir = TAURI / "src-tauri" / "binaries"
    bindir.mkdir(parents=True, exist_ok=True)
    dst = bindir / f"accountingqb-server-{triple}{exe}"
    shutil.copy(TAURI / ".dist" / f"accountingqb-server{exe}", dst)
    if not exe:
        os.chmod(dst, 0o755)
    print(f"sidecar -> {dst}")  # ASCII arrow: Windows console is cp1252


def _target_triple() -> str:
    out = subprocess.check_output(["rustc", "-vV"]).decode()
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split("host:")[1].strip()
    raise RuntimeError("could not determine rust host triple (is rustc installed?)")


if __name__ == "__main__":
    main()
