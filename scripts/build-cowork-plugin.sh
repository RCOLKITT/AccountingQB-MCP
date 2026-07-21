#!/usr/bin/env bash
# Build web/public/downloads/accountingqb.plugin — the Cowork plugin bundle.
#
# Contents (deliberate, keep in sync with cowork-plugin/):
#   plugin.json, README.md, .mcp.json, .claude-plugin/   from cowork-plugin/
#   skills/                                              from cowork-plugin/
#   mcpb/{icon.png, manifest.json, accountingqb-<v>.mcpb} current build
#
# Run scripts/build-mcpb.sh first if the .mcpb is stale. The bundle must
# always contain the CURRENT server build — never a cached one (a stale
# May build shipping old tax logic is exactly what this script prevents).
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import json; print(json.load(open('mcpb/manifest.json'))['version'])")
MCPB="accountingqb-${VERSION}.mcpb"

[ -f "$MCPB" ] || { echo "Missing $MCPB — run scripts/build-mcpb.sh first"; exit 1; }

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

cp cowork-plugin/plugin.json cowork-plugin/README.md cowork-plugin/.mcp.json "$STAGE/"
cp -R cowork-plugin/.claude-plugin "$STAGE/.claude-plugin"
cp -R cowork-plugin/skills "$STAGE/skills"
mkdir -p "$STAGE/mcpb"
cp mcpb/icon.png mcpb/manifest.json "$STAGE/mcpb/"
cp "$MCPB" "$STAGE/mcpb/$MCPB"

# Version consistency: plugin manifests must match the mcpb build
for f in "$STAGE/plugin.json" "$STAGE/.claude-plugin/plugin.json"; do
  grep -q "\"version\": \"$VERSION\"" "$f" || {
    echo "Version mismatch: $f is not $VERSION — update cowork-plugin manifests"; exit 1; }
done

mkdir -p web/public/downloads
OUT="$PWD/web/public/downloads/accountingqb.plugin"
rm -f "$OUT"
(cd "$STAGE" && zip -r -q "$OUT" . -x "*.DS_Store")
cp "$OUT" "web/public/downloads/accountingqb-${VERSION}.plugin"

echo "Built: $OUT ($(du -h "$OUT" | cut -f1)) + versioned copy"
unzip -l "$OUT" | tail -3
