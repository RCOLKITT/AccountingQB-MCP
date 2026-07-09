"""Phase 5 (Canada tax suite): GST/HST return workpaper, T2125 mapping,
CCA schedule math, T4A contractor report, and CRA instalment estimates."""

import asyncio
import json
from datetime import timedelta

import pytest
import respx
from httpx import Response

import accountingqb.server as qb_server

REALM = "9130350000000000"
BASE = f"{qb_server.BASE_URL}/v3/company/{REALM}"
QUERY_URL = f"{BASE}/query"
PREFS_URL = f"{BASE}/preferences"
TAX_SUMMARY_URL = f"{BASE}/reports/TaxSummary"
PL_URL = f"{BASE}/reports/ProfitAndLoss"


def _prime_ctx(ctx):
    ctx.realm_id = REALM
    ctx.access_token = "tok-1"
    ctx.token_expiry = qb_server._utcnow() + timedelta(hours=1)
    ctx.refresh_token = "rt-1"


# ---------------------------------------------------------------------------
# Mocked QBO data
# ---------------------------------------------------------------------------

INVOICES = [  # 113 total incl. 13 HST -> line 101 += 100, line 103 += 13
    {"Id": "1", "TxnDate": "2026-01-10", "TotalAmt": 113.0,
     "TxnTaxDetail": {"TotalTax": 13.0}},
]
SALES_RECEIPTS = [  # 226 total incl. 26 -> line 101 += 200, line 103 += 26
    {"Id": "2", "TxnDate": "2026-02-05", "TotalAmt": 226.0,
     "TxnTaxDetail": {"TotalTax": 26.0}},
]
PURCHASES = [
    # plain office purchase: full $5.00 ITC
    {"Id": "3", "TxnDate": "2026-01-20", "TotalAmt": 105.0,
     "EntityRef": {"value": "10", "name": "Staples"},
     "TxnTaxDetail": {"TotalTax": 5.0},
     "Line": [{"Amount": 100.0, "DetailType": "AccountBasedExpenseLineDetail",
               "AccountBasedExpenseLineDetail": {
                   "AccountRef": {"name": "Office Supplies"}}}]},
    # meals purchase: only 50% of the $6.50 GST/HST claimable -> $3.25
    {"Id": "4", "TxnDate": "2026-02-14", "TotalAmt": 56.50,
     "EntityRef": {"value": "11", "name": "The Keg"},
     "TxnTaxDetail": {"TotalTax": 6.50},
     "Line": [{"Amount": 50.0, "DetailType": "AccountBasedExpenseLineDetail",
               "AccountBasedExpenseLineDetail": {
                   "AccountRef": {"name": "Meals and Entertainment"}}}]},
]
BILLS = [
    {"Id": "5", "TxnDate": "2026-03-01", "TotalAmt": 42.0,
     "VendorRef": {"value": "12", "name": "Landlord"},
     "TxnTaxDetail": {"TotalTax": 2.0},
     "Line": [{"Amount": 40.0, "DetailType": "AccountBasedExpenseLineDetail",
               "AccountBasedExpenseLineDetail": {
                   "AccountRef": {"name": "Rent"}}}]},
]
TAX_PAYMENTS = [
    {"Id": "6", "PaymentDate": "2026-02-15", "PaymentAmount": 500.0},
    {"Id": "7", "PaymentDate": "2025-11-30", "PaymentAmount": 999.0},  # out of range
]
T4A_VENDORS = [
    {"Id": "10", "DisplayName": "Design Co", "TaxIdentifier": "123456789RT0001",
     "BillAddr": {"Line1": "1 Main St", "City": "Toronto",
                  "CountrySubDivisionCode": "ON", "PostalCode": "M1M 1M1"}},
    {"Id": "11", "DisplayName": "Corner Coffee"},
]
T4A_PURCHASES = [
    {"Id": "20", "TxnDate": "2026-04-01", "TotalAmt": 1200.0,
     "EntityRef": {"value": "10", "name": "Design Co"}},
    {"Id": "21", "TxnDate": "2026-04-02", "TotalAmt": 100.0,
     "EntityRef": {"value": "11", "name": "Corner Coffee"}},
]

PL_REPORT = {"Rows": {"Row": [
    {"Header": {"ColData": [{"value": "Income"}]},
     "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "1000.00"}]}]},
     "Summary": {"ColData": [{"value": "Total Income"}, {"value": "1000.00"}]}},
    {"Header": {"ColData": [{"value": "Expenses"}]},
     "Rows": {"Row": [
         {"ColData": [{"value": "Advertising"}, {"value": "100.00"}]},
         {"ColData": [{"value": "Meals and Entertainment"}, {"value": "80.00"}]},
     ]},
     "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "180.00"}]}},
]}}

PL_REPORT_200K = {"Rows": {"Row": [
    {"Summary": {"ColData": [{"value": "Total Income"}, {"value": "200000.00"}]}},
    {"Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "0.00"}]}},
]}}


def _query_dispatcher(country="CA", vendors=None, purchases=None, bills=None):
    vendors = T4A_VENDORS if vendors is None else vendors
    purchases = PURCHASES if purchases is None else purchases
    bills = BILLS if bills is None else bills

    def handler(request):
        q = request.url.params.get("query", "")
        if "FROM CompanyInfo" in q:
            return Response(200, json={"QueryResponse": {"CompanyInfo": [
                {"CompanyName": "Maple Co", "Country": country}]}})
        if "FROM TaxAgency" in q:
            return Response(200, json={"QueryResponse": {"TaxAgency": [
                {"Id": "1", "DisplayName": "Canada Revenue Agency"}]}})
        if "FROM Invoice" in q:
            return Response(200, json={"QueryResponse": {"Invoice": INVOICES}})
        if "FROM SalesReceipt" in q:
            return Response(200, json={"QueryResponse": {"SalesReceipt": SALES_RECEIPTS}})
        if "FROM Purchase" in q:
            return Response(200, json={"QueryResponse": {"Purchase": purchases}})
        if "FROM Bill" in q:
            return Response(200, json={"QueryResponse": {"Bill": bills}})
        if "FROM TaxPayment" in q:
            return Response(200, json={"QueryResponse": {"TaxPayment": TAX_PAYMENTS}})
        if "FROM Vendor" in q:
            return Response(200, json={"QueryResponse": {"Vendor": vendors}})
        if "FROM Account" in q:
            return Response(200, json={"QueryResponse": {"Account": [
                {"Id": "80", "Name": "Computer Equipment",
                 "AccountType": "Fixed Asset", "CurrentBalance": 9000.0}]}})
        return Response(200, json={"QueryResponse": {}})
    return handler


def _prefs_response(partner_tax=False, currency="CAD"):
    return Response(200, json={"Preferences": {
        "TaxPrefs": {"PartnerTaxEnabled": partner_tax},
        "CurrencyPrefs": {"MultiCurrencyEnabled": False,
                          "HomeCurrency": {"value": currency}},
    }})


def _ca_router(router, **dispatcher_kwargs):
    router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA", **dispatcher_kwargs))
    router.get(PREFS_URL).mock(return_value=_prefs_response())


# ---------------------------------------------------------------------------
# qb_gst_hst_return
# ---------------------------------------------------------------------------

def test_gst_hst_return_workpaper_math_with_report_fallback(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        router.get(TAX_SUMMARY_URL).mock(return_value=Response(400, json={
            "Fault": {"Error": [{"code": "4000", "Message": "bad request",
                                 "Detail": "no report"}]}}))

        result = asyncio.run(qb_server.qb_gst_hst_return("2026-01-01", "2026-03-31"))

    # Report failed -> graceful fallback note, workpaper still computed
    assert "TaxSummary report unavailable" in result
    # Line 101: (113-13) + (226-26) = 300
    assert "Line 101" in result and "$300.00" in result
    # Line 103/105: 13 + 26 = 39
    assert "$39.00" in result
    # ITCs: 5 (office) + 3.25 (50% of 6.50 meals) + 2 (bill) = 10.25
    assert "Line 106" in result and "$10.25" in result
    # Net tax 109 = 39 - 10.25 = 28.75
    assert "Line 109" in result and "$28.75" in result
    # Meals restriction disclosed: 3.25 disallowed
    assert "$3.25" in result and "Meals & entertainment ITC restriction" in result
    # In-range tax payment shown, out-of-range one not
    assert "$500.00" in result
    assert "$999.00" not in result
    # Quick Method eligibility note ($339 tax-included << $400k)
    assert "Quick Method" in result
    # Mandatory footer
    assert ("This is a workpaper, not a filing. Verify against QuickBooks' "
            "Sales Tax Centre before filing with CRA.") in result


def test_gst_hst_return_renders_taxsummary_report_rows(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        router.get(TAX_SUMMARY_URL).mock(return_value=Response(200, json={
            "Header": {"ReportName": "TaxSummary"},
            "Rows": {"Row": [
                {"ColData": [{"value": "Line 101 Gross sales"}, {"value": "300.00"}]},
            ]},
        }))

        result = asyncio.run(qb_server.qb_gst_hst_return("2026-01-01", "2026-03-31"))

    assert "QuickBooks TaxSummary report — Canada Revenue Agency" in result
    assert "Line 101 Gross sales" in result
    # Workpaper is still always computed alongside the report
    assert "Transaction-derived return lines" in result
    assert "$28.75" in result


def test_gst_hst_return_redirects_for_us_company(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("US"))
        router.get(PREFS_URL).mock(
            return_value=_prefs_response(partner_tax=True, currency="USD"))

        result = asyncio.run(qb_server.qb_gst_hst_return("2026-01-01", "2026-03-31"))

    assert "CA-tax tool" in result
    assert "registered in US" in result
    assert "qb_sales_tax_summary" in result


# ---------------------------------------------------------------------------
# qb_t2125_summary
# ---------------------------------------------------------------------------

def test_t2125_maps_accounts_to_lines(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        router.get(PL_URL).mock(return_value=Response(200, json=PL_REPORT))

        result = asyncio.run(qb_server.qb_t2125_summary(2025))

    # Advertising -> line 8521, full amount
    assert "Line 8521" in result and "$100.00" in result
    # Meals -> line 8523 at 50%: 80 * 0.5 = 40
    assert "Line 8523" in result and "$40.00" in result
    # Income lines and GST note
    assert "Line 8000" in result and "$1,000.00" in result
    assert "net of GST/HST" in result
    # CCA / home-office placeholders point at the right tools
    assert "9936" in result and "qb_cca_schedule" in result
    assert "9945" in result
    # Filing deadlines
    assert "June 15" in result and "April 30" in result


# ---------------------------------------------------------------------------
# qb_cca_schedule
# ---------------------------------------------------------------------------

def test_cca_class_50_half_year_pre_2025(qb_ctx):
    _prime_ctx(qb_ctx)
    assets = json.dumps([{"name": "Server", "cost": 10000, "class": "50",
                          "acquired": "2024-03-01"}])
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        result = asyncio.run(qb_server.qb_cca_schedule(assets, year=2024))

    # Half-year rule: 10,000 * 55% * 0.5 = 2,750; closing UCC 7,250
    assert "$2,750.00" in result
    assert "$7,250.00" in result


def test_cca_class_50_aii_2026_no_half_year(qb_ctx):
    _prime_ctx(qb_ctx)
    assets = json.dumps([{"name": "Server", "cost": 10000, "class": "50",
                          "acquired": "2026-01-15"}])
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        result = asyncio.run(qb_server.qb_cca_schedule(assets, year=2026))

    # AII: 10,000 * 55% * 1.5 = 8,250 (no half-year)
    assert "$8,250.00" in result
    assert "Accelerated Investment Incentive" in result
    assert "immediate expensing" in result


def test_cca_class_10_1_ceiling_clamp(qb_ctx):
    _prime_ctx(qb_ctx)
    assets = json.dumps([{"name": "BMW", "cost": 60000, "class": "10.1",
                          "acquired": "2025-05-01"}])
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        result = asyncio.run(qb_server.qb_cca_schedule(assets, year=2025))

    # Cost capped at the 2025 ceiling of $38,000; AII CCA = 38,000 * 30% * 1.5
    assert "$38,000.00" in result
    assert "$17,100.00" in result
    assert "no terminal loss" in result


def test_cca_without_assets_lists_fixed_asset_accounts(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        result = asyncio.run(qb_server.qb_cca_schedule(year=2026))

    assert "Computer Equipment" in result
    assert "assets_json" in result
    assert "Class 50" in result


# ---------------------------------------------------------------------------
# qb_t4a_contractor_report
# ---------------------------------------------------------------------------

def test_t4a_threshold_and_february_deadline(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router, purchases=T4A_PURCHASES, bills=[])

        result = asyncio.run(qb_server.qb_t4a_contractor_report(2026))

    # $1,200 vendor reportable; $100 vendor below the $500 admin threshold
    assert "Design Co" in result and "$1,200.00" in result
    assert "Corner Coffee" not in result
    assert "$500.00" in result
    assert "box 048" in result or "048" in result
    assert "February 2027" in result
    assert "T5018" in result


# ---------------------------------------------------------------------------
# qb_estimate_instalments
# ---------------------------------------------------------------------------

def test_instalments_cpp_2026_above_yampe(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        router.get(PL_URL).mock(return_value=Response(200, json=PL_REPORT_200K))

        result = asyncio.run(qb_server.qb_estimate_instalments(year=2026, province="ON"))

    # Base CPP: (74,600 - 3,500) * 11.9% = 8,460.90
    assert "$8,460.90" in result
    # CPP2: (85,000 - 74,600) * 8% = 832.00
    assert "$832.00" in result
    assert "$74,600.00" in result and "$85,000.00" in result
    # All four CRA instalment dates
    for due in ("Mar 15", "Jun 15", "Sep 15", "Dec 15"):
        assert due in result
    # Clearly labeled approximate + threshold note
    assert "approximate" in result.lower()
    assert "$3,000.00" in result


def test_instalments_quebec_note(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _ca_router(router)
        router.get(PL_URL).mock(return_value=Response(200, json=PL_REPORT_200K))

        result = asyncio.run(qb_server.qb_estimate_instalments(year=2026, province="QC"))

    assert "Revenu Québec" in result
