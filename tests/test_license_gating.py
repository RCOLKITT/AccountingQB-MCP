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
    # High-value tax + book-mutating tools AND the core financial reports MUST
    # require a license. If a refactor adds one to FREE_TOOLS, this fails loudly
    # (revenue leak) rather than silently.
    MUST_REQUIRE_LICENSE = {
        # tax + writes
        "qb_schedule_c",
        "qb_form_1120s_summary",
        "qb_form_1065_summary",
        "qb_t2125_summary",
        "qb_estimate_quarterly_tax",
        "qb_batch_create_bills",
        "qb_batch_create_expenses",
        "qb_apply_categorization_rules",
        # the reporting crown jewels — the product's core value, previously free
        "qb_profit_loss",
        "qb_balance_sheet",
        "qb_cash_flow",
        "qb_trial_balance",
        "qb_ar_aging",
        "qb_ap_aging",
        "qb_comparative_statements",
        "qb_list_invoices",
    }
    registered = set(s.mcp._tool_manager._tools.keys())
    for tool in MUST_REQUIRE_LICENSE:
        assert tool in registered, f"{tool} is not a registered tool"
        assert tool not in s.FREE_TOOLS, f"{tool} leaked into FREE_TOOLS!"


def test_free_set_is_minimal_connectivity_only():
    # The free set must stay tiny — connectivity/connection-management only, with
    # NO financial-reporting value. Widening it back is a revenue leak; lock it.
    assert s.FREE_TOOLS == {
        "qb_server_info",  # diagnostic only — no QuickBooks data
        "qb_company_info",
        "qb_list_companies",
        "qb_switch_company",
        "qb_refresh_connection",
    }


# ---------------------------------------------------------------------------
# _validate_license: hourly re-check + bounded offline grace, then fail closed.
# ---------------------------------------------------------------------------
def _fake_client(*, raises=False, status=200, payload=None):
    class _Resp:
        status_code = status

        def json(self):
            return payload or {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            if raises:
                raise RuntimeError("offline")
            return _Resp()

    return _Client


def test_validate_offline_within_grace_keeps_last_verdict(monkeypatch):
    import time

    monkeypatch.setattr(s, "_LICENSE_VALIDATION_URL", "https://x/api/validate")
    s._license_cache.clear()
    now = time.time()
    # last CONFIRMED check said valid, 1h ago; cache is now stale (needs recheck)
    s._license_cache["LK-X"] = {
        "valid": True,
        "tier": "pro",
        "validated_at": now - 3600,
        "expires": now - 1,
    }
    monkeypatch.setattr(s.httpx, "AsyncClient", _fake_client(raises=True))
    out = asyncio.run(s._validate_license("LK-X"))
    assert out["valid"] is True and out["reason"].startswith("grace")


def test_validate_offline_beyond_grace_fails_closed(monkeypatch):
    import time

    monkeypatch.setattr(s, "_LICENSE_VALIDATION_URL", "https://x/api/validate")
    s._license_cache.clear()
    now = time.time()
    s._license_cache["LK-X"] = {
        "valid": True,
        "tier": "pro",
        "validated_at": now - (73 * 3600),  # beyond 72h grace
        "expires": now - 1,
    }
    monkeypatch.setattr(s.httpx, "AsyncClient", _fake_client(raises=True))
    out = asyncio.run(s._validate_license("LK-X"))
    assert out["valid"] is False and out["reason"].startswith("unvalidated")


def test_validate_offline_no_prior_confirmation_never_valid(monkeypatch):
    monkeypatch.setattr(s, "_LICENSE_VALIDATION_URL", "https://x/api/validate")
    s._license_cache.clear()
    monkeypatch.setattr(s.httpx, "AsyncClient", _fake_client(raises=True))
    out = asyncio.run(s._validate_license("LK-NEVER-SEEN"))
    assert out["valid"] is False  # offline must never invent a valid license


def test_validate_expired_verdict_not_resurrected_by_grace(monkeypatch):
    import time

    monkeypatch.setattr(s, "_LICENSE_VALIDATION_URL", "https://x/api/validate")
    s._license_cache.clear()
    now = time.time()
    # last CONFIRMED said INVALID (expired) — grace must not flip it to valid
    s._license_cache["LK-X"] = {
        "valid": False,
        "tier": "free",
        "validated_at": now - 60,
        "expires": now - 1,
    }
    monkeypatch.setattr(s.httpx, "AsyncClient", _fake_client(raises=True))
    out = asyncio.run(s._validate_license("LK-X"))
    assert out["valid"] is False
