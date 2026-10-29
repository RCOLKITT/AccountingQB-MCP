"""Proactive hardening prompted by a CPA's bug reports:
1. List tools must NOT silently cap — qb_list_payments / qb_list_invoices /
   qb_list_transactions used `MAXRESULTS 100` and undercounted busy periods
   (the same class of bug as the bills-200 cap). They now paginate in full and
   the printed count/total reflect EVERY row; max_results caps only display.
2. qb_transaction_list gained a class filter + an unclassed ('Not Specified')
   finder for class cleanup.
3. qb_balance_sheet_by_class — the report she named — renders class columns and
   fails honestly when class tracking is off.
"""

import asyncio

import accountingqb.server as s


async def _no_multicurrency():
    return False


# --- silent-cap fixes -------------------------------------------------------


def test_list_payments_counts_all_not_just_page(monkeypatch):
    payments = [
        {
            "Id": str(i),
            "TxnDate": "2026-03-01",
            "TotalAmt": 10.0,
            "CustomerRef": {"name": f"Cust {i}"},
            "DepositToAccountRef": {"name": "Checking"},
        }
        for i in range(150)
    ]

    async def fake_query_all(query, **kw):
        assert "MAXRESULTS" not in query  # full pagination, no hard cap
        return {"QueryResponse": {"Payment": payments}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_list_payments("2026-01-01", "2026-12-31", max_results=50))
    assert "(150 payments)" in out  # true count, not 50
    assert "showing the first 50" in out
    assert "$1,500.00" in out  # total over ALL 150, not the displayed 50


def test_list_transactions_filters_over_full_set(monkeypatch):
    # 120 purchases; only 40 are >= $100. Count must reflect the 40 matches even
    # though display is capped — and the cap must not truncate before filtering.
    purchases = []
    for i in range(120):
        amt = 100.0 if i < 40 else 10.0
        purchases.append(
            {
                "Id": str(i),
                "TxnDate": "2026-03-01",
                "TotalAmt": amt,
                "EntityRef": {"name": f"V{i}"},
                "Line": [],
            }
        )

    async def fake_query_all(query, **kw):
        assert "MAXRESULTS" not in query
        return {"QueryResponse": {"Purchase": purchases}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_multicurrency_enabled", _no_multicurrency)
    out = asyncio.run(
        s.qb_list_transactions(
            "2026-01-01", "2026-12-31", min_amount=100, max_results=10
        )
    )
    assert "(40 transactions)" in out  # all matches counted
    assert "showing the first 10" in out
    assert "$4,000.00" in out  # 40 × $100


def test_list_invoices_counts_all(monkeypatch):
    invoices = [
        {
            "Id": str(i),
            "TxnDate": "2026-03-01",
            "DueDate": "2026-04-01",
            "DocNumber": str(i),
            "TotalAmt": 20.0,
            "Balance": 0.0,
            "CustomerRef": {"name": f"Cust {i}"},
        }
        for i in range(130)
    ]

    async def fake_query_all(query, **kw):
        assert "MAXRESULTS" not in query
        return {"QueryResponse": {"Invoice": invoices}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_multicurrency_enabled", _no_multicurrency)
    out = asyncio.run(s.qb_list_invoices("2026-01-01", "2026-12-31", max_results=25))
    assert "(130 invoices)" in out
    assert "showing the first 25" in out


# --- qb_transaction_list: class filter + unclassed finder -------------------


def _classed_bill(bill_id, cls):
    detail = {"AccountRef": {"value": "1", "name": "WIP"}}
    if cls:
        detail["ClassRef"] = {"value": "9", "name": cls}
    return {
        "Id": bill_id,
        "TxnDate": "2026-07-15",
        "DocNumber": bill_id,
        "TotalAmt": 100.0,
        "VendorRef": {"name": "Acme"},
        "Line": [
            {
                "Amount": 100.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": detail,
            }
        ],
    }


def test_transaction_list_class_filter(monkeypatch):
    classed = _classed_bill("1", "Ahous Adventures")
    unclassed = _classed_bill("2", "")

    async def fake_query_all(query, **kw):
        if "FROM Bill " in query:
            return {"QueryResponse": {"Bill": [classed, unclassed]}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(
        s.qb_transaction_list("2026-07-01", "2026-08-31", class_name="Ahous")
    )
    assert "Ahous Adventures" in out and "1 transactions" in out
    assert "class ~ 'Ahous'" in out


def test_transaction_list_unclassed_only(monkeypatch):
    classed = _classed_bill("1", "Ahous Adventures")
    unclassed = _classed_bill("2", "")

    async def fake_query_all(query, **kw):
        if "FROM Bill " in query:
            return {"QueryResponse": {"Bill": [classed, unclassed]}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(
        s.qb_transaction_list("2026-07-01", "2026-08-31", unclassed_only=True)
    )
    # Only the unclassed bill (#2) survives; the classed one is excluded.
    assert "1 transactions" in out and "unclassed" in out


# --- qb_balance_sheet_by_class ----------------------------------------------


def _bs_report(columns):
    return {
        "Header": {},
        "Columns": {"Column": [{"ColTitle": c} for c in columns]},
        "Rows": {
            "Row": [
                {
                    "ColData": [{"value": "Checking"}]
                    + [{"value": "1.00"}] * (len(columns) - 1)
                }
            ]
        },
    }


def test_balance_sheet_by_class_renders_when_tracked(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        assert "BalanceSheet" in endpoint
        assert kw["params"]["summarize_column_by"] == "Classes"
        return _bs_report(["", "Ahous Adventures", "Wahous Lodge", "Total"])

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_balance_sheet_by_class("2026-12-31"))
    assert "Balance Sheet by Class" in out


def test_balance_sheet_by_class_honest_when_off(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        # Class tracking off → QBO returns an ungrouped BS (Account + Total only).
        return _bs_report(["", "Total"])

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_balance_sheet_by_class("2026-12-31"))
    assert "No class breakdown available" in out
    assert "qb_balance_sheet" in out
