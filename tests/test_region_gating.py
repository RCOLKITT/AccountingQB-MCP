"""Region-gating invariant — Constitution: "Never Wrong-Jurisdiction Numbers".

A jurisdiction-specific tax tool (US Schedule C, CA T2125, …) must NEVER compute a
number for the wrong country. `require_region` enforces this: on a region mismatch
it returns a ⚠️ refusal string and never runs the tool body (so it never touches
QuickBooks). These tests lock that invariant at the gate level.

The gated-tool set is DISCOVERED from the live module via the `__region_gate__`
marker `require_region` stamps on each wrapper — so a newly added `@require_region`
tool is covered automatically, and *removing* a gate from a critical tool trips the
allowlist check below. This is the regression net for the crown-jewel invariant.
"""

import asyncio

import accountingqb.server as s
import pytest

OPPOSITE = {"US": "CA", "CA": "US"}


def _discover_region_gated():
    """Every module-level tool carrying the require_region marker → (name, region)."""
    found = {}
    for name in dir(s):
        gate = getattr(getattr(s, name), "__region_gate__", None)
        if gate:
            found[name] = gate[0]  # (region, alternative) → region
    return found


REGION_GATED = _discover_region_gated()

# Crown-jewel tools that MUST stay region-gated. If a refactor drops a decorator,
# discovery shrinks and this subset check fails loudly (rather than silently letting
# a US tool run on Canadian books). Kept intentionally small + high-signal.
MUST_BE_GATED = {
    "qb_schedule_c": "US",
    "qb_schedule_c_detailed": "US",
    "qb_form_1120s_summary": "US",
    "qb_form_1065_summary": "US",
    "qb_tax_summary": "US",
    "qb_t2125_summary": "CA",
    "qb_gst_hst_return": "CA",
    "qb_estimate_instalments": "CA",
}


def test_discovery_is_populated():
    # Sanity: the marker mechanism actually finds the gated tools (guards against a
    # silent break where discovery returns nothing → all other tests vacuously pass).
    assert len(REGION_GATED) >= 15, REGION_GATED


def test_crown_jewel_tools_stay_region_gated():
    for tool, region in MUST_BE_GATED.items():
        assert tool in REGION_GATED, f"{tool} lost its region gate!"
        assert (
            REGION_GATED[tool] == region
        ), f"{tool} gated to {REGION_GATED[tool]}, expected {region}"


@pytest.mark.parametrize("tool_name", sorted(REGION_GATED))
def test_wrong_jurisdiction_is_refused_without_fetching(tool_name, monkeypatch):
    """Every gated tool, called on the OPPOSITE region, must refuse with ⚠️ and never
    reach QuickBooks (no numbers computed for the wrong country)."""
    region = REGION_GATED[tool_name]
    wrong = OPPOSITE[region]

    async def fake_region():
        return {"region": wrong}

    def _must_not_fetch(*a, **k):
        raise AssertionError(
            f"{tool_name} touched QuickBooks despite a {region}/{wrong} region "
            f"mismatch — WRONG-JURISDICTION NUMBER RISK"
        )

    monkeypatch.setattr(s, "_get_region", fake_region)
    # If the gate ever fell through, the body would call one of these first.
    for fetch in ("qb_request", "qb_query", "qb_query_all"):
        if hasattr(s, fetch):
            monkeypatch.setattr(s, fetch, _must_not_fetch)

    tool = getattr(s, tool_name)
    result = asyncio.run(tool())  # wrapper is (*args) — no valid args needed to refuse

    assert isinstance(result, str), f"{tool_name} refusal should be a string"
    assert result.startswith("⚠️"), f"{tool_name} did not refuse: {result[:80]!r}"
    assert region in result and wrong in result, result[:120]


def test_matching_region_calls_through():
    """The gate must NOT block the correct region — a US tool runs on US books. Uses a
    synthetic require_region-wrapped function so this needs no QB data mocking."""
    calls = {"n": 0}

    @s.require_region("US", "use the CA tool")
    async def _sample():
        calls["n"] += 1
        return "ran"

    async def us_region():
        return {"region": "US"}

    async def ca_region():
        return {"region": "CA"}

    # Wrong region → refused, body never runs.
    import unittest.mock as mock

    with mock.patch.object(s, "_get_region", ca_region):
        out = asyncio.run(_sample())
    assert out.startswith("⚠️") and calls["n"] == 0

    # Right region → body runs.
    with mock.patch.object(s, "_get_region", us_region):
        out = asyncio.run(_sample())
    assert out == "ran" and calls["n"] == 1
