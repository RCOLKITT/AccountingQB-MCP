"""Form 1065 partnership workpaper — mirrors the 1120-S engine with the
partnership mechanics: guaranteed payments at line 10, Sch K at 5/6a/13a/18a/
18c/19a, guaranteed payments NEVER allocated pro-rata (they follow the
agreement, not ownership)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcpb" / "src"))

import accountingqb.server as s  # noqa: E402
from accountingqb.tax_tables import _1065_CATALOG, _ACCOUNT_TAXONOMY  # noqa: E402
from accountingqb.tax_tables import classify_account, line_limitation  # noqa: E402


def test_1065_taxonomy_verified_lines():
    cases = {
        "SalesOfProductIncome": "1a",
        "SuppliesMaterialsCogs": "2",
        "PayrollExpenses": "9",
        "RepairMaintenance": "11",
        "BadDebts": "12",
        "RentOrLeaseOfBuildings": "13",
        "TaxesPaid": "14",
        "InterestPaid": "15",
        "AdvertisingPromotional": "21",  # no advertising line on the 1065
        "TravelMeals": "21_meals",
        "InterestEarned": "K5",
        "DividendIncome": "K6a",
        "CharitableContributions": "K13a",
        "TaxExemptInterest": "K18a",
    }
    for subtype, want in cases.items():
        line, _d, _f = classify_account("", subtype, "US", form="1065")
        assert line == want, f"{subtype}: {line} != {want}"
    # catalog gate: every us_1065 target must exist in the authoritative catalog
    for subtype, mapping in _ACCOUNT_TAXONOMY.items():
        t = mapping.get("us_1065")
        if t:
            assert t in _1065_CATALOG, f"{subtype} → {t} not in catalog"
    assert line_limitation("21_meals", "US") == (0.50, "IRC §274(n)")
    # Schedule C / 1120-S untouched
    assert classify_account("", "TravelMeals", "US")[0] == "24b"
    assert classify_account("", "TravelMeals", "US", form="1120s")[0] == "20_meals"


def _pl_fixture():
    """Partnership book: Sales 100,000; Materials (COGS) 20,000;
    GP to partners 24,000 (declared); Staff wages 10,000; Rent 6,000;
    Meals 2,000 (→1,000 ded); Charity 1,000 (K13a); Interest income 500 (K5)."""

    def leaf(name, amt):
        return {"ColData": [{"value": name}, {"value": str(amt)}]}

    def section(title, leaves):
        return {
            "Header": {"ColData": [{"value": title}]},
            "Rows": {"Row": leaves},
            "Summary": {
                "ColData": [
                    {"value": f"Total {title}"},
                    {
                        "value": str(
                            sum(float(l["ColData"][1]["value"]) for l in leaves)
                        )
                    },
                ]
            },
        }

    return {
        "Rows": {
            "Row": [
                section("Income", [leaf("Sales", 100000.0)]),
                section("Cost of Goods Sold", [leaf("Materials", 20000.0)]),
                section(
                    "Expenses",
                    [
                        leaf("Guaranteed Payments", 24000.0),
                        leaf("Staff Wages", 10000.0),
                        leaf("Rent", 6000.0),
                        leaf("Business meals", 2000.0),
                        leaf("Charitable donations", 1000.0),
                    ],
                ),
                section("Other Income", [leaf("Interest income", 500.0)]),
            ]
        }
    }


def _patch(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        if "ProfitAndLoss" in endpoint:
            return _pl_fixture()
        if "GeneralLedger" in endpoint:
            return {"Rows": {"Row": []}}  # no distribution activity
        return {}

    async def fake_query_all(q, **kw):
        if "FROM Account" in q:
            return {
                "QueryResponse": {
                    "Account": [
                        {
                            "Id": "9",
                            "Name": "Partner Distributions",
                            "AccountType": "Equity",
                        }
                    ]
                }
            }
        return {"QueryResponse": {}}

    async def fake_chart():
        return (
            {
                "Sales": "SalesOfProductIncome",
                "Materials": "SuppliesMaterialsCogs",
                "Interest income": "InterestEarned",
                "Staff Wages": "PayrollExpenses",
                "Guaranteed Payments": "",  # name-only; declaration routes it
                "Rent": "RentOrLeaseOfBuildings",
                "Business meals": "TravelMeals",
                "Charitable donations": "CharitableContributions",
            },
            {},
        )

    async def fake_profile(year):
        return {
            "entity": {
                "type": "partnership",
                "shareholders": [
                    {"name": "Pat", "ownership_pct": 0.5},
                    {"name": "Sam", "ownership_pct": 0.5},
                ],
                "guaranteed_payment_accounts": ["Guaranteed Payments"],
                "distribution_accounts": ["Partner Distributions"],
            }
        }

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_chart_maps", fake_chart)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_profile)
    monkeypatch.setattr(s, "_get_region", fake_region)


def test_1065_golden_numbers(monkeypatch):
    _patch(monkeypatch)
    out = asyncio.run(s.qb_form_1065_summary("2026"))
    # Total income: 100,000 − 20,000 COGS = 80,000.
    assert "Line 8 — Total income: $80,000.00" in out
    # Guaranteed payments split to line 10 by declaration.
    assert "Line 10 — Guaranteed payments to partners: $24,000.00" in out
    assert "Line 9 — Salaries and wages (other than to partners): $10,000.00" in out
    assert "Line 13 — Rent: $6,000.00" in out
    # Deductions: 24k + 10k + 6k + 1k meals = 41,000 → ordinary 39,000.
    assert "Line 22 — Total deductions: $41,000.00" in out
    assert "Line 23 — Ordinary business income (loss): $39,000.00" in out
    # Sch K: interest K5, charity K13a, meals disallowed → 18c.
    assert "Interest income (separately stated): $500.00" in out
    assert "Charitable contributions" in out and "$1,000.00" in out
    assert "meals disallowed ($1,000.00" in out
    # M-1: book 37,500 + 1,000 nonded − 0 = 38,500 = 39,000 + 500 − 1,000. Ties.
    assert "Net income per books: $37,500.00" in out
    assert "✅ Ties out." in out
    # K-1 pro-rata 50/50 of ordinary; GP explicitly NOT pro-rata.
    assert "Pat (50.00%)" in out and "$19,500.00" in out
    assert "NOT allocated" in out and "partnership agreement" in out
    # Advisory present.
    assert "Partners are NOT employees" in out


def test_1065_requires_declaration(monkeypatch):
    _patch(monkeypatch)

    async def no_entity(year):
        return {}

    monkeypatch.setattr(s, "_get_allocation_profile", no_entity)
    out = asyncio.run(s.qb_form_1065_summary("2026"))
    assert "never guessed" in out and "entity_type='partnership'" in out
    assert "Line 23" not in out


def test_partnership_entity_declaration(monkeypatch):
    saved = {}

    async def fake_save(year, profile):
        saved.clear()
        saved.update(profile)
        return True

    async def fake_get(year):
        return dict(saved)

    async def fake_chart():
        return {}

    monkeypatch.setattr(s, "_save_allocation_profile", fake_save)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_get)
    monkeypatch.setattr(s, "_account_subtype_map", fake_chart)
    out = asyncio.run(
        s.qb_allocation_profile(
            tax_year=2026,
            entity_type="partnership",
            shareholders_json='[{"name":"Pat","ownership_pct":0.5},{"name":"Sam","ownership_pct":0.5}]',
            guaranteed_payment_accounts_json='["Guaranteed Payments"]',
        )
    )
    assert "saved" in out.lower()
    assert saved["entity"]["type"] == "partnership"
    assert saved["entity"]["guaranteed_payment_accounts"] == ["Guaranteed Payments"]
    assert "Partnership / multi-member LLC" in out
    assert "1065 line 10" in out
