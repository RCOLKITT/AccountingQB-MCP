"""Taxpayer allocation layer: profile set/get + validation, the classify→allocate
→limit order, both vehicle methods, and Form 8829 (Line 30) with the gross-income
limit + carryforward. Golden numbers stay put when NO profile exists (100% + warn)."""

import asyncio
from unittest.mock import patch

import accountingqb.server as s


def _tool(fn):
    return getattr(fn, "__wrapped__", fn)


# ---- profile round-trip + validation (mocked in-memory store) ---------------

def _store_patches(monkeypatch, store):
    async def fake_get(year):
        return store.get(int(year), {})

    async def fake_save(year, profile):
        store[int(year)] = profile
        return True

    async def fake_chart():
        return {"Internet & TV": "Utilities"}

    monkeypatch.setattr(s, "_get_allocation_profile", fake_get)
    monkeypatch.setattr(s, "_save_allocation_profile", fake_save)
    monkeypatch.setattr(s, "_account_subtype_map", fake_chart)


def test_profile_set_derives_and_get(monkeypatch):
    store = {}
    _store_patches(monkeypatch, store)
    fn = _tool(s.qb_allocation_profile)
    out = asyncio.run(fn(
        2025, home_office_sqft=300, home_sqft=2400,
        vehicle_method="actual", business_miles=6500, total_miles=10000,
        account_allocations_json='{"Internet & TV": 0.6}', source="CPA Form 8829 TY2025"))
    assert "saved" in out.lower()
    p = store[2025]
    assert p["home_office"]["percentage"] == 0.125          # 300/2400 derived
    assert p["vehicle"]["percentage"] == 0.65               # 6500/10000 derived
    assert p["vehicle"]["method"] == "actual"
    assert p["account_allocations"]["Internet & TV"]["percentage"] == 0.6
    assert p["provenance"]["source"] == "CPA Form 8829 TY2025" and p["provenance"]["set_at"]
    # GET renders it back
    got = asyncio.run(fn(2025))
    assert "Home office" in got and "12.50%" in got and "65.0%" in got


def test_profile_home_office_method(monkeypatch):
    store = {}
    _store_patches(monkeypatch, store)
    fn = _tool(s.qb_allocation_profile)
    # default method is 'actual' when sqft is set
    asyncio.run(fn(2025, home_office_sqft=250, home_sqft=2500))
    assert store[2025]["home_office"]["method"] == "actual"
    # switch to simplified without re-entering sqft (preserved)
    asyncio.run(fn(2025, home_office_method="simplified"))
    assert store[2025]["home_office"]["method"] == "simplified"
    assert store[2025]["home_office"]["office_sqft"] == 250     # preserved
    # invalid method rejected
    bad = asyncio.run(fn(2025, home_office_method="regular"))
    assert "must be 'actual' or 'simplified'" in bad


def test_profile_validation(monkeypatch):
    _store_patches(monkeypatch, {})
    fn = _tool(s.qb_allocation_profile)
    assert "cannot exceed" in asyncio.run(fn(2025, home_office_sqft=3000, home_sqft=2400))
    assert "standard_mileage" in asyncio.run(
        fn(2025, vehicle_method="bogus", business_miles=1, total_miles=2))
    assert "between 0 and 1" in asyncio.run(
        fn(2025, account_allocations_json='{"Internet & TV": 1.5}'))


def test_empty_profile_message(monkeypatch):
    _store_patches(monkeypatch, {})
    out = asyncio.run(_tool(s.qb_allocation_profile)(2025))
    assert "No profile set" in out and "100%" in out


# ---- allocation resolution + Form 8829 unit ---------------------------------

def test_account_alloc_treatments():
    prof = {"vehicle": {"method": "standard_mileage"},
            "account_allocations": {"Net": {"percentage": 0.4}}}
    assert s._account_alloc("Auto", "9", [], prof)[0] == "mileage_excluded"
    assert s._account_alloc("Auto", "9", [], {"vehicle": {"method": "actual", "percentage": 0.7}})[:2] == ("line", 0.7)
    assert s._account_alloc("Home Office", "18", ["home_8829"], prof)[0] == "home_indirect"
    assert s._account_alloc("Net", "25", [], prof)[:2] == ("line", 0.4)
    assert s._account_alloc("Other", "25", [], prof)[:2] == ("line", 1.0)


def test_home_indirect_detected_by_fqn_parent_chain():
    """A leaf named 'Property taxes' (classifies to Line 23) whose FQN is under a
    'Home office' parent must route to Form 8829, not Line 23 at 100%."""
    expenses = {"Property taxes": 1115.84, "Advertising": 500.0}
    fqn = {"Property taxes": "Home office:Property taxes", "Advertising": "Advertising"}
    res = s._map_expenses_to_schedule_c(expenses, {}, {}, fqn)
    home = {n for n, _ in res["home_indirect"]}
    assert "Property taxes" in home          # routed to 8829 by parent chain
    assert not any("23" in b["line"] for b in res["lines"].values())  # not on Line 23


def test_home_indirect_designated_by_profile():
    """An account the taxpayer explicitly designates (e.g. a standalone
    'Electricity' that's really a home cost) routes to Form 8829, even with no
    'home' in the name or parent chain."""
    prof = {"home_office": {"percentage": 0.125, "accounts": ["Electricity"]}}
    res = s._map_expenses_to_schedule_c({"Electricity": 317.0}, {}, prof, {})
    assert ("Electricity", 317.0) in res["home_indirect"]


def test_form8829_income_limit_and_carryforward():
    assert s._form8829(4000, 0.125, 16950) == (500.0, 0.0, 500.0)     # within profit
    allowed, carry, tentative = s._form8829(4000, 0.50, 1200)          # exceeds profit
    assert allowed == 1200.0 and carry == 800.0 and tentative == 2000.0
    allowed, carry, _ = s._form8829(4000, 0.50, -500)                  # a loss: none allowed
    assert allowed == 0.0 and carry == 2000.0


# ---- vehicle standard mileage end-to-end ------------------------------------

def test_standard_mileage_replaces_actual():
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "40000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "40000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Auto expenses"}, {"value": "3000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "3000.00"}]}},
    ]}}
    accts = [{"Name": "Auto expenses", "AccountSubType": "Auto", "FullyQualifiedName": "Auto expenses"}]
    prof = {"vehicle": {"method": "standard_mileage", "business_miles": 8000, "total_miles": 10000}}

    async def req(m, p, params=None, **k):
        return pl

    async def qall(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def qy(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D"}]}}

    async def getprof(y):
        return prof

    with patch.object(s, "qb_request", req), patch.object(s, "qb_query_all", qall), \
            patch.object(s, "qb_query", qy), patch.object(s, "_get_allocation_profile", getprof):
        out = asyncio.run(_tool(s.qb_schedule_c)("2025"))
    assert "standard mileage" in out
    assert "8,000 business miles × $0.700/mi = $5,600.00" in out
    assert "actual vehicle expenses of $3,000.00 are excluded" in out
    assert "Does not reconcile" not in out
