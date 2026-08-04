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
    assert "Line 7 — Gross income: $156.76" in out


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
    assert "13 credit-card charge(s)" in out
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

    # Belt-and-suspenders: even if _HOSTED_CONNECTOR is somehow False on the
    # deployed process, MCP_JWT_SECRET (always set on the connector, never on a
    # local .mcpb) pins it to hosted — a session-independent, static signal.
    with patch.object(s, "qb_query", boom), \
            patch.object(s, "_HOSTED_CONNECTOR", False), \
            patch.dict(s.os.environ, {"MCP_JWT_SECRET": "x"}), \
            patch.object(s._default_ctx, "hosted_mode", False):
        out = asyncio.run(_unwrap(s.qb_server_info)())
    assert "Deployment:** hosted connector" in out

    # ROOT CAUSE of the recurring flip: local hosted-broker mode. The mode must
    # come from the import-time config (_HOSTED_BROKER_CONFIG), NOT the mutable
    # ctx.hosted_mode that _load_hosted_tokens() flips True after a refresh.
    # Same build, hosted_mode toggling False→True must NOT change the answer.
    async def noconn(q):
        raise RuntimeError("no token yet")
    for mutated in (False, True):     # expired, then after a hosted-token load
        with patch.object(s, "qb_query", noconn), \
                patch.object(s, "_HOSTED_CONNECTOR", False), \
                patch.dict(s.os.environ, {}, clear=False), \
                patch.object(s, "_HOSTED_BROKER_CONFIG", True), \
                patch.object(s._default_ctx, "hosted_mode", mutated):
            s.os.environ.pop("MCP_JWT_SECRET", None)
            out = asyncio.run(_unwrap(s.qb_server_info)())
        assert "Deployment:** hosted connector" in out, \
            f"flipped when hosted_mode={mutated}"


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
    assert "Removed from this year's deductions" in out and "statutory" in out
    assert "Likely need a business-use %" in out and "Cell phone" in out
    # no false reconciliation warning (three buckets tie to the P&L)
    assert "Does not reconcile" not in out


def test_home_office_subaccounts_route_by_parent_chain():
    """P0 audit guard: accounts under a 'Home office' PARENT whose own leaf name
    lacks 'home' (Mortgage interest, Property taxes, Repairs) must route to Form
    8829 at the home-office %, NOT be deducted 100% on their operating lines.
    Detection keys on the FullyQualifiedName ('Home office:Property taxes'), not
    the leaf. Over-claiming here is an examination risk — this must not regress."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "50000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "50000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Advertising"}, {"value": "500.00"}]},
             # 'Home office' PARENT group — children's leaf names lack 'home'
             {"Header": {"ColData": [{"value": "Home office"}]},
              "Rows": {"Row": [
                  {"ColData": [{"value": "Mortgage interest"}, {"value": "3613.41"}]},
                  {"ColData": [{"value": "Property taxes"}, {"value": "1115.84"}]},
                  {"ColData": [{"value": "Repairs & maintenance"}, {"value": "2116.19"}]},
                  {"ColData": [{"value": "Home utilities"}, {"value": "564.64"}]}]},
              "Summary": {"ColData": [{"value": "Total Home office"}, {"value": "7410.08"}]}}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "7910.08"}]}},
    ]}}
    # The chart gives the FullyQualifiedName — the parent chain QuickBooks already knows.
    accts = [
        {"Name": "Advertising", "AccountSubType": "AdvertisingPromotional", "FullyQualifiedName": "Advertising"},
        {"Name": "Mortgage interest", "AccountSubType": "OtherMiscellaneousExpense", "FullyQualifiedName": "Home office:Mortgage interest"},
        {"Name": "Property taxes", "AccountSubType": "OtherMiscellaneousExpense", "FullyQualifiedName": "Home office:Property taxes"},
        {"Name": "Repairs & maintenance", "AccountSubType": "RepairMaintenance", "FullyQualifiedName": "Home office:Repairs & maintenance"},
        {"Name": "Home utilities", "AccountSubType": "Utilities", "FullyQualifiedName": "Home office:Home utilities"},
    ]

    async def fake_req(m, p, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D"}]}}

    async def fake_profile(year):
        return {"home_office": {"method": "actual", "office_sqft": 300, "home_sqft": 2400,
                                "percentage": 0.125, "basis_note": "300 / 2400 sqft"}}

    fn = getattr(s.qb_schedule_c, "__wrapped__", s.qb_schedule_c)
    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(fn("2025"))

    # All four home costs pooled to Form 8829 at 12.5% (7410.08 × .125 = 926.26)
    assert "Line 30 — Home office (Form 8829): $926.26" in out
    assert "$7,410.08 × 12.50%" in out
    # NOT deducted at 100% on their operating lines — the whole point.
    assert "Line 16" not in out          # mortgage interest did NOT land on interest
    assert "Line 23" not in out          # property taxes did NOT land on taxes
    assert "Line 21" not in out          # repairs did NOT land on repairs
    # personal home share (7410.08 × 87.5% = 6483.82) is disclosed, and it reconciles
    assert "6,483.82 personal home share" in out
    assert "Does not reconcile" not in out


def test_owner_draws_sums_amount_not_running_balance():
    """A real QuickBooks GeneralLedger has an Amount column AND a running-Balance
    column. The tool must sum Amount — summing the balance (which grows every row)
    over-counts, which is how a $56,018 net investment showed as ~$96k. Guard it."""
    accts = [{"Id": "80", "Name": "Owner Investment", "AccountType": "Equity"}]
    # Column metadata as QuickBooks actually returns it (ColKey identifies each).
    gl = {"Columns": {"Column": [
            {"ColTitle": "Date", "ColType": "Date",
             "MetaData": [{"Name": "ColKey", "Value": "tx_date"}]},
            {"ColTitle": "Transaction Type", "ColType": "String",
             "MetaData": [{"Name": "ColKey", "Value": "txn_type"}]},
            {"ColTitle": "Amount", "ColType": "Money",
             "MetaData": [{"Name": "ColKey", "Value": "subt_nat_amount"}]},
            {"ColTitle": "Balance", "ColType": "Money",
             "MetaData": [{"Name": "ColKey", "Value": "rbal_nat_amount"}]}]},
          "Rows": {"Row": [
            {"Header": {"ColData": [{"value": "Owner Investment"}]},
             "Rows": {"Row": [
                 {"ColData": [{"value": ""}, {"value": "Beginning Balance"},
                              {"value": ""}, {"value": "0.00"}]},
                 {"ColData": [{"value": "2025-02-01"}, {"value": "Deposit"},
                              {"value": "40000.00"}, {"value": "40000.00"}]},
                 {"ColData": [{"value": "2025-05-01"}, {"value": "Deposit"},
                              {"value": "16018.25"}, {"value": "56018.25"}]}]},
             "Summary": {"ColData": [{"value": "Total Owner Investment"},
                                     {"value": ""}, {"value": "56018.25"}]}}]}}

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_req(m, p, params=None, **k):
        return gl

    with patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_request", fake_req):
        out = asyncio.run(_unwrap(s.qb_owner_draws)(2025))

    assert "$56,018.25" in out               # net = sum of Amount
    assert "$96,018.25" not in out           # NOT sum of running Balance (the bug)
    assert "net contribution" in out
    assert "audit cross-check passed" in out  # transactions tie to the balance change


def test_t2125_applies_allocation_home_and_vehicle():
    """T2125 (Canada) now runs the SAME allocation engine as Schedule C: meals
    50% (ITA s.67.1), motor-vehicle business-use %, and home costs routed to line
    9945 with the loss limit — instead of everything at 100%. One code path."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "20000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "20000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Advertising"}, {"value": "100.00"}]},
             {"ColData": [{"value": "Meals and Entertainment"}, {"value": "1000.00"}]},
             {"ColData": [{"value": "Motor vehicle"}, {"value": "2000.00"}]},
             {"Header": {"ColData": [{"value": "Home office"}]},
              "Rows": {"Row": [
                  {"ColData": [{"value": "Property taxes"}, {"value": "1000.00"}]},
                  {"ColData": [{"value": "Utilities"}, {"value": "500.00"}]}]},
              "Summary": {"ColData": [{"value": "Total Home office"}, {"value": "1500.00"}]}}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "4600.00"}]}},
    ]}}
    accts = [
        {"Name": "Advertising", "AccountSubType": "AdvertisingPromotional", "FullyQualifiedName": "Advertising"},
        {"Name": "Meals and Entertainment", "AccountSubType": "EntertainmentMeals", "FullyQualifiedName": "Meals and Entertainment"},
        {"Name": "Motor vehicle", "AccountSubType": "Auto", "FullyQualifiedName": "Motor vehicle"},
        {"Name": "Property taxes", "AccountSubType": "OtherMiscellaneousExpense", "FullyQualifiedName": "Home office:Property taxes"},
        {"Name": "Utilities", "AccountSubType": "Utilities", "FullyQualifiedName": "Home office:Utilities"},
    ]

    async def fake_req(m, p, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "Maple Co", "Country": "CA"}]}}

    async def fake_profile(y):
        return {"home_office": {"percentage": 0.20, "basis_note": "300/1500 sqft"},
                "vehicle": {"method": "actual", "percentage": 0.60,
                            "basis_note": "6000/10000 km"}}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(_unwrap(s.qb_t2125_summary)(2025))

    assert "Line 8523" in out and "× 50% (ITA s.67.1) = $500.00" in out    # meals 50%
    assert "Line 9281" in out and "× 60%" in out                           # vehicle business-use
    assert "Line 9945 — Business-use-of-home: $300.00" in out              # home → 9945
    assert "$1,500.00 × 20.00% business use" in out
    assert "Line 9281" in out                                              # motor vehicle, not US "Line 9"
    assert "Line 30" not in out and "Form 8829" not in out                 # CA labels, not US
    assert "Does not reconcile" not in out                                 # conservation holds


def test_owner_draws_excludes_opening_balance_equity():
    """P0: Opening Balance Equity carries QuickBooks' own deletion-adjustment JEs,
    not owner activity. On a contributions-only book it must NOT appear and must
    not invert the net to a phantom 'draw'. Retained Earnings likewise excluded."""
    accts = [
        {"Id": "13", "Name": "Owner investments", "AccountType": "Equity",
         "AccountSubType": "OwnersEquity"},
        {"Id": "20", "Name": "Opening balance equity", "AccountType": "Equity",
         "AccountSubType": "OpeningBalanceEquity"},
        {"Id": "21", "Name": "Retained earnings", "AccountType": "Equity",
         "AccountSubType": "RetainedEarnings"},
    ]
    cols = {"Columns": {"Column": [
        {"ColTitle": "Date", "MetaData": [{"Name": "ColKey", "Value": "tx_date"}]},
        {"ColTitle": "Amount", "ColType": "Money",
         "MetaData": [{"Name": "ColKey", "Value": "subt_nat_amount"}]},
        {"ColTitle": "Balance", "ColType": "Money",
         "MetaData": [{"Name": "ColKey", "Value": "rbal_nat_amount"}]}]}}

    def gl_for(acct_name, rows):
        return {**cols, "Rows": {"Row": [
            {"Header": {"ColData": [{"value": acct_name}]},
             "Rows": {"Row": rows}}]}}

    owner_gl = gl_for("Owner investments", [
        {"ColData": [{"value": ""}, {"value": ""}, {"value": "0.00"}]},
        {"ColData": [{"value": "2026-02-01"}, {"value": "40000.00"}, {"value": "40000.00"}]},
        {"ColData": [{"value": "2026-05-01"}, {"value": "12005.25"}, {"value": "52005.25"}]}])
    # OBE holds a huge QB deletion-adjustment JE — if counted it inverts the sign.
    obe_gl = gl_for("Opening balance equity", [
        {"ColData": [{"value": ""}, {"value": ""}, {"value": "0.00"}]},
        {"ColData": [{"value": "2026-03-11"}, {"value": "-130741.79"}, {"value": "-130741.79"}]}])

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_req(m, p, params=None, **k):
        acct_id = (params or {}).get("account")
        return obe_gl if acct_id == "20" else owner_gl if acct_id == "13" else \
            {"Rows": {"Row": []}}

    with patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_request", fake_req):
        out = asyncio.run(_unwrap(s.qb_owner_draws)(2026))

    assert "Opening balance equity" not in out.split("Excluded QuickBooks")[0]
    assert "Retained earnings" not in out.split("Excluded QuickBooks")[0]
    assert "Net owner activity: $52,005.25" in out    # positive, not (−$78,736.54)
    assert "net contribution" in out
    assert "net draw" not in out                        # not sign-inverted
    assert "($130,741.79)" not in out                   # the OBE artifact never appears
    assert "Excluded QuickBooks system equity" in out   # disclosed


def test_home_indirect_duplicate_leaf_and_inactive():
    """P0: two accounts share the leaf 'Repairs & maintenance' — one under a
    'Home office' parent, one standalone. The home one routes to Form 8829; the
    standalone STAYS on its operating line (Line 21). And an INACTIVE home account
    (a deleted mortgage) still routes — the chart lookup must include inactive."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "80000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "80000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Repairs & maintenance"}, {"value": "2316.68"}]},
             {"Header": {"ColData": [{"value": "Home office"}]},
              "Rows": {"Row": [
                  {"ColData": [{"value": "Repairs & maintenance"}, {"value": "2116.19"}]},
                  {"ColData": [{"value": "Mortgage interest (deleted)"}, {"value": "3613.41"}]},
                  {"ColData": [{"value": "Property taxes"}, {"value": "1115.84"}]}]},
              "Summary": {"ColData": [{"value": "Total Home office"}, {"value": "6845.44"}]}}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "9162.12"}]}},
    ]}}
    # The deleted mortgage account is INACTIVE — only returned with Active IN (true,false).
    accts = [
        {"Name": "Repairs & maintenance", "AccountSubType": "RepairMaintenance",
         "FullyQualifiedName": "Repairs & maintenance", "Active": True},
        {"Name": "Repairs & maintenance", "AccountSubType": "RepairsAndMaintainceHomeOffice",
         "FullyQualifiedName": "Home office:Repairs & maintenance", "Active": True},
        {"Name": "Mortgage interest (deleted)", "AccountSubType": "InterestPaid",
         "FullyQualifiedName": "Home office:Mortgage interest (deleted)", "Active": False},
        {"Name": "Property taxes", "AccountSubType": "PropertyTaxHomeOffice",
         "FullyQualifiedName": "Home office:Property taxes", "Active": True},
    ]

    async def fake_req(m, p, params=None, **k):
        return pl

    captured = {}

    async def fake_all(q, **k):
        captured["q"] = q
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D"}]}}

    async def fake_profile(y):
        return {"home_office": {"percentage": 0.125, "basis_note": "300/2400"}}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(_unwrap(s.qb_schedule_c)("2025"))

    # chart lookup asked for inactive accounts
    assert "Active IN (true, false)" in captured["q"]
    # home base = 2116.19 + 3613.41 + 1115.84 = 6845.44 (NOT 4432.87 with both repairs)
    assert "$6,845.44 × 12.50%" in out
    # standalone repairs stayed on Line 21 at 100% — did NOT get swept into home
    assert "Line 21" in out and "2,316.68" in out
    # the inactive mortgage did NOT stay on the interest line at 100%
    assert "3,613.41" not in out.split("× 12.50%")[0]   # not deducted in full anywhere above home
    assert "Does not reconcile" not in out


def test_list_vendors_discloses_truncation_and_pages_all():
    """qb_list_vendors must page ALL vendors (not a bare MAXRESULTS 50 that stops
    mid-alphabet) and disclose truncation instead of silently capping at 50."""
    vendors = [{"Id": str(i), "DisplayName": f"Vendor {i:03d}", "Active": True}
               for i in range(60)]
    seen = {}

    async def fake_query_all(q, **k):
        seen["q"] = q
        return {"QueryResponse": {"Vendor": vendors}}

    # If the tool wrongly used qb_query (bounded), this would be called instead.
    async def fake_query(q):
        seen["bounded"] = q
        return {"QueryResponse": {"Vendor": vendors[:50]}}

    with patch.object(s, "qb_query_all", fake_query_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_demo_active", lambda: False):
        out = asyncio.run(_unwrap(s.qb_list_vendors)("", 50))

    assert "bounded" not in seen                     # did NOT use a bounded query
    assert "MAXRESULTS" not in seen["q"]             # full paginating fetch
    assert "Vendors (60 found)" in out               # true total, not 50
    assert "Showing the first 50 of 60" in out       # truncation disclosed
    assert "Vendor 059" not in out                   # the 60th is not shown
    # max_results=0 shows everything
    with patch.object(s, "qb_query_all", fake_query_all), \
            patch.object(s, "_demo_active", lambda: False):
        allout = asyncio.run(_unwrap(s.qb_list_vendors)("", 0))
    assert "Vendor 059" in allout and "Showing the first" not in allout


def test_inactivate_and_account_txns_resolve_exact_over_partial():
    """qb_inactivate_account / qb_account_transactions now use the shared resolver:
    an exact 'Utilities' resolves cleanly instead of colliding with 'Home
    utilities' under a bare LIKE."""
    utilities = {"Id": "25", "Name": "Utilities", "AccountType": "Expense",
                 "AccountSubType": "Utilities", "FullyQualifiedName": "Utilities",
                 "SyncToken": "0", "Active": True, "CurrentBalance": 0.0}

    async def fake_query(q):
        # _resolve_account tries exact Name first; return the single exact match.
        if "Name = 'Utilities'" in q:
            return {"QueryResponse": {"Account": [utilities]}}
        return {"QueryResponse": {"Account": []}}

    posted = {}

    async def fake_request(m, p, json_body=None, **k):
        posted["body"] = json_body
        return {"Account": {**utilities, "Active": False}}

    with patch.object(s, "qb_query", fake_query), \
            patch.object(s, "qb_request", fake_request), \
            patch.object(s, "_demo_active", lambda: False):
        out = asyncio.run(_unwrap(s.qb_inactivate_account)("Utilities"))

    assert "has been inactivated" in out
    assert posted["body"]["Id"] == "25" and posted["body"]["Active"] is False


def test_allocation_profile_leaf_keys_apply_to_fqn_accounts():
    """REGRESSION: the FQN extractor change made Schedule C look up
    'Communications:Cell phone' while the profile stores the leaf 'Cell phone'.
    The % must still apply (match on leaf OR FQN), and a truly-unmatched
    configured key must be surfaced — never silently ignored under 'not
    configured'."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "50000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "50000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"Header": {"ColData": [{"value": "Communications"}]},
              "Rows": {"Row": [{"ColData": [{"value": "Cell phone"}, {"value": "1000.00"}]}]},
              "Summary": {"ColData": [{"value": "Total Communications"}, {"value": "1000.00"}]}}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "1000.00"}]}},
    ]}}
    accts = [{"Name": "Cell phone", "AccountSubType": "Utilities",
              "FullyQualifiedName": "Communications:Cell phone", "Active": True}]

    async def fake_req(m, p, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D"}]}}

    async def fake_profile(y):
        # Leaf-named keys, as the profile actually stores them. One matches an
        # account (Cell phone); one matches nothing (should be surfaced).
        return {"account_allocations": {
            "Cell phone": {"percentage": 0.75, "basis_note": "75% business"},
            "Ghost account": {"percentage": 0.5}}}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(_unwrap(s.qb_schedule_c)("2025"))

    # the 75% applied ($1,000 × 75% = $750), NOT deducted at 100%
    assert "× 75%" in out and "$750.00" in out
    # the unmatched configured key is surfaced loudly
    assert "match NO account" in out and "Ghost account" in out
    # and 'Cell phone' (which DID match) is not in the unmatched section
    unmatched_section = out.split("match NO account")[1]
    assert "Cell phone" not in unmatched_section


def test_deduction_finder_respects_loss_and_profile():
    """P0-2: at a loss, income-limited deductions resolve to $0 (not fabricated
    gross values), and a configured home office is reported as CONFIGURED (read
    from the profile) rather than '🔴 NOT CLAIMED — $1,500'."""
    pl = {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Sales"}, {"value": "5000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"}, {"value": "5000.00"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": [
             {"ColData": [{"value": "Advertising"}, {"value": "9500.00"}]},
             {"ColData": [{"value": "Business meals"}, {"value": "2000.00"}]}]},
         "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "11500.00"}]}},
    ]}}
    accts = [
        {"Name": "Advertising", "AccountSubType": "AdvertisingPromotional", "FullyQualifiedName": "Advertising"},
        {"Name": "Business meals", "AccountSubType": "EntertainmentMeals", "FullyQualifiedName": "Business meals"},
    ]

    async def fake_req(m, p, params=None, **k):
        return pl

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": accts}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "D", "Country": "US"}]}}

    async def fake_profile(y):
        return {"home_office": {"percentage": 0.125, "basis_note": "300/2400"}}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(_unwrap(s.qb_deduction_finder)("2025"))

    # canonical net reflects LIMITED meals: 5000 − (10000 + 1000) = −6000 loss
    assert "a loss" in out
    # home office read from the profile → CONFIGURED, not a $1,500 "NOT CLAIMED"
    assert "CONFIGURED" in out
    assert "$1,500" not in out
    # income-limited items resolve to $0 this year, not fabricated gross values
    assert "$6,000" not in out and "$6000" not in out     # no invented SE-health value
    assert "$0 this year" in out or "$0 (it does not carry" in out
    # no fabricated education/vehicle dollar estimates summed into a savings promise
    assert "Potential tax savings: ~$2,633.97" not in out
