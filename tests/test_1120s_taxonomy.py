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
