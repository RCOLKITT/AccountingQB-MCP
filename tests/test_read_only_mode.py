"""Read-only mode invariant — a client-selected read-only connection must make every
book-mutating tool structurally impossible, server-side (not just client approval).

When `licenses.read_only` is set, the remote service puts `read_only=True` on the
per-request QBContext; `_apply_readonly_gating` (server.py) wraps every non-read-only
tool so it refuses BEFORE running. These lock that: every write tool refuses under a
read-only context and never touches QuickBooks; read tools are unaffected.

Mirrors test_region_gating.py / test_license_gating.py. The gate wraps `tool.fn` in the
registry (the path the connector actually calls), so we exercise the registry fn.
"""

import asyncio

import accountingqb.server as s
from accountingqb.context import QBContext, reset_ctx, set_ctx

# Every registered tool that is NOT read-only → must be gated.
WRITE_TOOLS = sorted(set(s.mcp._tool_manager._tools.keys()) - s.READ_ONLY_TOOLS)


def test_read_only_tool_set_is_populated_and_correct():
    assert len(s.READ_ONLY_TOOLS) >= 90, len(s.READ_ONLY_TOOLS)
    # Representative report tools are read-only …
    for t in ["qb_profit_loss", "qb_balance_sheet", "qb_cash_flow", "qb_trial_balance"]:
        assert t in s.READ_ONLY_TOOLS, f"{t} should be read-only"
    # … and crown-jewel book-mutating tools are NOT (so they get gated).
    for t in [
        "qb_create_invoice",
        "qb_batch_create_bills",
        "qb_apply_categorization_rules",
    ]:
        assert t in s.mcp._tool_manager._tools, f"{t} not registered"
        assert t not in s.READ_ONLY_TOOLS, f"{t} must be a gated write tool"


def test_readonly_wrapper_refuses_then_runs():
    """Unit-test the gate directly: refuses (without running the body) under a
    read-only context; runs the body when not read-only."""
    log = {"ran": False}

    async def fn(*_a, **_k):
        log["ran"] = True
        return "RAN"

    fn.__name__ = "qb_create_invoice"
    gated = s.require_not_readonly(fn)

    tok = set_ctx(QBContext(read_only=True))
    try:
        out = asyncio.run(gated())
    finally:
        reset_ctx(tok)
    assert log["ran"] is False and out.startswith("⚠️")

    tok = set_ctx(QBContext(read_only=False))
    try:
        assert asyncio.run(gated()) == "RAN" and log["ran"] is True
    finally:
        reset_ctx(tok)


def test_every_write_tool_refuses_under_read_only(monkeypatch):
    """Under a read-only context, EVERY write tool refuses via ⚠️ and never reaches
    QuickBooks (qb_request/qb_query stubbed to raise)."""

    def _must_not_fetch(*_a, **_k):
        raise AssertionError("a read-only connection reached QuickBooks!")

    for name in ("qb_request", "qb_query", "qb_query_all"):
        if hasattr(s, name):
            monkeypatch.setattr(s, name, _must_not_fetch)

    tok = set_ctx(QBContext(read_only=True))
    try:
        for tool_name in WRITE_TOOLS:
            fn = s.mcp._tool_manager._tools[tool_name].fn
            result = asyncio.run(fn())  # wrapper is (*args) — refuses before body
            assert isinstance(result, str), f"{tool_name}: expected refusal string"
            assert result.startswith(
                "⚠️"
            ), f"{tool_name} did not refuse: {result[:80]!r}"
            assert "read-only" in result.lower(), tool_name
    finally:
        reset_ctx(tok)
