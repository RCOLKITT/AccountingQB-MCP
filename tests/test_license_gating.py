"""License-gating invariant — paid tools must refuse an invalid license.

`require_license` (server.py) is the revenue gate: FREE_TOOLS always pass; when a
license system is configured, a non-free tool validates the license and, if invalid,
returns a refusal string WITHOUT running the tool body. This had no direct test — a
refactor could silently stop gating (giving paid tools away) or add a paid tool to
FREE_TOOLS (revenue leak). These lock the behavior + the free/paid split.

`_apply_license_gating()` is a no-op in the test env (no license infra configured), so
we exercise the `require_license` wrapper directly — the same unit the gating applies.
"""

import asyncio

import accountingqb.server as s


def _wrap(name, log):
    """A synthetic tool named `name`, wrapped by require_license. Records if the body
    ran (the gate must NOT run the body when it refuses)."""

    async def fn(*_a, **_k):
        log["ran"] = True
        return "TOOL-RAN"

    fn.__name__ = name
    return s.require_license(fn)


def _bad_license(monkeypatch):
    monkeypatch.setattr(s, "_effective_license_key", lambda: "LK-BAD")

    async def invalid(_key):
        return {"valid": False, "tier": "free"}

    monkeypatch.setattr(s, "_validate_license", invalid)


def test_paid_tool_refuses_invalid_license(monkeypatch):
    _bad_license(monkeypatch)
    log = {"ran": False}
    tool = _wrap("qb_schedule_c", log)  # a non-free tool name

    result = asyncio.run(tool("2025"))

    assert log["ran"] is False, "paid tool body ran despite an invalid license"
    assert isinstance(result, str)
    assert "requires a paid license" in result


def test_valid_license_passes_through(monkeypatch):
    monkeypatch.setattr(s, "_effective_license_key", lambda: "LK-GOOD")

    async def valid(_key):
        return {"valid": True, "tier": "pro"}

    monkeypatch.setattr(s, "_validate_license", valid)
    log = {"ran": False}
    tool = _wrap("qb_schedule_c", log)

    assert asyncio.run(tool("2025")) == "TOOL-RAN"
    assert log["ran"] is True


def test_free_tool_bypasses_validation(monkeypatch):
    # A FREE_TOOL must run even with an invalid license — and must NOT even call the
    # validator (validation raising proves the free-tool short-circuit).
    monkeypatch.setattr(s, "_effective_license_key", lambda: "LK-BAD")

    async def explode(_key):
        raise AssertionError("free tool must not validate the license")

    monkeypatch.setattr(s, "_validate_license", explode)
    free_name = next(iter(s.FREE_TOOLS))
    log = {"ran": False}
    tool = _wrap(free_name, log)

    assert asyncio.run(tool()) == "TOOL-RAN"
    assert log["ran"] is True


def test_dev_mode_unlocks_without_validating(monkeypatch):
    # No license infra (no effective key, no validation URL) = dev/self-hosted =
    # everything unlocked, and the validator is never consulted.
    monkeypatch.setattr(s, "_effective_license_key", lambda: "")
    monkeypatch.setattr(s, "_LICENSE_VALIDATION_URL", "", raising=False)

    async def explode(_key):
        raise AssertionError("dev mode must not validate")

    monkeypatch.setattr(s, "_validate_license", explode)
    log = {"ran": False}
    tool = _wrap("qb_schedule_c", log)  # a paid tool, still unlocked in dev

    assert asyncio.run(tool("2025")) == "TOOL-RAN"
    assert log["ran"] is True


def test_free_tools_are_all_real_registered_tools():
    # A typo in FREE_TOOLS is a silent bug (a phantom free tool, or a real tool left
    # gated). Every FREE_TOOL must be a registered tool.
    registered = set(s.mcp._tool_manager._tools.keys())
    missing = sorted(s.FREE_TOOLS - registered)
    assert not missing, f"FREE_TOOLS not registered: {missing}"


def test_revenue_crown_jewels_are_not_free():
    # High-value tax + book-mutating tools MUST require a license. If a refactor adds
    # one to FREE_TOOLS, this fails loudly (revenue leak) rather than silently.
    MUST_REQUIRE_LICENSE = {
        "qb_schedule_c",
        "qb_form_1120s_summary",
        "qb_form_1065_summary",
        "qb_t2125_summary",
        "qb_estimate_quarterly_tax",
        "qb_batch_create_bills",
        "qb_batch_create_expenses",
        "qb_apply_categorization_rules",
    }
    registered = set(s.mcp._tool_manager._tools.keys())
    for tool in MUST_REQUIRE_LICENSE:
        assert tool in registered, f"{tool} is not a registered tool"
        assert tool not in s.FREE_TOOLS, f"{tool} leaked into FREE_TOOLS!"
