"""Version-parity invariant — the connector version is ONE number across every artifact
that ships the 138-tool connector.

`mcpb/pyproject.toml` is canonical (it's what PyPI publishes and what the release tag is
verified against — see .github/workflows/release.yml). The generated MCP manifest and the
Cowork plugin (both `.claude-plugin/plugin.json` and the root `plugin.json`) bundle/point at
that same connector, so they must carry the same version. The plugin drifted to 3.16.0 while
the connector shipped 3.18.2; this test makes that drift a red CI gate instead of a thing a
human has to remember.

Deliberately NOT covered: `web/` (the Next.js app, versioned independently at 2.x) and
`accountingqb-desktop-tauri/` (the desktop app, versioned independently at 0.x). Those are
separate products with their own release cadence — coupling them here would be wrong.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    text = (REPO / "mcpb" / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "could not find version in mcpb/pyproject.toml"
    return m.group(1)


CANONICAL = _pyproject_version()

# Every artifact that must carry the SAME version as the connector package.
PINNED_JSON = [
    "mcpb/manifest.json",
    "cowork-plugin/.claude-plugin/plugin.json",
    "cowork-plugin/plugin.json",
]


def test_canonical_version_is_sane():
    # Guards against a regex that silently matched nothing / a malformed bump.
    assert re.fullmatch(r"\d+\.\d+\.\d+", CANONICAL), CANONICAL


def test_all_connector_artifacts_match_pyproject():
    mismatches = {}
    for rel in PINNED_JSON:
        data = json.loads((REPO / rel).read_text())
        if data.get("version") != CANONICAL:
            mismatches[rel] = data.get("version")
    assert not mismatches, (
        f"version drift from canonical {CANONICAL} (mcpb/pyproject.toml): {mismatches}. "
        "Bump these to match — the plugin/manifest ship the same connector."
    )
