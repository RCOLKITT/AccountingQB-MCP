"""Channel-parity gates — every way users work with the platform must get the
same capability (docs/RELEASE-PLAYBOOK.md is the human-readable companion).

Drift this suite exists to prevent (each one actually happened, 2026-10):
  - the support KB said '130 Total' while the manifest shipped 142 tools, with
    21 tools missing entirely — its '(N Total)' header evades the generic
    tool-count copy regex in test_tax_data_policy, so it needs its own gate;
  - the public changelog had no entries for four shipped releases;
  - the desktop app's two version files could disagree.

The one parity step CI cannot force — cutting the signed desktop release so it
re-bundles the current server — is nudged by the channel-parity job in
.github/workflows/release.yml, which opens an issue when desktop lags.
"""

import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_TOOLS = {
    t["name"] for t in json.loads((REPO / "mcpb/manifest.json").read_text())["tools"]
}


def _pyproject_version() -> str:
    text = (REPO / "mcpb/pyproject.toml").read_text()
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1)


# --- support KB: the full tool list users' support answers come from ---------


def test_support_kb_lists_every_tool():
    kb_text = (REPO / "web/src/lib/support-kb/tools.md").read_text()
    kb = set(re.findall(r"\bqb_[a-z0-9_]+\b", kb_text))
    missing = sorted(MANIFEST_TOOLS - kb)
    ghosts = sorted(kb - MANIFEST_TOOLS)
    assert not missing, (
        f"support-kb/tools.md is missing {len(missing)} shipped tool(s): {missing}. "
        "Add them to the right section and bump that section's count + the total."
    )
    assert not ghosts, (
        f"support-kb/tools.md lists tool(s) that don't exist: {ghosts}. "
        "Remove or rename them — the support bot must not describe phantom tools."
    )


def test_support_kb_total_matches_manifest():
    kb_text = (REPO / "web/src/lib/support-kb/tools.md").read_text()
    m = re.search(r"#\s*AccountingQB Tools \((\d+) Total\)", kb_text)
    assert m, "support-kb/tools.md header must read '# AccountingQB Tools (N Total)'"
    assert int(m.group(1)) == len(MANIFEST_TOOLS), (
        f"support-kb header says {m.group(1)} tools, manifest ships "
        f"{len(MANIFEST_TOOLS)} — update the header (and whichever section grew)."
    )


def test_support_kb_section_counts_sum_to_total():
    kb_text = (REPO / "web/src/lib/support-kb/tools.md").read_text()
    sections = [int(n) for n in re.findall(r"^## .*\((\d+)\)", kb_text, re.MULTILINE)]
    assert sections, "support-kb/tools.md has no '## Section (N)' headers"
    assert sum(sections) == len(MANIFEST_TOOLS), (
        f"support-kb section counts sum to {sum(sections)} but the manifest ships "
        f"{len(MANIFEST_TOOLS)} tools — a section count wasn't updated."
    )


# --- public changelog: no feature release ships without release notes --------


def test_changelog_covers_current_minor():
    """The newest /changelog entry must share major.minor with the shipping
    package version — a feature release (X.Y.0) can't ship silently. Patch
    releases (X.Y.1+) ride the minor's existing entry."""
    text = (REPO / "web/src/lib/changelog.ts").read_text()
    m = re.search(r'version:\s*"(\d+\.\d+\.\d+)"', text)
    assert m, "could not find the newest version entry in changelog.ts"
    newest = m.group(1)
    pkg = _pyproject_version()
    assert newest.rsplit(".", 1)[0] == pkg.rsplit(".", 1)[0], (
        f"changelog.ts newest entry is {newest} but the package is {pkg} — "
        "prepend a release entry to web/src/lib/changelog.ts for this release."
    )


# --- desktop app: its two version files must agree ----------------------------


def test_desktop_version_files_agree():
    tauri = json.loads(
        (REPO / "accountingqb-desktop-tauri/src-tauri/tauri.conf.json").read_text()
    )["version"]
    pkg = json.loads((REPO / "accountingqb-desktop-tauri/package.json").read_text())[
        "version"
    ]
    assert tauri == pkg, (
        f"desktop version drift: tauri.conf.json={tauri} vs package.json={pkg} — "
        "bump both together (the desktop-v* tag must match tauri.conf.json)."
    )
