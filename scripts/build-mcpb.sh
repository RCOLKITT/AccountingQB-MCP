#!/usr/bin/env bash
#
# build-mcpb.sh — build a self-contained AccountingQB .mcpb desktop extension.
#
# Claude Desktop bundles Node.js but NOT Python. Python extensions must
# therefore vendor all of their package dependencies inside the bundle
# (server/lib) and rely on the user's own Python 3.10+ interpreter.
# This script produces such a bundle WITHOUT requiring uv on user machines:
# the manifest launches `python3 -m accountingqb.server` with
# PYTHONPATH=${__dirname}/src${pathSeparator}${__dirname}/server/lib.
#
# Usage:
#   scripts/build-mcpb.sh
#
# Cross-platform note:
#   A plain `pip install --target` on the packing machine is the baseline
#   and works for the pure-Python deps (mcp, httpx, pydantic). However,
#   `cryptography` and `pydantic-core` ship platform-specific wheels, so a
#   bundle built on Linux will not run on macOS/Windows. For distribution,
#   CI should run this script once per OS (macOS, Windows, Linux), or pass
#   explicit cross-build flags to pip, e.g.:
#     pip install --target ... --only-binary=:all: \
#         --platform macosx_11_0_arm64 --python-version 3.10 ...
#   and pack one .mcpb per platform.
#
# PYTHONPATH separator note:
#   The MCPB manifest uses ${pathSeparator} so the PYTHONPATH entry
#   expands with ':' on macOS/Linux and ';' on Windows. If a target
#   MCPB client does not support ${pathSeparator}, a win32
#   platform_overrides entry with a ';'-joined PYTHONPATH would be the
#   fallback — document/verify against the client before shipping.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCPB_DIR="$REPO_ROOT/mcpb"
LIB_DIR="$MCPB_DIR/server/lib"

VERSION="$(python3 -c "import json; print(json.load(open('$MCPB_DIR/manifest.json'))['version'])")"
echo "==> Building AccountingQB .mcpb v$VERSION"

# ---------------------------------------------------------------------------
# 1. Vendor Python dependencies into server/lib (no uv required at runtime)
# ---------------------------------------------------------------------------
echo "==> Cleaning $LIB_DIR"
rm -rf "$LIB_DIR"
mkdir -p "$LIB_DIR"

echo "==> Installing dependencies into server/lib (wheels only)"
# Unpinned on purpose — versions resolve at build time. Per-platform builds
# should add --platform/--python-version/--implementation/--abi for
# cross-builds; CI should run this script per OS.
python3 -m pip install \
    --target "$LIB_DIR" \
    --only-binary=:all: \
    "mcp[cli]" httpx pydantic cryptography

# Strip caches from the vendored tree to keep the bundle small.
find "$LIB_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$LIB_DIR" -type d -name "*.dist-info" -exec rm -rf {}/RECORD \; 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. Refresh manifest tools array from server.py
#    (--strip: name/description only, which is what `mcpb pack` expects)
# ---------------------------------------------------------------------------
echo "==> Regenerating manifest tools from server.py"
python3 "$REPO_ROOT/scripts/generate-schemas.py" --strip

# ---------------------------------------------------------------------------
# 3. Validate: manifest tool count must equal the server's registered count
# ---------------------------------------------------------------------------
echo "==> Validating manifest tool count against server.py"
python3 - "$MCPB_DIR" <<'PYEOF'
import ast, json, sys
from pathlib import Path

mcpb_dir = Path(sys.argv[1])
manifest = json.loads((mcpb_dir / "manifest.json").read_text())
tree = ast.parse((mcpb_dir / "src" / "accountingqb" / "server.py").read_text())

def is_tool(node):
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == "tool":
            return True
    return False

server_count = sum(
    1 for n in ast.walk(tree)
    if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and is_tool(n)
)
manifest_count = len(manifest.get("tools", []))
print(f"    server.py tools:  {server_count}")
print(f"    manifest tools:   {manifest_count}")
if server_count != manifest_count:
    sys.exit(f"ERROR: tool count mismatch (server={server_count}, manifest={manifest_count})")
print("    OK: counts match")
PYEOF

python3 -m json.tool "$MCPB_DIR/manifest.json" > /dev/null
echo "    OK: manifest.json is valid JSON"

# ---------------------------------------------------------------------------
# 4. Pack the bundle
# ---------------------------------------------------------------------------
OUT_FILE="$REPO_ROOT/accountingqb-$VERSION.mcpb"
rm -f "$OUT_FILE"

if command -v mcpb >/dev/null 2>&1; then
    echo "==> Packing with mcpb CLI"
    mcpb pack "$MCPB_DIR" "$OUT_FILE"
elif command -v npx >/dev/null 2>&1 && npx --yes @anthropic-ai/mcpb --version >/dev/null 2>&1; then
    echo "==> Packing with npx @anthropic-ai/mcpb"
    npx --yes @anthropic-ai/mcpb pack "$MCPB_DIR" "$OUT_FILE"
else
    echo "==> mcpb CLI not available; falling back to zip (honoring .mcpbignore)"
    # Build -x exclusion args from .mcpbignore (dir entries -> dir/**).
    EXCLUDES=()
    while IFS= read -r pattern; do
        # skip blanks and comments
        [[ -z "$pattern" || "$pattern" == \#* ]] && continue
        if [[ "$pattern" == */ ]]; then
            EXCLUDES+=("-x" "${pattern}*" "-x" "*/${pattern}*")
        else
            EXCLUDES+=("-x" "$pattern" "-x" "*/$pattern")
        fi
    done < "$MCPB_DIR/.mcpbignore"
    (cd "$MCPB_DIR" && zip -qr "$OUT_FILE" . "${EXCLUDES[@]}")
fi

echo "==> Done: $OUT_FILE"
ls -lh "$OUT_FILE" || true
