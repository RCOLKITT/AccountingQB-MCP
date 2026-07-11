"""Phase 4 (Canada unblock): region detection, tax-code resolution, and
GlobalTaxCalculation / TaxCodeRef injection on create tools."""

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
INVOICE_URL = f"{BASE}/invoice"

INVOICE_OK = {"Invoice": {"Id": "9", "DocNumber": "1001",
                          "TotalAmt": 113.0, "DueDate": "2026-08-01"}}


def _prime_ctx(ctx):
    ctx.realm_id = REALM
    ctx.access_token = "tok-1"
    ctx.token_expiry = qb_server._utcnow() + timedelta(hours=1)
    ctx.refresh_token = "rt-1"


def _query_dispatcher(country="CA", province=None):
    """Answer QBO SELECT queries by entity, regardless of call order."""
    company = {"CompanyName": "Maple Co", "Country": country}
    if province:
        company["CompanyAddr"] = {"CountrySubDivisionCode": province}

    def handler(request):
        q = request.url.params.get("query", "")
        if "FROM CompanyInfo" in q:
            return Response(200, json={"QueryResponse": {"CompanyInfo": [company]}})
        if "FROM TaxCode" in q:
            return Response(200, json={"QueryResponse": {"TaxCode": [
                {"Id": "3", "Name": "HST ON", "Active": True,
                 "SalesTaxRateList": {"TaxRateDetail": [
                     {"TaxRateRef": {"value": "7"}}]}},
                {"Id": "4", "Name": "GST", "Active": True,
                 "SalesTaxRateList": {"TaxRateDetail": [
                     {"TaxRateRef": {"value": "8"}}]}},
                {"Id": "5", "Name": "Exempt", "Active": True},
            ]}})
        if "FROM TaxRate" in q:
            return Response(200, json={"QueryResponse": {"TaxRate": [
                {"Id": "7", "Name": "HST ON", "RateValue": 13,
                 "AgencyRef": {"value": "1"}},
                {"Id": "8", "Name": "GST", "RateValue": 5,
                 "AgencyRef": {"value": "1"}},
            ]}})
        if "FROM TaxAgency" in q:
            return Response(200, json={"QueryResponse": {"TaxAgency": [
                {"Id": "1", "DisplayName": "Canada Revenue Agency"}]}})
        if "FROM Customer" in q:
            return Response(200, json={"QueryResponse": {"Customer": [
                {"Id": "42", "DisplayName": "TechStart Inc"}]}})
        return Response(200, json={"QueryResponse": {}})
    return handler


def _prefs_response(partner_tax=False, currency="CAD"):
    return Response(200, json={"Preferences": {
        "TaxPrefs": {"PartnerTaxEnabled": partner_tax},
        "CurrencyPrefs": {"MultiCurrencyEnabled": False,
                          "HomeCurrency": {"value": currency}},
    }})


# ---------------------------------------------------------------------------
# (a) CA invoice: GlobalTaxCalculation + TaxCodeRef injected
# ---------------------------------------------------------------------------

def test_ca_invoice_sends_global_tax_and_tax_code_ref(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())
        post = router.post(INVOICE_URL).mock(return_value=Response(200, json=INVOICE_OK))

        result = asyncio.run(qb_server.qb_create_invoice(
            "TechStart", '[{"description": "Consulting", "amount": 100}]',
            tax_code="HST ON",
        ))

    assert "Invoice created" in result
    body = json.loads(post.calls[0].request.content)
    assert body["GlobalTaxCalculation"] == "TaxExcluded"
    assert body["Line"][0]["SalesItemLineDetail"]["TaxCodeRef"] == {"value": "3"}


def test_ca_invoice_tax_inclusive_and_per_line_override(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())
        post = router.post(INVOICE_URL).mock(return_value=Response(200, json=INVOICE_OK))

        result = asyncio.run(qb_server.qb_create_invoice(
            "TechStart",
            '[{"description": "A", "amount": 100, "tax_code": "GST"},'
            ' {"description": "B", "amount": 50}]',
            tax_code="HST ON", tax_inclusive=True,
        ))

    assert "Invoice created" in result
    body = json.loads(post.calls[0].request.content)
    assert body["GlobalTaxCalculation"] == "TaxInclusive"
    # per-line override wins; default fills the rest
    assert body["Line"][0]["SalesItemLineDetail"]["TaxCodeRef"] == {"value": "4"}
    assert body["Line"][1]["SalesItemLineDetail"]["TaxCodeRef"] == {"value": "3"}


# ---------------------------------------------------------------------------
# (b) US invoice: no GlobalTaxCalculation, no TaxCodeRef
# ---------------------------------------------------------------------------

def test_us_invoice_has_no_global_tax_fields(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("US"))
        router.get(PREFS_URL).mock(return_value=_prefs_response(partner_tax=True, currency="USD"))
        post = router.post(INVOICE_URL).mock(return_value=Response(200, json=INVOICE_OK))

        result = asyncio.run(qb_server.qb_create_invoice(
            "TechStart", '[{"description": "Consulting", "amount": 100}]',
        ))

    assert "Invoice created" in result
    body = json.loads(post.calls[0].request.content)
    assert "GlobalTaxCalculation" not in body
    assert "TaxCodeRef" not in body["Line"][0]["SalesItemLineDetail"]


# ---------------------------------------------------------------------------
# (c) CA invoice without any tax code: friendly error, no POST
# ---------------------------------------------------------------------------

def test_ca_invoice_without_tax_code_blocked_before_post(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())
        post = router.post(INVOICE_URL).mock(return_value=Response(200, json=INVOICE_OK))

        result = asyncio.run(qb_server.qb_create_invoice(
            "TechStart", '[{"description": "Consulting", "amount": 100}]',
        ))

    assert "requires a sales tax code" in result
    assert "qb_list_tax_codes" in result
    assert post.called is False


# ---------------------------------------------------------------------------
# (d) US-tax tools redirect for CA companies without running their queries
# ---------------------------------------------------------------------------

def test_schedule_c_redirects_for_ca_company(qb_ctx):
    _prime_ctx(qb_ctx)
    # Strict respx: any Schedule C report request would be unmatched and raise,
    # so getting the redirect string back proves the gate short-circuited.
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())

        result = asyncio.run(qb_server.qb_schedule_c(tax_year="2025"))

    assert "US-tax tool" in result
    assert "registered in CA" in result
    assert "qb_t2125_summary" in result


# ---------------------------------------------------------------------------
# (e) _resolve_tax_code matching + not-found error
# ---------------------------------------------------------------------------

def test_resolve_tax_code_case_insensitive_and_by_id(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))

        assert asyncio.run(qb_server._resolve_tax_code("hst on")) == ("3", "HST ON")
        assert asyncio.run(qb_server._resolve_tax_code("3")) == ("3", "HST ON")
        # substring match
        assert asyncio.run(qb_server._resolve_tax_code("exem")) == ("5", "Exempt")


def test_resolve_tax_code_not_found_lists_available(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(qb_server._resolve_tax_code("PST BC"))

    msg = str(exc_info.value)
    assert "PST BC" in msg
    assert "HST ON" in msg
    assert "GST" in msg


# ---------------------------------------------------------------------------
# Region detection & caching
# ---------------------------------------------------------------------------

def test_get_region_detects_ca_and_caches_per_realm(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        query = router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())

        info1 = asyncio.run(qb_server._get_region())
        info2 = asyncio.run(qb_server._get_region())

    assert info1 == {"region": "CA", "home_currency": "CAD", "multicurrency": False,
                     "subdivision": ""}
    assert info2 is info1  # served from region_cache
    assert query.call_count == 1
    assert qb_ctx.region_cache[REALM]["region"] == "CA"


def test_get_region_defaults_to_us_on_api_error(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(return_value=Response(500, json={}))

        info = asyncio.run(qb_server._get_region())

    assert info["region"] == "US"
    assert qb_ctx.region_cache == {}  # failures are not cached


def test_partner_tax_enabled_wins_over_missing_country(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher(""))
        router.get(PREFS_URL).mock(return_value=_prefs_response(partner_tax=True, currency="USD"))

        info = asyncio.run(qb_server._get_region())

    assert info["region"] == "US"


# ---------------------------------------------------------------------------
# Discovery tools
# ---------------------------------------------------------------------------

def test_qb_list_tax_codes_shows_rates_and_agency(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())

        result = asyncio.run(qb_server.qb_list_tax_codes())

    assert "HST ON" in result
    assert "13%" in result
    assert "Canada Revenue Agency" in result
    assert "Zero-rated / Exempt" in result  # Exempt code grouped separately
    assert "tax_code=" in result  # usage hint


def test_qb_list_tax_codes_annotates_detected_province(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA", province="ON"))
        router.get(PREFS_URL).mock(return_value=_prefs_response())

        result = asyncio.run(qb_server.qb_list_tax_codes())

    assert "Detected province: ON — HST 13%" in result
    assert "HST ON" in result


def test_qb_list_tax_rates_lists_rate_values(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        router.get(QUERY_URL).mock(side_effect=_query_dispatcher("CA"))

        result = asyncio.run(qb_server.qb_list_tax_rates())

    assert "GST" in result and "5%" in result
    assert "HST ON" in result and "13%" in result
    assert "Canada Revenue Agency" in result


# ---------------------------------------------------------------------------
# qb_estimate_quarterly_tax — US state income tax table
# ---------------------------------------------------------------------------

PL_URL = f"{BASE}/reports/ProfitAndLoss"

PL_100K = {"Rows": {"Row": [
    {"Summary": {"ColData": [{"value": "Total Income"}, {"value": "100000.00"}]}},
    {"Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "0.00"}]}},
]}}


def _us_router(router, province=None):
    router.get(QUERY_URL).mock(side_effect=_query_dispatcher("US", province=province))
    router.get(PREFS_URL).mock(
        return_value=_prefs_response(partner_tax=True, currency="USD"))
    router.get(PL_URL).mock(return_value=Response(200, json=PL_100K))


def test_quarterly_tax_no_income_tax_state(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)

        result = asyncio.run(qb_server.qb_estimate_quarterly_tax(state="TX"))

    assert "TX — no state income tax on earned income: $0.00" in result


def test_quarterly_tax_flat_state_pa(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)

        result = asyncio.run(qb_server.qb_estimate_quarterly_tax(state="PA"))

    # 3.07% of $100,000 net income
    assert "PA flat 3.07% income tax: $3,070.00" in result


def test_quarterly_tax_progressive_ca_disclaimer(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)

        result = asyncio.run(qb_server.qb_estimate_quarterly_tax(state="CA"))

    assert "CA progressive — ~9.3% effective-rate approximation" in result
    assert "planning approximation" in result


def test_quarterly_tax_unknown_state_generic(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router)

        result = asyncio.run(qb_server.qb_estimate_quarterly_tax(state="ZZ"))

    assert "generic ~5% estimate" in result and "pass state=XX" in result


def test_quarterly_tax_autodetects_state_from_company_addr(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock(assert_all_called=False) as router:
        _us_router(router, province="MA")

        result = asyncio.run(qb_server.qb_estimate_quarterly_tax())

    assert "**State:** MA" in result
    assert "MA flat 5% income tax" in result
