"""The bookkeeping-automation batch (v3.27.0) — a CPA user's 10-item report
after closing two corporations' books. Each test reproduces the gap he hit."""

import asyncio
import json

import accountingqb.server as s


async def _us_region():
    return {"region": "US", "multicurrency": False}


async def _ca_region():
    return {"region": "CA", "multicurrency": False}


async def _no_dup(*a, **k):
    return None


def _wire_create(monkeypatch, posts, *, region=_us_region, query_responses=None):
    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append((method, endpoint, json_body))
        key = {
            "invoice": "Invoice",
            "salesreceipt": "SalesReceipt",
            "journalentry": "JournalEntry",
            "deposit": "Deposit",
            "purchase": "Purchase",
        }.get(endpoint, endpoint)
        return {key: {"Id": "77", "TotalAmt": 100.0, "DocNumber": "N-1"}}

    async def fake_query(q, **kw):
        for frag, resp in (query_responses or {}).items():
            if frag in q:
                return resp
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", region)
    monkeypatch.setattr(s, "_duplicate_guard", _no_dup)


CUSTOMER = {
    "QueryResponse": {"Customer": [{"Id": "9", "DisplayName": "Stripe Customer"}]}
}


# --- item 1: invoice date + number -------------------------------------------


def test_invoice_sets_txn_date_and_doc_number(monkeypatch):
    posts = []
    _wire_create(monkeypatch, posts, query_responses={"FROM Customer": CUSTOMER})
    out = asyncio.run(
        s.qb_create_invoice(
            "Stripe Customer",
            json.dumps([{"description": "June services", "amount": 100}]),
            txn_date="2026-06-15",
            invoice_number="STR-1042",
        )
    )
    assert "created" in out.lower()
    body = next(b for m, e, b in posts if e == "invoice")
    assert body["TxnDate"] == "2026-06-15"  # historical date, not today
    assert body["DocNumber"] == "STR-1042"  # explicit number, not auto


# --- item 2: sales receipts ---------------------------------------------------


def test_sales_receipt_created_with_date_number_and_deposit_target(monkeypatch):
    posts = []
    accounts = {
        "QueryResponse": {
            "Account": [{"Id": "35", "Name": "Chequing", "AccountType": "Bank"}]
        }
    }

    async def fake_resolve(name, **kw):
        return {"Id": "35", "Name": "Chequing"}, None

    _wire_create(monkeypatch, posts, query_responses={"FROM Customer": CUSTOMER})
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    out = asyncio.run(
        s.qb_create_sales_receipt(
            "Stripe Customer",
            json.dumps([{"description": "Subscription", "amount": 100}]),
            txn_date="2026-06-15",
            receipt_number="SR-88",
            deposit_to_account="Chequing",
        )
    )
    assert "Sales receipt created" in out
    body = next(b for m, e, b in posts if e == "salesreceipt")
    assert body["TxnDate"] == "2026-06-15"
    assert body["DocNumber"] == "SR-88"
    assert body["DepositToAccountRef"]["value"] == "35"
    assert body["Line"][0]["DetailType"] == "SalesItemLineDetail"


def test_sales_receipt_ca_requires_tax_code(monkeypatch):
    posts = []
    _wire_create(
        monkeypatch,
        posts,
        region=_ca_region,
        query_responses={"FROM Customer": CUSTOMER},
    )
    out = asyncio.run(
        s.qb_create_sales_receipt(
            "Stripe Customer", json.dumps([{"description": "Sub", "amount": 100}])
        )
    )
    # Canadian edition refuses a sale with no tax code — the exact cause of the
    # misstated GST/HST lines when sales went in as deposits instead.
    assert posts == [] or all(e != "salesreceipt" for _, e, _ in posts)
    assert "tax" in out.lower()


# --- item 3: deposits — linked UF payments + customer on lines ----------------


def test_deposit_links_undeposited_funds_payments(monkeypatch):
    posts = []

    async def fake_resolve(name, **kw):
        return {"Id": "35", "Name": "Chequing"}, None

    _wire_create(monkeypatch, posts)
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    out = asyncio.run(
        s.qb_create_deposit(
            "2026-06-20",
            "Chequing",
            linked_txns_json=json.dumps(
                [
                    {"txn_id": "501", "txn_type": "Payment", "amount": 60.0},
                    {"txn_id": "502", "txn_type": "SalesReceipt", "amount": 40.0},
                ]
            ),
        )
    )
    assert "Linked from Undeposited Funds: 2" in out
    body = next(b for m, e, b in posts if e == "deposit")
    linked = [l for l in body["Line"] if "LinkedTxn" in l]
    assert [l["LinkedTxn"][0]["TxnId"] for l in linked] == ["501", "502"]
    assert linked[0]["LinkedTxn"][0]["TxnType"] == "Payment"


def test_deposit_line_carries_customer(monkeypatch):
    posts = []

    async def fake_resolve(name, **kw):
        return {"Id": "35", "Name": "Chequing"}, None

    async def fake_entity(kind, name):
        assert (kind, name) == ("Customer", "Stripe Customer")
        return {"value": "9", "name": "Stripe Customer"}, None

    _wire_create(monkeypatch, posts)
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    monkeypatch.setattr(s, "_resolve_name_entity", fake_entity)
    asyncio.run(
        s.qb_create_deposit(
            "2026-06-20",
            "Chequing",
            lines_json=json.dumps(
                [
                    {
                        "account_name": "Sales",
                        "amount": 100.0,
                        "customer_name": "Stripe Customer",
                    }
                ]
            ),
        )
    )
    body = next(b for m, e, b in posts if e == "deposit")
    detail = body["Line"][0]["DepositLineDetail"]
    assert detail["Entity"] == {"value": "9", "name": "Stripe Customer"}


# --- items 4+5: JE line names + tax codes --------------------------------------


def _wire_je(monkeypatch, posts, region=_ca_region):
    async def fake_read(entity, entity_id):
        return {"Account": {"Id": entity_id, "Name": f"Acct{entity_id}"}}

    async def fake_resolve_acct(name, **kw):
        return {"Id": "1", "Name": name, "AccountType": "Accounts Payable"}, None

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append((method, endpoint, json_body))
        return {"JournalEntry": {"Id": "321", "TotalAmt": 100.0}}

    async def fake_tax(code):
        assert code == "HST ON"
        return "5", "HST ON"

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "_resolve_account", fake_resolve_acct)
    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "_resolve_tax_code", fake_tax)
    monkeypatch.setattr(s, "_get_region", region)
    monkeypatch.setattr(s, "_duplicate_guard", _no_dup)


def test_je_line_carries_vendor_entity_and_tax_code(monkeypatch):
    posts = []
    _wire_je(monkeypatch, posts)

    async def fake_entity(kind, name):
        return {"value": "44", "name": name}, None

    monkeypatch.setattr(s, "_resolve_name_entity", fake_entity)
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-06-30",
            json.dumps(
                [
                    {
                        "account_name": "Accounts Payable",
                        "amount": 100,
                        "type": "Debit",
                        "vendor_name": "Wedler Engineering",
                        "tax_code": "HST ON",
                    },
                    {
                        "account_name": "Shareholder Loan",
                        "amount": 100,
                        "type": "Credit",
                    },
                ]
            ),
        )
    )
    assert "created" in out.lower()
    body = next(b for m, e, b in posts if e == "journalentry")
    d0 = body["Line"][0]["JournalEntryLineDetail"]
    assert d0["Entity"] == {
        "Type": "Vendor",
        "EntityRef": {"value": "44", "name": "Wedler Engineering"},
    }
    assert d0["TaxCodeRef"] == {"value": "5"}
    assert d0["TaxApplicableOn"] == "Purchase"  # debit default
    assert "Entity" not in body["Line"][1]["JournalEntryLineDetail"]


def test_je_tax_code_refused_for_us_books(monkeypatch):
    posts = []
    _wire_je(monkeypatch, posts, region=_us_region)
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-06-30",
            json.dumps(
                [
                    {
                        "account_name": "A",
                        "amount": 10,
                        "type": "Debit",
                        "tax_code": "HST ON",
                    },
                    {"account_name": "B", "amount": 10, "type": "Credit"},
                ]
            ),
        )
    )
    assert "Canada/global" in out and posts == []


# --- item 6: expense to a balance-sheet account --------------------------------


def test_expense_accepts_balance_sheet_category(monkeypatch):
    posts = []
    vendors = {"QueryResponse": {"Vendor": [{"Id": "7", "DisplayName": "Owner Draw"}]}}
    calls = {"n": 0}

    async def fake_resolve(name, *, account_type=""):
        calls["n"] += 1
        if account_type == "Expense":
            return None, f"No Expense account matches '{name}'."
        return {
            "Id": "88",
            "Name": "Shareholder Loan",
            "AccountType": "Long Term Liability",
        }, None

    _wire_create(monkeypatch, posts, query_responses={"FROM Vendor": vendors})
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    out = asyncio.run(
        s.qb_create_expense("Owner Draw", 250.0, "Shareholder Loan", "2026-06-01")
    )
    assert "Expense created" in out
    assert "Long Term Liability" in out  # the honest note about the category
    assert calls["n"] == 2  # expense-first, then any-type fallback


# --- item 7: duplicate guard ----------------------------------------------------


def test_duplicate_guard_refuses_and_allows(monkeypatch):
    hits = {
        "QueryResponse": {
            "Purchase": [{"Id": "900", "DocNumber": "X1", "TotalAmt": 250.0}]
        }
    }

    async def fake_query(q, **kw):
        assert "TxnDate = '2026-06-01'" in q and "TotalAmt = '250.00'" in q
        return hits

    monkeypatch.setattr(s, "qb_query", fake_query)
    msg = asyncio.run(s._duplicate_guard("Purchase", "2026-06-01", 250.0, False))
    assert msg and "duplicate" in msg.lower() and "900" in msg
    # allow_duplicate skips the check entirely
    assert (
        asyncio.run(s._duplicate_guard("Purchase", "2026-06-01", 250.0, True)) is None
    )


def test_duplicate_guard_fails_open(monkeypatch):
    async def broken_query(q, **kw):
        raise RuntimeError("QBO down")

    monkeypatch.setattr(s, "qb_query", broken_query)
    assert (
        asyncio.run(s._duplicate_guard("Purchase", "2026-06-01", 250.0, False)) is None
    )


# --- item 8: bank rec sees transfers --------------------------------------------


def test_bank_rec_includes_transfers(monkeypatch):
    queried = []

    async def fake_query_all(q, **kw):
        for ent in (
            "Purchase",
            "BillPayment",
            "Deposit",
            "Payment",
            "SalesReceipt",
            "JournalEntry",
            "Transfer",
        ):
            if f"FROM {ent} " in q:
                queried.append(ent)
                if ent == "Transfer":
                    return {
                        "QueryResponse": {
                            "Transfer": [
                                {
                                    "Id": "77",
                                    "TxnDate": "2026-06-10",
                                    "Amount": 500.0,  # Transfer has Amount, not TotalAmt
                                    "FromAccountRef": {"name": "Chequing"},
                                    "ToAccountRef": {"name": "Savings"},
                                }
                            ]
                        }
                    }
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(
        s.qb_bank_reconciliation(
            "Chequing",
            "Date,Description,Amount\n2026-06-10,TRANSFER TO SAVINGS,-500.00",
        )
    )
    assert "Transfer" in queried  # the missing entity type is now swept
    # The in-books transfer matches the statement line instead of being
    # reported as a missing book entry (which caused duplicate re-entry).
    assert "**Matched:** 1" in out
    assert "not in books:** 0" in out


# --- item 9: active-company footer ----------------------------------------------


def test_company_footer_names_active_company_when_multi(monkeypatch):
    from accountingqb.context import QBContext, reset_ctx, set_ctx

    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.realm_id = "222"
    ctx.hosted_companies = [
        {"realmId": "111", "companyName": "OPSTART, INC."},
        {"realmId": "222", "companyName": "Reign Innovations Inc."},
    ]
    token = set_ctx(ctx)
    try:

        async def tool():
            return "## Balance Sheet"

        wrapped = s.company_context_footer(tool)
        out = asyncio.run(wrapped())
        assert "Active company: Reign Innovations Inc." in out
    finally:
        reset_ctx(token)


def test_company_footer_silent_for_single_company(monkeypatch):
    from accountingqb.context import QBContext, reset_ctx, set_ctx

    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.realm_id = "111"
    ctx.hosted_companies = [{"realmId": "111", "companyName": "Solo Co"}]
    token = set_ctx(ctx)
    try:

        async def tool():
            return "## P&L"

        out = asyncio.run(s.company_context_footer(tool)())
        assert "Active company" not in out  # no noise for single-company users
    finally:
        reset_ctx(token)


# --- item 10: monthly P&L renders period columns --------------------------------


def test_profit_loss_monthly_renders_period_columns(monkeypatch):
    report = {
        "Header": {"StartPeriod": "2026-01-01", "EndPeriod": "2026-03-31"},
        "Columns": {
            "Column": [
                {"ColTitle": "", "ColType": "Account"},
                {"ColTitle": "Jan 2026", "ColType": "Money"},
                {"ColTitle": "Feb 2026", "ColType": "Money"},
                {"ColTitle": "Mar 2026", "ColType": "Money"},
                {"ColTitle": "Total", "ColType": "Money"},
            ]
        },
        "Rows": {
            "Row": [
                {
                    "ColData": [
                        {"value": "Sales"},
                        {"value": "100.00"},
                        {"value": "200.00"},
                        {"value": "300.00"},
                        {"value": "600.00"},
                    ]
                }
            ]
        },
    }

    async def fake_request(method, endpoint, **kw):
        assert kw.get("params", {}).get("summarize_column_by") == "Month"
        return report

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_profit_loss("2026-01-01", "2026-03-31", summarize_by="Month")
    )
    # The old summary parser collapsed these to a single annual column.
    assert "Jan 2026" in out and "Feb 2026" in out and "Mar 2026" in out
    assert "200.00" in out
