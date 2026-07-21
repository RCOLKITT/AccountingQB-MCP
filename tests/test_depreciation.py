"""OBBBA depreciation rules, §195 startup costs, JE mechanics, and the
account-resolution / entity-casing API fixes."""

import asyncio
import json
from datetime import timedelta

import respx
from httpx import Response

import accountingqb.server as qb_server

REALM = "9130350000000000"
BASE = f"{qb_server.BASE_URL}/v3/company/{REALM}"
QUERY_URL = f"{BASE}/query"
PREFS_URL = f"{BASE}/preferences"
JE_URL = f"{BASE}/journalentry"


def _prime_ctx(ctx):
    ctx.realm_id = REALM
    ctx.access_token = "tok-1"
    ctx.token_expiry = qb_server._utcnow() + timedelta(hours=1)
    ctx.refresh_token = "rt-1"


ACCOUNTS = [
    {"Id": "50", "Name": "Company Vehicle", "FullyQualifiedName": "Company Vehicle",
     "AccountType": "Fixed Asset", "AccountSubType": "Vehicles", "CurrentBalance": 90000.0},
    {"Id": "51", "Name": "Hotels", "FullyQualifiedName": "Travel:Hotels",
     "AccountType": "Expense", "AccountSubType": "Travel", "CurrentBalance": 0},
    {"Id": "52", "Name": "Checking", "FullyQualifiedName": "Checking",
     "AccountType": "Bank", "AccountSubType": "Checking", "CurrentBalance": 10000.0},
    {"Id": "53", "Name": "Accumulated Depreciation - Company Vehicle",
     "FullyQualifiedName": "Company Vehicle:Accumulated Depreciation - Company Vehicle",
     "AccountType": "Fixed Asset", "AccountSubType": "AccumulatedDepreciation",
     "CurrentBalance": 0},
    {"Id": "54", "Name": "Depreciation Expense", "FullyQualifiedName": "Depreciation Expense",
     "AccountType": "Expense", "AccountSubType": "Depreciation", "CurrentBalance": 0},
]


def _us_dispatcher(request):
    q = request.url.params.get("query", "")
    if "FROM CompanyInfo" in q:
        return Response(200, json={"QueryResponse": {"CompanyInfo": [
            {"CompanyName": "Test Co", "Country": "US"}]}})
    if "FROM Account" in q:
        if "FullyQualifiedName = " in q:
            wanted = q.split("FullyQualifiedName = '")[1].split("'")[0]
            rows = [a for a in ACCOUNTS if a["FullyQualifiedName"] == wanted]
        elif "Name LIKE " in q:
            frag = q.split("Name LIKE '%")[1].split("%'")[0].lower()
            rows = [a for a in ACCOUNTS if frag in a["Name"].lower()]
        else:
            rows = ACCOUNTS
        return Response(200, json={"QueryResponse": {"Account": rows}})
    return Response(200, json={"QueryResponse": {}})


def _us_router(router):
    router.get(QUERY_URL).mock(side_effect=_us_dispatcher)
    router.get(PREFS_URL).mock(return_value=Response(200, json={"Preferences": {
        "TaxPrefs": {"PartnerTaxEnabled": True},
        "CurrencyPrefs": {"MultiCurrencyEnabled": False,
                          "HomeCurrency": {"value": "USD"}},
    }}))


# ---------------------------------------------------------------------------
# Bonus depreciation — OBBBA vs TCJA phase-down
# ---------------------------------------------------------------------------

def test_vehicle_bonus_100_pct_obbba_acquisition(qb_ctx):
    # Heavy SUV acquired after 1/19/2025 -> permanent 100% bonus (the
    # "Escalade" scenario that previously got 40%)
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        result = asyncio.run(qb_server.qb_vehicle_depreciation_calculator(
            purchase_price=100000, purchase_date="2026-03-01",
            business_use_pct=1.0, vehicle_weight_lbs=7000, tax_year="2026"))

    assert "permanent under OBBBA" in result
    # 2026 SUV cap 32,000; remainder 68,000 fully bonused; MACRS yr1 = 0
    assert "$32,000.00" in result
    assert "$68,000.00" in result
    assert "TOTAL FIRST-YEAR DEDUCTION: $100,000.00" in result


def test_vehicle_bonus_phase_down_pre_obbba_acquisition(qb_ctx):
    # Acquired on/before 1/19/2025, placed in service 2025 -> 40%
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        result = asyncio.run(qb_server.qb_vehicle_depreciation_calculator(
            purchase_price=100000, purchase_date="2025-01-10",
            business_use_pct=1.0, vehicle_weight_lbs=7000, tax_year="2025"))

    assert "TCJA phase-down" in result
    assert "40%" in result
    assert "permanent under OBBBA" not in result


def test_vehicle_50_pct_use_gate_no_179_no_bonus(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        result = asyncio.run(qb_server.qb_vehicle_depreciation_calculator(
            purchase_price=100000, purchase_date="2026-03-01",
            business_use_pct=0.5, vehicle_weight_lbs=7000, tax_year="2026"))

    assert "not more than 50%" in result
    assert "Straight-line" in result
    assert "Section 179: " not in result


def test_standard_vehicle_280f_caps_2026(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        result = asyncio.run(qb_server.qb_vehicle_depreciation_calculator(
            purchase_price=80000, purchase_date="2026-03-01",
            business_use_pct=1.0, vehicle_weight_lbs=4500, tax_year="2026"))

    assert "$20,300.00" in result  # 2026 §280F yr1 cap with bonus
    assert "§280F" in result


# ---------------------------------------------------------------------------
# §195 startup costs
# ---------------------------------------------------------------------------

def test_startup_costs_under_50k(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        result = asyncio.run(qb_server.qb_startup_cost_analysis(
            30000, "2026-07-01"))

    # $5,000 immediate; $25,000/180 = $138.89/mo x 6 months = $833.33
    assert "Immediate deduction: **$5,000.00**" in result
    assert "$833.3" in result
    assert "Total 2026 deduction: $5,833.3" in result


def test_startup_costs_phaseout(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        # $52k -> immediate reduced to $3,000
        result = asyncio.run(qb_server.qb_startup_cost_analysis(52000, "2026-01-01"))
        assert "Immediate deduction: **$3,000.00**" in result
        # $60k -> fully phased out
        result2 = asyncio.run(qb_server.qb_startup_cost_analysis(60000, "2026-01-01"))
        assert "Immediate deduction: **$0.00**" in result2
        assert "fully phased out" in result2


# ---------------------------------------------------------------------------
# JE mechanics + API fixes
# ---------------------------------------------------------------------------

def test_je_accepts_fully_qualified_account_name(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        post = router.post(JE_URL).mock(return_value=Response(200, json={
            "JournalEntry": {"Id": "77", "TotalAmt": 100.0}}))

        result = asyncio.run(qb_server.qb_create_journal_entry(
            "2026-06-30",
            '[{"account_name": "Travel:Hotels", "amount": 100, "type": "Debit"},'
            ' {"account_name": "Checking", "amount": 100, "type": "Credit"}]'))

    assert "Journal entry created" in result
    body = json.loads(post.calls[0].request.content)
    assert body["Line"][0]["JournalEntryLineDetail"]["AccountRef"]["value"] == "51"


def test_je_blocks_depreciation_credit_to_asset(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        post = router.post(JE_URL).mock(return_value=Response(200, json={}))

        result = asyncio.run(qb_server.qb_create_journal_entry(
            "2026-06-30",
            '[{"account_name": "Depreciation Expense", "amount": 5000, "type": "Debit"},'
            ' {"account_name": "Company Vehicle", "amount": 5000, "type": "Credit",'
            '  "description": "Annual depreciation"}]'))

    assert "qb_record_depreciation" in result
    assert "cost basis" in result
    assert post.called is False


def test_record_depreciation_uses_contra_account(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)
        post = router.post(JE_URL).mock(return_value=Response(200, json={
            "JournalEntry": {"Id": "78"}}))

        result = asyncio.run(qb_server.qb_record_depreciation(
            "Company Vehicle", 5000, "2026-12-31"))

    assert "Depreciation recorded" in result
    body = json.loads(post.calls[0].request.content)
    credit = [l for l in body["Line"]
              if l["JournalEntryLineDetail"]["PostingType"] == "Credit"][0]
    # Credits the AccumulatedDepreciation contra (Id 53), not the asset (50)
    assert credit["JournalEntryLineDetail"]["AccountRef"]["value"] == "53"
    assert "cost basis untouched" in result


def test_record_depreciation_requires_cost_basis(qb_ctx):
    _prime_ctx(qb_ctx)
    zero_basis = [dict(a, CurrentBalance=0.0) if a["Id"] == "50" else a for a in ACCOUNTS]

    def dispatcher(request):
        q = request.url.params.get("query", "")
        if "FROM CompanyInfo" in q:
            return Response(200, json={"QueryResponse": {"CompanyInfo": [
                {"CompanyName": "Test Co", "Country": "US"}]}})
        if "FROM Account" in q:
            frag = q.split("LIKE '%")[1].split("%'")[0].lower() if "LIKE" in q else ""
            rows = [a for a in zero_basis if frag in a["Name"].lower()]
            return Response(200, json={"QueryResponse": {"Account": rows}})
        return Response(200, json={"QueryResponse": {}})

    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=dispatcher)
        result = asyncio.run(qb_server.qb_record_depreciation(
            "Company Vehicle", 5000, "2026-12-31"))

    assert "no cost basis" in result


def test_qb_read_lowercases_entity_path(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        route = router.get(f"{BASE}/journalentry/9").mock(
            return_value=Response(200, json={"JournalEntry": {"Id": "9",
                                                              "SyncToken": "0"}}))
        result = asyncio.run(qb_server.qb_read("JournalEntry", "9"))

    assert route.called
    assert result["JournalEntry"]["Id"] == "9"


def test_1099_report_runs_in_demo_and_carries_footer(qb_ctx):
    # Regression: footer once referenced an unbound 'year' variable and the
    # tool crashed for every caller (no test covered it).
    _prime_ctx(qb_ctx)
    qb_ctx.license_key = "LK-DEMO-REVIEW2026"
    result = asyncio.run(qb_server.qb_1099_contractor_report("2026"))
    assert "TAX_DATA v" in result
    assert "1099" in result


# ---------------------------------------------------------------------------
# v3.5 CPA workbook tools
# ---------------------------------------------------------------------------

def _demo_ctx(qb_ctx):
    _prime_ctx(qb_ctx)
    qb_ctx.license_key = "LK-DEMO-REVIEW2026"


def test_reconciliation_status_demo(qb_ctx):
    _demo_ctx(qb_ctx)
    result = asyncio.run(qb_server.qb_reconciliation_status())
    assert "Reconciliation Status" in result
    assert "Checking" in result and "$47,523.84" in result
    # The honest API-limitation caveat must always ship
    assert "does not expose reconciliation status" in result


def test_comparative_statements_demo_scaling(qb_ctx):
    # Demo serves prior-year values scaled x0.85, so deltas are non-zero
    _demo_ctx(qb_ctx)
    result = asyncio.run(qb_server.qb_comparative_statements("pl"))
    assert "Comparative Profit & Loss" in result
    assert "Δ%" in result or "Δ" in result
    # 187,500 vs 159,375 (=85%) -> +18% swing on Total Income
    assert "$187,500.00" in result and "$159,375.00" in result


def test_comparative_statements_rejects_bad_statement(qb_ctx):
    _demo_ctx(qb_ctx)
    result = asyncio.run(qb_server.qb_comparative_statements("cashflow"))
    assert "must be 'pl'" in result


def test_tax_payments_made_demo_finds_treasury(qb_ctx):
    _demo_ctx(qb_ctx)
    result = asyncio.run(qb_server.qb_tax_payments_made("2026"))
    assert "United States Treasury" in result
    assert "$8,500.00" in result
    assert "Total paid" in result
    assert "IRS online account" in result


def test_owner_draws_demo(qb_ctx):
    _demo_ctx(qb_ctx)
    result = asyncio.run(qb_server.qb_owner_draws(2026))
    assert "Owner's Draws & Contributions" in result
    assert "Owner contribution" in result and "Owner draw" in result
    assert "Net owner activity" in result
    assert "not business expenses" in result


def test_comparative_math_with_mocked_periods(qb_ctx):
    # Non-demo: two distinct mocked report periods -> exact delta math
    _prime_ctx(qb_ctx)
    def reports(request):
        start = request.url.params.get("start_date", "")
        val = "1000.00" if start.startswith("2026") else "500.00"
        return Response(200, json={"Rows": {"Row": [
            {"Summary": {"ColData": [{"value": "Total Income"}, {"value": val}]}},
        ]}})
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{BASE}/reports/ProfitAndLoss").mock(side_effect=reports)
        result = asyncio.run(qb_server.qb_comparative_statements("pl", 2026))
    assert "$1,000.00" in result and "$500.00" in result
    # delta +500 = +100% -> flagged
    assert "+100%" in result and "⚠️" in result
