"""Regression tests for the v3.10.0 end-to-end review findings (NutriFitAI):
Schedule C / T2125 income mapping, the Trial Balance rewrite, missing-receipts
filtering, and the find-duplicates tightening. Golden numbers are the review's."""

import asyncio
import json
from unittest.mock import patch

import accountingqb.server as s


def _unwrap(tool):
    return getattr(tool, "__wrapped__", tool)


# --- P&L mirroring the review: Sales $195, Refunds -$39 (contra), interest
#     $0.76 (Other Income), $20,090.02 expenses. Net must be -$19,933.26. ------
PL = {
    "Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Sales"}, {"value": "195.00"}]},
             {"ColData": [{"value": "Refunds to customers"}, {"value": "-39.00"}]},
         ]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "156.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "General Operations"}, {"value": "20090.02"}]},
         ]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "20090.02"}]}},
        {"Header": {"ColData": [{"value": "Other Income"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Interest Earned"}, {"value": "0.76"}]},
         ]},
         "Summary": {"ColData": [{"value": "Total Other Income"}, {"value": "0.76"}]}},
    ]}
}


def _run_pl(coro_fn, *a):
    async def fake_req(method, path, params=None, **k):
        return PL

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "NutriFitAI LLC"}]}}

    with patch.object(s, "qb_request", fake_req), patch.object(s, "qb_query", fake_query):
        return asyncio.run(_unwrap(coro_fn)(*a))


def test_schedule_c_income_split():
    out = _run_pl(s.qb_schedule_c, "2026")
    assert "Line 1 — Gross receipts or sales:** $195.00" in out
    assert "Line 2 — Returns and allowances:** $39.00" in out
    assert "Line 6 — Other income" in out and "$0.76" in out
    assert "Line 7 — Gross income:** $156.76" in out
    assert "$-19,933.26" in out              # net = 156.76 - 20090.02


def test_schedule_c_detailed_agrees():
    out = _run_pl(s.qb_schedule_c_detailed, "2026")
    assert "$195.00" in out and "$156.76" in out
    assert "Gross income (Line 7): $156.76" in out


def test_t2125_income_split():
    out = _run_pl(s.qb_t2125_summary, 2026)
    assert "Gross sales, commissions or fees: $195.00" in out
    assert "Other income" in out and "$0.76" in out
    assert "Gross business income: $156.76" in out


def test_breakdown_summary_only_pl():
    # A summary-only P&L (no leaf rows) must still read income correctly.
    pl = {"Rows": {"Row": [
        {"Summary": {"ColData": [{"value": "Total Income"}, {"value": "100000.00"}]}},
        {"Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "0.00"}]}},
    ]}}
    gross, ret, cogs, other = s._pl_income_breakdown(pl)
    assert gross == 100000.0 and ret == 0.0 and other == 0.0


# --- Trial balance: two columns, correct signs, as-of header, balances --------
TB = {"Columns": {"Column": [{"ColTitle": ""}, {"ColTitle": "Debit"},
                             {"ColTitle": "Credit"}]},
      "Rows": {"Row": [
          {"ColData": [{"value": "Checking"}, {"value": "36123.23"}, {"value": ""}]},
          {"ColData": [{"value": "General Operations"}, {"value": "20090.02"}, {"value": ""}]},
          {"ColData": [{"value": "Sales"}, {"value": ""}, {"value": "195.00"}]},
          {"ColData": [{"value": "Owner Equity"}, {"value": ""}, {"value": "56018.25"}]},
          {"Summary": {"ColData": [{"value": "TOTAL"}, {"value": "56213.25"},
                                   {"value": "56213.25"}]}},
      ]}}


def test_trial_balance_two_columns_and_balances():
    async def fake_req(method, path, params=None, **k):
        return TB
    with patch.object(s, "qb_request", fake_req):
        out = asyncio.run(_unwrap(s.qb_trial_balance)("2026-08-02"))
    assert "as of 2026-08-02" in out
    assert "| Account | Debit | Credit |" in out
    assert "| Checking | $36,123.23 |  |" in out          # debit populated
    assert "| Sales |  | $195.00 |" in out                # credit populated
    assert "In balance" in out
    assert "to " not in out.split("\n")[0]                # header is as-of, not a range


# --- Missing receipts: exclude card payments / transfers / interest -----------
def test_missing_receipts_excludes_card_payment_and_interest():
    accounts = [
        {"Id": "10", "Name": "Checking", "AccountType": "Bank"},
        {"Id": "20", "Name": "Office Supplies", "AccountType": "Expense"},
        {"Id": "30", "Name": "Interest Expense", "AccountType": "Expense"},
    ]
    purchases = [
        # real expense — should be flagged (no receipt)
        {"Id": "1", "TxnDate": "2026-02-01", "TotalAmt": 500.0,
         "EntityRef": {"name": "Staples"},
         "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "20"}}}]},
        # credit-card payment / transfer to a Bank account — must be excluded
        {"Id": "2", "TxnDate": "2026-02-02", "TotalAmt": 8500.0,
         "EntityRef": {"name": "Amex"},
         "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "10"}}}]},
        # interest — must be excluded
        {"Id": "3", "TxnDate": "2026-02-03", "TotalAmt": 120.0,
         "EntityRef": {"name": "Bank"},
         "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "30"}}}]},
    ]

    async def fake_query_all(q, **k):
        if "Attachable" in q:
            return {"QueryResponse": {}}
        if "Account" in q:
            return {"QueryResponse": {"Account": accounts}}
        if "Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}       # Bill

    with patch.object(s, "qb_query_all", fake_query_all):
        out = asyncio.run(_unwrap(s.qb_missing_receipts)(75.0, "2026-01-01", "2026-12-31"))
    assert "Staples" in out and "Purchase #1" in out
    assert "Amex" not in out and "Purchase #2" not in out
    assert "excluded 2" in out


# --- Find duplicates: same-day default + recurring suppression ----------------
def test_find_duplicates_recurring_suppressed_and_counts():
    purchases = [
        # true same-day duplicate
        {"Id": "1", "TxnDate": "2026-03-01", "TotalAmt": 300.0, "EntityRef": {"name": "Acme"}},
        {"Id": "2", "TxnDate": "2026-03-01", "TotalAmt": 300.0, "EntityRef": {"name": "Acme"}},
        # a monthly recurring subscription (same vendor+amount, many days) — suppress
        {"Id": "3", "TxnDate": "2026-01-15", "TotalAmt": 49.0, "EntityRef": {"name": "SaaS"}},
        {"Id": "4", "TxnDate": "2026-02-15", "TotalAmt": 49.0, "EntityRef": {"name": "SaaS"}},
        {"Id": "5", "TxnDate": "2026-03-15", "TotalAmt": 49.0, "EntityRef": {"name": "SaaS"}},
        {"Id": "6", "TxnDate": "2026-04-15", "TotalAmt": 49.0, "EntityRef": {"name": "SaaS"}},
    ]

    async def fake_query_all(q, **k):
        return {"QueryResponse": {"Purchase": purchases}}

    with patch.object(s, "qb_query_all", fake_query_all):
        out = asyncio.run(_unwrap(s.qb_find_duplicates)("2026-01-01", "2026-12-31"))
    assert "Acme" in out and "1 extra transaction" in out
    assert "SaaS" not in out                              # recurring, suppressed
    assert "Suppressed 1 recurring" in out


# --- Books hygiene: disclose a truncated ID list ------------------------------
def test_books_hygiene_discloses_truncated_ids():
    accounts = [
        {"Id": "100", "Name": "Amex", "AccountType": "Credit Card"},
        {"Id": "200", "Name": "Checking", "AccountType": "Bank"},
    ]
    # 13 credit-card purchases each miscategorized to the Bank account.
    purchases = [{
        "Id": str(1000 + i), "TxnDate": "2026-05-01", "TotalAmt": 100.0,
        "AccountRef": {"value": "100"},
        "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "200"}}}],
    } for i in range(13)]

    async def fake_query_all(q, **k):
        if "Active = false" in q:
            return {"QueryResponse": {}}
        if "Account" in q:
            return {"QueryResponse": {"Account": accounts}}
        if "Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}

    with patch.object(s, "qb_query_all", fake_query_all):
        out = asyncio.run(_unwrap(s.qb_books_hygiene)("2026-01-01", "2026-12-31"))
    assert "13 credit-card purchase(s)" in out
    assert "showing first 10 of 13" in out


# ===== v3.13.1 — second-round review fixes =========================

def test_other_income_not_double_counted():
    """P&L with an Other Income section AND a 'Net Other Income' roll-up row —
    'other income' is a substring of 'net other income', which used to add the
    amount twice. Line 7 must equal Line 3 + Line 6."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "195.00"}]},
                          {"ColData": [{"value": "Refunds"}, {"value": "-39.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "156.00"}]}},
        {"Header": {"ColData": [{"value": "Other Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Interest earned"}, {"value": "0.76"}]}]},
         "Summary": {"ColData": [{"value": "Total Other Income"}, {"value": "0.76"}]}},
        {"Summary": {"ColData": [{"value": "Net Other Income"}, {"value": "0.76"}]}},
    ]}}
    gross, ret, cogs, other = s._pl_income_breakdown(pl)
    assert (gross, ret, cogs, other) == (195.0, 39.0, 0.0, 0.76)
    line3 = round(gross - ret, 2)
    line7 = round((line3 - cogs) + other, 2)
    assert line7 == round(line3 + other, 2) == 156.76


def test_duplicate_detectors_agree():
    """qb_find_duplicates and qb_books_health_audit must report the same extra
    count — they now share _purchase_dup_clusters."""
    purchases = [
        {"Id": "1", "TxnDate": "2026-03-01", "TotalAmt": 300.0, "EntityRef": {"name": "Acme"}},
        {"Id": "2", "TxnDate": "2026-03-01", "TotalAmt": 300.0, "EntityRef": {"name": "Acme"}},
        # recurring — suppressed by both
        {"Id": "3", "TxnDate": "2026-01-15", "TotalAmt": 95.63, "EntityRef": {"name": "Anthropic"}},
        {"Id": "4", "TxnDate": "2026-02-15", "TotalAmt": 95.63, "EntityRef": {"name": "Anthropic"}},
        {"Id": "5", "TxnDate": "2026-03-15", "TotalAmt": 95.63, "EntityRef": {"name": "Anthropic"}},
        {"Id": "6", "TxnDate": "2026-04-15", "TotalAmt": 95.63, "EntityRef": {"name": "Anthropic"}},
    ]
    clusters, _ = s._purchase_dup_clusters(purchases, 0)
    extra = sum(len(c) - 1 for _, _, c in clusters)
    assert extra == 1                      # only the Acme same-day pair


def test_missing_receipts_excludes_deleted_card_account():
    """A payment categorized to a DELETED credit-card account must be excluded —
    the account type is only known if inactive accounts are fetched too."""
    active = [{"Id": "20", "Name": "Office Supplies", "AccountType": "Expense"}]
    inactive = [{"Id": "99", "Name": "Delta SkyMiles Reserve Card (1008)",
                 "AccountType": "Credit Card"}]
    purchases = [
        {"Id": "1", "TxnDate": "2026-02-01", "TotalAmt": 500.0,
         "EntityRef": {"name": "Staples"},
         "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "20"}}}]},
        {"Id": "2037", "TxnDate": "2026-01-26", "TotalAmt": 1000.0,
         "EntityRef": {"name": "Amex payment"},
         "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "99"}}}]},
    ]

    async def fake_query_all(q, **k):
        if "Attachable" in q:
            return {"QueryResponse": {}}
        if "Active = false" in q:
            return {"QueryResponse": {"Account": inactive}}
        if "Account" in q:
            return {"QueryResponse": {"Account": active}}
        if "Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}

    with patch.object(s, "qb_query_all", fake_query_all):
        out = asyncio.run(_unwrap(s.qb_missing_receipts)(75.0, "2026-01-01", "2026-12-31"))
    assert "Staples" in out
    assert "#2037" not in out and "excluded 1" in out


def test_server_info_reports_version_and_count():
    async def fake_query(q):
        raise RuntimeError("not connected")
    with patch.object(s, "qb_query", fake_query):
        out = asyncio.run(_unwrap(s.qb_server_info)())
    assert "Version:" in out and "Tools registered:" in out
    assert str(len(s.mcp._tool_manager._tools)) in out


def test_server_info_deployment_mode_is_static():
    """Deployment mode must be reported from the process, not the QuickBooks
    session — accurate even with an expired/absent token (the degraded state
    where someone reaches for this tool)."""
    async def boom(q):
        raise RuntimeError("expired token")
    with patch.object(s, "qb_query", boom), patch.object(s, "_HOSTED_CONNECTOR", True):
        out = asyncio.run(_unwrap(s.qb_server_info)())
    assert "Deployment:** hosted connector" in out    # stable even when QB not connected
    assert "not connected" in out                       # only the QuickBooks line degrades


def test_schedule_c_meals_limit_and_allocation_warning():
    """Meals shown at 50% with the §274(n) arithmetic; a utility-typed account
    is flagged as likely needing a business-use % (Part 6 safety net)."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "50000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "50000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Business meals"}, {"value": "1102.10"}]},
             {"ColData": [{"value": "Cell phone"}, {"value": "809.03"}]}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "1911.13"}]}},
    ]}}
    accts = [{"Name": "Business meals", "AccountSubType": "TravelMeals", "FullyQualifiedName": "Business meals"},
             {"Name": "Cell phone", "AccountSubType": "Utilities", "FullyQualifiedName": "Cell phone"}]

    async def fake_req(m, p, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D"}]}}

    fn = getattr(s.qb_schedule_c, "__wrapped__", s.qb_schedule_c)
    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query):
        out = asyncio.run(fn("2025"))
    assert "× 50% (IRC §274(n)) = $551.05" in out or "× 50% (IRC §274(n))" in out
    assert "Line 24b — Deductible meals: $551.0" in out
    assert "statutory limits removed" in out
    assert "Likely need a business-use %" in out and "Cell phone" in out
    # no false reconciliation warning (three buckets tie to the P&L)
    assert "Does not reconcile" not in out
