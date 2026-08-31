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
            assert (
                us in tt._SCHEDULE_C_CATALOG
            ), f"{subtype}: US line {us} not in catalog"
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
    common = [
        "AdvertisingPromotional",
        "Auto",
        "Insurance",
        "InterestPaid",
        "LegalProfessionalFees",
        "OfficeExpenses",
        "RentOrLeaseOfBuildings",
        "RepairMaintenance",
        "Travel",
        "TravelMeals",
        "Utilities",
        "SuppliesMaterials",
        "PayrollExpenses",
        "SalesOfProductIncome",
        "DiscountsRefundsGiven",
        "InterestEarned",
    ]
    for st in common:
        for juris, catalog in (
            ("US", tt._SCHEDULE_C_CATALOG),
            ("CA", tt._T2125_CATALOG),
        ):
            line, desc, flags = s.classify_account("x", st, juris)
            assert line in catalog, f"{st}/{juris} -> {line} not in catalog"


def test_unknown_falls_to_catch_all():
    assert s.classify_account("Zorp Widget 9000", None, "US")[0] == "27a"
    assert s.classify_account("Zorp Widget 9000", None, "CA")[0] == "9270"


# ---- Semantic corrections (the number-movers) -------------------------------


def test_entertainment_nondeductible_us_only():
    us_line, _d, us_flags = s.classify_account(
        "Client Entertainment", "Entertainment", "US"
    )
    assert us_line == "NONDED_274" and "nondeductible" in us_flags
    ca_line, _d2, _f2 = s.classify_account(
        "Client Entertainment", "Entertainment", "CA"
    )
    assert ca_line == "8523"  # CA: 50% deductible (ITA 67.1)


def test_charitable_nondeductible():
    # Sole-prop charitable contributions: not a Schedule C deduction (§170).
    line, desc, flags = s.classify_account(
        "Contributions to charities", "CharitableContributions", "US"
    )
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


def test_three_bucket_reconciliation():
    # With statutory limits there are THREE buckets, and nothing may be dropped:
    # deductible + statutorily-disallowed + non-deductible == all P&L expenses.
    expenses = {
        "Advertising": 100.0,
        "Client Entertainment": 40.0,
        "Business meals": 200.0,
        "Rent": 1200.0,
        "Mystery Account": 15.0,
    }
    sc = s._map_expenses_to_schedule_c(expenses, {})["lines"]
    deductible = sum(d["deductible"] for d in sc.values() if not d.get("nondeductible"))
    disallowed = sum(
        d["amount"] - d["deductible"] for d in sc.values() if not d.get("nondeductible")
    )
    nondeduct = sum(d["amount"] for d in sc.values() if d.get("nondeductible"))
    assert round(deductible + disallowed + nondeduct, 2) == round(
        sum(expenses.values()), 2
    )
    assert round(nondeduct, 2) == 40.0  # entertainment excluded from Line 28
    meals = next(d for k, d in sc.items() if "24b" in k)
    assert round(meals["deductible"], 2) == 100.0  # 200 × 50% (§274(n))
    assert round(meals["amount"], 2) == 200.0  # full amount retained (nothing dropped)


def test_meals_statutory_limit():
    import accountingqb.tax_tables as tt

    assert tt.line_limitation("24b", "US") == (0.50, "IRC §274(n)")
    assert tt.line_limitation("8523", "CA")[0] == 0.50  # ITA s.67.1
    assert tt.line_limitation("8", "US") == (1.0, "")  # advertising: no limit
    # STATUTORY_LIMITS is in the ledgered control plane
    assert "STATUTORY_LIMITS" in tt.TABLES


def test_parent_posted_amounts_not_dropped():
    # A parent account carrying a DIRECT balance plus children — the amount
    # posted straight to the parent (696.17) must not vanish from Line 24a.
    pl = {
        "Rows": {
            "Row": [
                {
                    "Header": {"ColData": [{"value": "Expenses"}]},
                    "Rows": {
                        "Row": [
                            {
                                "Header": {"ColData": [{"value": "Travel"}]},
                                "Rows": {
                                    "Row": [
                                        {
                                            "ColData": [
                                                {"value": "Travel:Hotels"},
                                                {"value": "690.30"},
                                            ]
                                        },
                                        {
                                            "ColData": [
                                                {"value": "Travel:Taxis"},
                                                {"value": "690.94"},
                                            ]
                                        },
                                    ]
                                },
                                "Summary": {
                                    "ColData": [
                                        {"value": "Total Travel"},
                                        {"value": "2077.41"},
                                    ]
                                },
                            },
                        ]
                    },
                    "Summary": {
                        "ColData": [{"value": "Total Expenses"}, {"value": "2077.41"}]
                    },
                },
            ]
        }
    }
    exp = s._extract_pl_expense_accounts(pl)
    assert round(sum(exp.values()), 2) == 2077.41  # nothing dropped
    assert abs(exp.get("Travel", 0) - 696.17) < 0.01  # parent residual
    sc = s._map_expenses_to_schedule_c(exp, {})["lines"]
    line24a = next(d["amount"] for k, d in sc.items() if "24a" in k)
    assert abs(line24a - 2077.41) < 0.01  # full amount, not 1381.24


def test_subtype_beats_name():
    # An account NAMED "advertising" but typed TravelMeals maps by subtype (24b)
    line, _d, _f = s.classify_account("Advertising dinner", "TravelMeals", "US")
    assert line == "24b"


# ---- End-to-end via qb_schedule_c on the demo chart (subtype path live) ------


def test_schedule_c_demo_uses_subtypes():
    # Demo P&L: Advertising (AdvertisingPromotional) -> Line 8; the subtype map
    # is built from DEMO_ACCOUNTS.
    pl = {
        "Rows": {
            "Row": [
                {
                    "Header": {"ColData": [{"value": "Income"}]},
                    "Rows": {
                        "Row": [
                            {
                                "ColData": [
                                    {"value": "Software Revenue"},
                                    {"value": "1000.00"},
                                ]
                            }
                        ]
                    },
                    "Summary": {
                        "ColData": [{"value": "Total Income"}, {"value": "1000.00"}]
                    },
                },
                {
                    "Header": {"ColData": [{"value": "Expenses"}]},
                    "Rows": {
                        "Row": [
                            {
                                "ColData": [
                                    {"value": "Advertising"},
                                    {"value": "300.00"},
                                ]
                            },
                            {"ColData": [{"value": "Rent"}, {"value": "500.00"}]},
                        ]
                    },
                    "Summary": {
                        "ColData": [{"value": "Total Expenses"}, {"value": "800.00"}]
                    },
                },
            ]
        }
    }

    async def fake_req(method, path, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": s.DEMO_ACCOUNTS}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "Demo"}]}}

    fn = getattr(s.qb_schedule_c, "__wrapped__", s.qb_schedule_c)
    with (
        patch.object(s, "qb_request", fake_req),
        patch.object(s, "qb_query_all", fake_all),
        patch.object(s, "qb_query", fake_query),
    ):
        out = asyncio.run(fn("2026"))
    assert "Line 8 — Advertising: $300.00" in out
    assert "Line 20b — Rent" in out and "$500.00" in out
    assert "Line 28 — Total expenses: $800.00" in out


def test_public_tax_data_is_accurate_and_derived():
    """The public /tax-data payload must be built FROM the live registry (never
    hand-typed) so it can't drift, and every highlight must carry a citation."""
    import accountingqb.tax_tables as tt

    d = tt.public_tax_data()
    # meta mirrors the registry exactly
    assert d["version"] == tt.TAX_DATA_VERSION
    assert d["verified"] == tt.TAX_DATA_VERIFIED
    assert d["table_count"] == len(tt.TABLES)
    # ledger chain must verify (a broken chain is a red flag we'd never publish)
    assert d["ledger"]["chain_ok"] is True
    assert d["ledger"]["rows"] == len(tt.load_ledger())
    # highlights: each has a real source; values match the tables (not invented)
    assert d["highlights"], "expected concrete highlight rows"
    for h in d["highlights"]:
        assert h["source"] and h["label"] and h["jurisdiction"] in ("US", "CA")
    meals = next(h for h in d["highlights"] if "meals" in h["label"].lower())
    assert (
        f"{int(round(tt._STATUTORY_LIMITS['meals_us']['factor'] * 100))}%"
        in meals["label"]
    )
    assert meals["source"] == tt._STATUTORY_LIMITS["meals_us"]["cite"]
    # mileage highlight must cite the year it actually shows (no year/source mismatch)
    mil = next((h for h in d["highlights"] if "mileage" in h["label"].lower()), None)
    if mil:
        import re

        yr = re.search(r"\((\d{4})\)", mil["label"]).group(1)
        assert yr in mil["source"], f"mileage cites {mil['source']} but shows {yr}"
    # whole thing must be JSON-serializable
    import json

    json.dumps(d)
