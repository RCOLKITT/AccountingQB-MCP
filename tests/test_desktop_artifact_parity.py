"""Drift guard: the desktop artifact (accountingqb-local/artifact.html) is a fork of the Cowork
plugin dashboard template, adapted with a window.cowork shim. The DATA layer (report tabs + the
qb_* tools each loads) must stay in parity — if the plugin gains a tab or a report tool, the
desktop copy has to be updated too, or this test fails. It also asserts the shim is present.
"""

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent
DESKTOP = _ROOT / "accountingqb-local" / "artifact.html"
PLUGIN = (
    _ROOT
    / "cowork-plugin"
    / "skills"
    / "accountingqb-dashboard"
    / "references"
    / "artifact-template.html"
)


def _tabs(html: str) -> set:
    return set(re.findall(r'data-tab="([a-z]+)"', html))


def _report_tools(html: str) -> set:
    # Tools pulled for the report tabs are invoked as call('qb_...'). Write tools (qb_create_*)
    # are NOT called this way in the desktop (they go through the confirm-gated path), so they
    # don't enter this set — parity stays clean.
    return set(re.findall(r"\bcall\('(qb_[a-z0-9_]+)'", html))


def test_desktop_and_plugin_tabs_match():
    d, p = _tabs(DESKTOP.read_text()), _tabs(PLUGIN.read_text())
    assert d == p, f"tab drift between desktop and plugin: {d ^ p}"


def test_desktop_and_plugin_report_tools_match():
    # The desktop must cover EVERY tool the plugin template uses (a plugin change
    # fails here until the desktop catches up — the original drift this guards).
    # The desktop MAY exceed the plugin: it became the flagship surface and grows
    # first (practice layer, workpapers, rules), so superset — not equality.
    d, p = _report_tools(DESKTOP.read_text()), _report_tools(PLUGIN.read_text())
    assert p <= d, f"plugin uses tools the desktop lacks: {p - d}"


def test_desktop_has_cowork_shim():
    html = DESKTOP.read_text()
    assert "window.cowork" in html
    for fn in ("callMcpTool", "askClaude", "sendPrompt"):
        assert fn in html, f"window.cowork shim missing {fn}"
