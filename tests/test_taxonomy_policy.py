"""Drift gate + behavior tests for the canonical account-classification taxonomy
(tax_tables._ACCOUNT_TAXONOMY / classify_account). Structural invariants keep the
mappings honest; behavior tests lock the AccountSubType path, the semantic
corrections, and the arithmetic identities a wrong mapping would break."""

import asyncio
from unittest.mock import patch

import accountingqb.tax_tables as tt
import accountingqb.server as s


# ---- Structural gate: every mapping resolves to a real, cited line ----------

def test_taxonomy_targets_exist_in_catalog():
    for subtype, targets in tt._ACCOUNT_TAXONOMY.items():
        us = targets.get("us")
        if us is not None:
            assert us in tt._SCHEDULE_C_CATALOG, f"{subtype}: US line {us} not in catalog"
        ca = targets.get("ca")
        if ca is not None:
            assert ca in tt._T2125_CATALOG, f"{subtype}: CA line {ca} not in catalog"


def test_catalog_lines_are_cited():
    for line, meta in {**tt._SCHEDULE_C_CATALOG, **tt._T2125_CATALOG}.items():
        assert meta.get("desc"), f"{line}: missing desc"
        assert meta.get("authority"), f"{line}: missing authority"
        assert meta.get("cite", "").startswith("http"), f"{line}: missing citation URL"


def test_name_fallback_lines_exist_in_catalog():
    for pat, line in tt._NAME_FALLBACK_US:
        assert line in tt._SCHEDULE_C_CATALOG, f"US fallback -> unknown line {line}"
    for pat, line in tt._NAME_FALLBACK_CA:
        assert line in tt._T2125_CATALOG, f"CA fallback -> unknown line {line}"


def test_common_subtypes_all_classify():
    # A representative set of common QBO subtypes must land on a catalog line
    # in BOTH jurisdictions (no crash, no phantom line).
    common = ["AdvertisingPromotional", "Auto", "Insurance", "InterestPaid",
              "LegalProfessionalFees", "OfficeExpenses", "RentOrLeaseOfBuildings",
              "RepairMaintenance", "Travel", "TravelMeals", "Utilities",
              "SuppliesMaterials", "PayrollExpenses", "SalesOfProductIncome",
              "DiscountsRefundsGiven", "InterestEarned"]
    for st in common:
        for juris, catalog in (("US", tt._SCHEDULE_C_CATALOG), ("CA", tt._T2125_CATALOG)):
            line, desc, flags = s.classify_account("x", st, juris)
            assert line in catalog, f"{st}/{juris} -> {line} not in catalog"


def test_unknown_falls_to_catch_all():
    assert s.classify_account("Zorp Widget 9000", None, "US")[0] == "27a"
    assert s.classify_account("Zorp Widget 9000", None, "CA")[0] == "9270"


# ---- Semantic corrections (the number-movers) -------------------------------

def test_entertainment_nondeductible_us_only():
    us_line, _d, us_flags = s.classify_account("Client Entertainment", "Entertainment", "US")
    assert us_line == "NONDED_274" and "nondeductible" in us_flags
    ca_line, _d2, _f2 = s.classify_account("Client Entertainment", "Entertainment", "CA")
    assert ca_line == "8523"                       # CA: 50% deductible (ITA 67.1)


def test_charitable_nondeductible():
    # Sole-prop charitable contributions: not a Schedule C deduction (§170).
    line, desc, flags = s.classify_account("Contributions to charities",
                                           "CharitableContributions", "US")
    assert line == "NONDED_170" and "nondeductible" in flags and "170" in desc
    # name fallback catches it too
    assert s.classify_account("Charitable donations", None, "US")[0] == "NONDED_170"
    # CA: also excluded from T2125 (claims a T1 credit)
    assert s.classify_account("Charitable donations", None, "CA")[0] == "NONDED"


def test_equipment_lease_20a():
    # subtype is authoritative regardless of name
    assert s.classify_account("Forklift Lease", "EquipmentRental", "US")[0] == "20a"
    # name fallback catches an explicit "equipment lease"; a generic lease -> 20b
    assert s.classify_account("Equipment Lease", None, "US")[0] == "20a"
    assert s.classify_account("Building Lease", None, "US")[0] == "20b"


def test_subcontractor_ca_8340_us_11():
    assert s.classify_account("Subcontractor costs", None, "CA")[0] == "8340"
    assert s.classify_account("Subcontractor costs", None, "US")[0] == "11"


def test_ca_word_boundary_no_substring_collision():
    # "overdue" must NOT hit the CA "due" -> 8760 rule (the old naive-substring bug)
    line, _d, _f = s.classify_account("Overdue balance writeoff", None, "CA")
    assert line != "8760"


# ---- Arithmetic invariant: nothing dropped; deductible + nondeductible = P&L -

def test_expense_mapping_conserves_total():
    expenses = {"Advertising": 100.0, "Client Entertainment": 40.0,
                "Rent": 1200.0, "Mystery Account": 15.0}
    sc = s._map_expenses_to_schedule_c(expenses, {})
    deductible = sum(d["amount"] for d in sc.values() if not d.get("nondeductible"))
    nondeduct = sum(d["amount"] for d in sc.values() if d.get("nondeductible"))
    assert round(deductible + nondeduct, 2) == round(sum(expenses.values()), 2)
    assert round(nondeduct, 2) == 40.0             # entertainment excluded from Line 28


def test_parent_posted_amounts_not_dropped():
    # A parent account carrying a DIRECT balance plus children — the amount
    # posted straight to the parent (696.17) must not vanish from Line 24a.
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"Header": {"ColData": [{"value": "Travel"}]},
              "Rows": {"Row": [
                  {"ColData": [{"value": "Travel:Hotels"}, {"value": "690.30"}]},
                  {"ColData": [{"value": "Travel:Taxis"}, {"value": "690.94"}]}]},
              "Summary": {"ColData": [{"value": "Total Travel"}, {"value": "2077.41"}]}},
         ]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "2077.41"}]}},
    ]}}
    exp = s._extract_pl_expense_accounts(pl)
    assert round(sum(exp.values()), 2) == 2077.41            # nothing dropped
    assert abs(exp.get("Travel", 0) - 696.17) < 0.01          # parent residual
    sc = s._map_expenses_to_schedule_c(exp, {})
    line24a = next(d["amount"] for k, d in sc.items() if "24a" in k)
    assert abs(line24a - 2077.41) < 0.01                      # full amount, not 1381.24


def test_subtype_beats_name():
    # An account NAMED "advertising" but typed TravelMeals maps by subtype (24b)
    line, _d, _f = s.classify_account("Advertising dinner", "TravelMeals", "US")
    assert line == "24b"


# ---- End-to-end via qb_schedule_c on the demo chart (subtype path live) ------

def test_schedule_c_demo_uses_subtypes():
    # Demo P&L: Advertising (AdvertisingPromotional) -> Line 8; the subtype map
    # is built from DEMO_ACCOUNTS.
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Software Revenue"}, {"value": "1000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "1000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Advertising"}, {"value": "300.00"}]},
                          {"ColData": [{"value": "Rent"}, {"value": "500.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "800.00"}]}},
    ]}}

    async def fake_req(method, path, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": s.DEMO_ACCOUNTS}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "Demo"}]}}

    fn = getattr(s.qb_schedule_c, "__wrapped__", s.qb_schedule_c)
    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query):
        out = asyncio.run(fn("2026"))
    assert "Line 8 — Advertising: $300.00" in out
    assert "Line 20b — Rent" in out and "$500.00" in out
    assert "Line 28 — Total expenses: $800.00" in out
