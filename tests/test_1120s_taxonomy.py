"""Form 1120-S taxonomy (spine of S-corp entity coverage — SPEC-1120S).

The rules that matter:
- classify_account(form="1120s") maps to VERIFIED 1120-S lines (2022 renumbering:
  §179D at 19, Other deductions 20, ordinary income 22).
- Separately-stated items (interest/dividends/charitable/tax-exempt) go to
  Schedule K, NEVER page-1 ordinary income — the defining S-corp mechanic.
- The default form (Schedule C) is byte-for-byte unchanged — adding the 1120-S
  dimension must not move a single sole-prop number.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcpb" / "src"))

from accountingqb.tax_tables import (  # noqa: E402
    _1120S_CATALOG,
    _ACCOUNT_TAXONOMY,
    classify_account,
    line_limitation,
)


def test_page1_mappings_use_verified_line_numbers():
    cases = {
        "SalesOfProductIncome": "1a",
        "DiscountsRefundsGiven": "1b",
        "SuppliesMaterialsCogs": "2",
        "AdvertisingPromotional": "16",  # NOT 8 (that's the Schedule C number)
        "PayrollExpenses": "8",
        "RepairMaintenance": "9",
        "BadDebts": "10",
        "RentOrLeaseOfBuildings": "11",
        "EquipmentRental": "11",
        "TaxesPaid": "12",
        "PayrollTaxExpenses": "12",
        "InterestPaid": "13",
        "Insurance": "20",  # no insurance line on the 1120-S → other deductions
        "Utilities": "20",
        "TravelMeals": "20_meals",
    }
    for subtype, want in cases.items():
        line, _desc, _flags = classify_account("", subtype, "US", form="1120s")
        assert line == want, f"{subtype}: {line} != {want}"


def test_separately_stated_items_leave_ordinary_income():
    # Interest/dividend/charitable/tax-exempt are Schedule K items on an 1120-S —
    # never page-1 income/deductions. classify flags them separately_stated.
    for subtype, want in {
        "InterestEarned": "K4",
        "DividendIncome": "K5a",
        "CharitableContributions": "K12a",
        "TaxExemptInterest": "K16a",
    }.items():
        line, _d, flags = classify_account("", subtype, "US", form="1120s")
        assert line == want and "separately_stated" in flags


def test_scorp_charitable_is_not_nondeductible():
    # Schedule C: charitable is NONDED_170 (a sole prop deducts on Schedule A).
    # 1120-S: it's separately stated (K 12a) and flows to the shareholders.
    line_c, _d, flags_c = classify_account("", "CharitableContributions", "US")
    line_s, _d, flags_s = classify_account(
        "", "CharitableContributions", "US", form="1120s"
    )
    assert line_c == "NONDED_170" and "nondeductible" in flags_c
    assert line_s == "K12a" and "nondeductible" not in flags_s


def test_entertainment_stays_nondeductible_on_1120s():
    line, _d, flags = classify_account("", "Entertainment", "US", form="1120s")
    assert line == "NONDED_274" and "nondeductible" in flags


def test_default_form_unchanged():
    # Backward compatibility: no form → identical Schedule C behavior.
    assert classify_account("", "TravelMeals", "US")[0] == "24b"
    assert classify_account("", "AdvertisingPromotional", "US")[0] == "8"
    assert classify_account("", "PayrollExpenses", "US")[0] == "26"
    # The COGS subtypes added for the 1120-S have no "us" key — Schedule C
    # still falls through to the name fallback / catch-all exactly as before.
    assert classify_account("", "SuppliesMaterialsCogs", "US")[0] == "27a"
    # And CA untouched.
    assert classify_account("", "TravelMeals", "CA")[0] == "8523"


def test_name_fallback_translated_to_1120s_lines():
    # No subtype (name-only accounts) — same patterns, 1120-S targets.
    assert classify_account("Advertising", "", "US", form="1120s")[0] == "16"
    assert classify_account("Wages", "", "US", form="1120s")[0] == "8"
    assert classify_account("Business meals", "", "US", form="1120s")[0] == "20_meals"
    assert classify_account("State taxes", "", "US", form="1120s")[0] == "12"
    assert classify_account("Mystery expense", "", "US", form="1120s")[0] == "20"


def test_taxonomy_targets_exist_in_the_1120s_catalog():
    # The taxonomy may only target lines the authoritative catalog defines
    # (mirror of the Schedule C gate) — a typo'd line id can't ship.
    for subtype, mapping in _ACCOUNT_TAXONOMY.items():
        line = mapping.get("us_1120s")
        if line:
            assert line in _1120S_CATALOG, f"{subtype} → {line} not in catalog"


def test_meals_limitation_on_1120s_line():
    factor, cite = line_limitation("20_meals", "US")
    assert factor == 0.50 and "274(n)" in cite
    # And the plain other-deductions line is fully deductible.
    assert line_limitation("20", "US") == (1.0, "")


def test_no_home_8829_flag_on_1120s():
    # Form 8829 is a sole-proprietor form; an S-corp home office is an
    # accountable-plan reimbursement, so the 8829 review flag must not fire.
    _l, _d, flags = classify_account("Home office utilities", "", "US", form="1120s")
    assert "home_8829" not in flags
    # ...but still fires on Schedule C.
    _l, _d, flags_c = classify_account("Home office utilities", "", "US")
    assert "home_8829" in flags_c


# --- entity declaration (PR B) — stored in the taxpayer profile ---------------

import asyncio  # noqa: E402

import accountingqb.server as s  # noqa: E402


def _profile_patch(monkeypatch):
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
    return saved


def test_entity_declaration_persists_and_renders(monkeypatch):
    saved = _profile_patch(monkeypatch)
    out = asyncio.run(
        s.qb_allocation_profile(
            tax_year=2026,
            entity_type="s_corp",
            shareholders_json='[{"name":"Ryan","ownership_pct":0.6},{"name":"Ava","ownership_pct":0.4}]',
            officer_comp_accounts_json='["Officer Wages"]',
            distribution_accounts_json='["Shareholder Distributions"]',
        )
    )
    assert "saved" in out.lower()
    ent = saved["entity"]
    assert ent["type"] == "s_corp"
    assert [x["ownership_pct"] for x in ent["shareholders"]] == [0.6, 0.4]
    assert ent["officer_comp_accounts"] == ["Officer Wages"]
    assert ent["distribution_accounts"] == ["Shareholder Distributions"]
    assert "S corporation" in out and "60.00%" in out
    assert "1120-S line 7" in out and "Sch K 16d" in out


def test_ownership_must_sum_to_exactly_one(monkeypatch):
    _profile_patch(monkeypatch)
    out = asyncio.run(
        s.qb_allocation_profile(
            tax_year=2026,
            shareholders_json='[{"name":"A","ownership_pct":0.5},{"name":"B","ownership_pct":0.4}]',
        )
    )
    # Never pro-rated silently: K-1 allocations are exact or refused.
    assert "sum to exactly 1.0" in out and "never auto-scaled" in out


def test_bad_entity_type_rejected(monkeypatch):
    _profile_patch(monkeypatch)
    out = asyncio.run(s.qb_allocation_profile(tax_year=2026, entity_type="c_corp"))
    assert "sole_prop" in out and "s_corp" in out


# --- qb_form_1120s_summary (PR C) — golden numbers ----------------------------


def _pl_fixture():
    """Synthetic S-corp P&L:
    Income: Sales 200,000; Refunds -5,000; Interest income 1,000 (K4);
            Muni interest 500 (K16a, tax-exempt)
    COGS: Materials 40,000
    Expenses: Officer Wages 60,000 (declared officer comp → line 7);
              Staff Wages 30,000 (line 8); Rent 12,000 (line 11);
              Meals 4,000 (50% → 2,000 ded, 2,000 → K16c);
              Entertainment 1,000 (NONDED_274 → K16c);
              Charity 2,000 (K12a separately stated)
    Book income = 195,500(+1,500 K/exempt inc) ... computed below."""

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
                section(
                    "Income",
                    [leaf("Sales", 200000.0), leaf("Refunds given", -5000.0)],
                ),
                section("Cost of Goods Sold", [leaf("Materials", 40000.0)]),
                section(
                    "Expenses",
                    [
                        leaf("Officer Wages", 60000.0),
                        leaf("Staff Wages", 30000.0),
                        leaf("Rent", 12000.0),
                        leaf("Business meals", 4000.0),
                        leaf("Client entertainment", 1000.0),
                        leaf("Charitable donations", 2000.0),
                    ],
                ),
                section(
                    "Other Income",
                    [
                        leaf("Interest income", 1000.0),
                        leaf("Muni bond interest", 500.0),
                    ],
                ),
            ]
        }
    }


def _patch_1120s(monkeypatch, subtypes=None):
    async def fake_request(method, endpoint, **kw):
        if "ProfitAndLoss" in endpoint:
            return _pl_fixture()
        if "GeneralLedger" in endpoint:
            # Distribution account activity: two draws of -15,000 (equity debits).
            return {
                "Columns": {
                    "Column": [
                        {
                            "ColType": "tx_date",
                            "MetaData": [{"Name": "ColKey", "Value": "tx_date"}],
                        },
                        {
                            "ColType": "amount",
                            "MetaData": [
                                {"Name": "ColKey", "Value": "subt_nat_amount"}
                            ],
                        },
                    ]
                },
                "Rows": {
                    "Row": [
                        {
                            "Header": {
                                "ColData": [{"value": "Shareholder Distributions"}]
                            },
                            "Rows": {
                                "Row": [
                                    {
                                        "ColData": [
                                            {"value": "2026-03-01"},
                                            {"value": "-15000"},
                                        ]
                                    },
                                    {
                                        "ColData": [
                                            {"value": "2026-09-01"},
                                            {"value": "-15000"},
                                        ]
                                    },
                                ]
                            },
                        }
                    ]
                },
            }
        return {}

    async def fake_query_all(q, **kw):
        if "FROM Account" in q:
            return {
                "QueryResponse": {
                    "Account": [
                        {
                            "Id": "77",
                            "Name": "Shareholder Distributions",
                            "AccountType": "Equity",
                        }
                    ]
                }
            }
        return {"QueryResponse": {}}

    async def fake_chart():
        return (
            subtypes
            or {
                "Sales": "SalesOfProductIncome",
                "Refunds given": "DiscountsRefundsGiven",
                "Materials": "SuppliesMaterialsCogs",
                "Interest income": "InterestEarned",
                "Muni bond interest": "TaxExemptInterest",
                "Staff Wages": "PayrollExpenses",
                "Officer Wages": "PayrollExpenses",
                "Rent": "RentOrLeaseOfBuildings",
                "Business meals": "TravelMeals",
                "Client entertainment": "Entertainment",
                "Charitable donations": "CharitableContributions",
            },
            {},
        )

    async def fake_profile(year):
        return {
            "entity": {
                "type": "s_corp",
                "shareholders": [
                    {"name": "Ryan", "ownership_pct": 0.6},
                    {"name": "Ava", "ownership_pct": 0.4},
                ],
                "officer_comp_accounts": ["Officer Wages"],
                "distribution_accounts": ["Shareholder Distributions"],
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


def test_1120s_golden_numbers(monkeypatch):
    _patch_1120s(monkeypatch)
    out = asyncio.run(s.qb_form_1120s_summary("2026"))
    # Page 1: 200,000 − 5,000 returns − 40,000 COGS = 155,000 total income.
    assert "Line 1a — Gross receipts or sales: $200,000.00" in out
    assert "Line 1b — Returns and allowances: $5,000.00" in out
    assert "Line 2 — Cost of goods sold: $40,000.00" in out
    assert "Line 6 — Total income: $155,000.00" in out
    # Officer comp pulled OUT of wages by declaration.
    assert "Line 7 — Compensation of officers: $60,000.00" in out
    assert "Line 8 — Salaries and wages: $30,000.00" in out
    assert "Line 11 — Rents: $12,000.00" in out
    # Meals at 50%: deductions = 60k+30k+12k+2k = 104,000 → ordinary 51,000.
    assert "Line 21 — Total deductions: $104,000.00" in out
    assert "Line 22 — Ordinary business income (loss): $51,000.00" in out
    # Separately stated: interest K4, muni K16a, charity K12a — never in page 1.
    assert "Interest income (separately stated): $1,000.00" in out
    assert "Tax-exempt interest income: $500.00" in out
    assert "Charitable contributions" in out and "$2,000.00" in out
    # Nondeductible (K16c): 2,000 meals disallowed + 1,000 entertainment.
    assert "meals disallowed ($2,000.00" in out
    assert "Client entertainment ($1,000.00)" in out
    # Distributions from the declared equity account: 30,000 out.
    assert "Item 16d — Distributions: $30,000.00" in out
    # M-1 ties: book 47,500 (196.5k inc − 40k COGS − 109k exp) + 3,000 nonded
    # − 500 exempt = 50,000 = 51,000 ordinary + 1,000 K income − 2,000 K charity.
    assert "Net income per books: $47,500.00" in out
    assert "✅ Ties out." in out
    # K-1 pro-rata (60/40 of 51,000 ordinary; 30,000 distributions).
    assert "Ryan (60.00%)" in out and "$30,600.00" in out
    assert "Ava (40.00%)" in out and "$20,400.00" in out
    assert "distributions $18,000.00" in out and "distributions $12,000.00" in out
    # Reasonable comp: 60k comp vs 30k distributions → no automatic flag.
    assert "No automatic flag" in out


def test_1120s_requires_entity_declaration(monkeypatch):
    _patch_1120s(monkeypatch)

    async def no_entity(year):
        return {}

    monkeypatch.setattr(s, "_get_allocation_profile", no_entity)
    out = asyncio.run(s.qb_form_1120s_summary("2026"))
    assert "never guessed" in out and "entity_type='s_corp'" in out
    assert "Line 22" not in out  # no numbers produced without the declaration


def test_1120s_reasonable_comp_flags_zero_salary(monkeypatch):
    _patch_1120s(monkeypatch)

    async def zero_comp_profile(year):
        return {
            "entity": {
                "type": "s_corp",
                "shareholders": [{"name": "Ryan", "ownership_pct": 1.0}],
                "officer_comp_accounts": [],  # nothing declared as officer comp
                "distribution_accounts": ["Shareholder Distributions"],
            }
        }

    monkeypatch.setattr(s, "_get_allocation_profile", zero_comp_profile)
    out = asyncio.run(s.qb_form_1120s_summary("2026"))
    assert "HIGH RISK" in out and "Rev. Rul. 74-44" in out
    # And never invents a salary figure.
    assert "correct" not in out.split("HIGH RISK")[1][:400].lower()
