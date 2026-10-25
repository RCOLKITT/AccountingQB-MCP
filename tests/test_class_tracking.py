"""Read-side class tracking + the Bill vendor fix (reported by a CPA auditing
class-coded books). Locks that every read path surfaces the class on each line,
that Bills show their vendor (was '(no vendor)' because the code read EntityRef
instead of VendorRef), and that qb_list_bills pages past the old 200/1000 cap."""

import asyncio

import accountingqb.server as s

CLASS_A = "Wahous Wilderness Lodge"
CLASS_B = "Ahous Adventures"


async def _no_multicurrency():
    return False


def _bill(bill_id, vendor, acct_id, acct_name, amount, cls):
    return {
        "Id": bill_id,
        "TxnDate": "2026-07-15",
        "TotalAmt": amount,
        "Balance": 0,
        "DueDate": "2026-08-15",
        "VendorRef": {"value": "500", "name": vendor},
        "Line": [
            {
                "Amount": amount,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": acct_id, "name": acct_name},
                    "ClassRef": {"value": "9", "name": cls},
                },
            }
        ],
    }


# --- qb_transaction_detail: class on each line -----------------------------


def test_transaction_detail_shows_class(monkeypatch):
    bill = _bill("17677", "Acme Co", "1150040006", "Work in progress", 1200.0, CLASS_A)

    async def fake_read(entity, entity_id):
        return {"Bill": bill}

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "_multicurrency_enabled", _no_multicurrency)
    out = asyncio.run(s.qb_transaction_detail("Bill", "17677"))
    assert "Work in progress" in out
    assert f"Class: {CLASS_A}" in out  # the gap Shayla reported


# --- qb_list_bills: class per line + full pagination -----------------------


def test_list_bills_class_and_no_silent_cap(monkeypatch):
    # 250 bills — past the old 200 cap. qb_query_all returns them all.
    bills = [
        _bill(str(18000 + i), f"Vendor {i}", "1150040006", "WIP", 100.0 + i, CLASS_B)
        for i in range(250)
    ]

    async def fake_query_all(query, **kw):
        assert "FROM Bill" in query
        return {"QueryResponse": {"Bill": bills}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_multicurrency_enabled", _no_multicurrency)
    out = asyncio.run(s.qb_list_bills("2026-07-01", "2026-08-31", max_results=500))
    assert f"[class: {CLASS_B}]" in out  # class surfaced per line
    assert "(250 bills" in out  # count reflects ALL, not a 200 cap


def test_list_bills_display_cap_notes_remainder(monkeypatch):
    bills = [
        _bill(str(18000 + i), f"V{i}", "1", "WIP", 10.0, CLASS_A) for i in range(60)
    ]

    async def fake_query_all(query, **kw):
        return {"QueryResponse": {"Bill": bills}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_multicurrency_enabled", _no_multicurrency)
    out = asyncio.run(s.qb_list_bills("2026-07-01", "2026-08-31", max_results=50))
    # All 60 counted, only 50 displayed, with a clear note.
    assert "(60 bills" in out and "showing the first 50" in out


# --- qb_account_transactions: vendor fix + class column --------------------


def test_account_transactions_vendor_and_class(monkeypatch):
    acct = {
        "Id": "1150040006",
        "Name": "Work in progress",
        "AccountType": "Other Current Asset",
        "AccountSubType": "",
        "Active": True,
        "CurrentBalance": 5000.0,
    }
    bill = _bill("18924", "Maaqutusiis Supplier", "1150040006", "WIP", 800.0, CLASS_A)

    async def fake_resolve(name, **kw):
        return acct, None

    async def fake_query_all(query, **kw):
        if "FROM Bill " in query or query.strip().startswith("SELECT * FROM Bill"):
            return {"QueryResponse": {"Bill": [bill]}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(
        s.qb_account_transactions("Work in progress", "2026-07-01", "2026-08-31")
    )
    # Vendor is read from VendorRef now (was "(no vendor)" on every Bill).
    assert "Maaqutusiis Supplier" in out
    assert "(no vendor)" not in out
    # Class column carries the line's class.
    assert CLASS_A in out
    assert "| Class |" in out


# --- report tools: class column renders ------------------------------------


def _report_with_class():
    return {
        "Header": {"StartPeriod": "2026-07-01", "EndPeriod": "2026-08-31"},
        "Columns": {
            "Column": [
                {"ColTitle": "Date", "ColType": "tx_date"},
                {"ColTitle": "Transaction Type", "ColType": "txn_type"},
                {"ColTitle": "Name", "ColType": "name"},
                {"ColTitle": "Class", "ColType": "klass_name"},
                {"ColTitle": "Amount", "ColType": "subt_nat_amount"},
            ]
        },
        "Rows": {
            "Row": [
                {
                    "ColData": [
                        {"value": "2026-07-15"},
                        {"value": "Bill"},
                        {"value": "Acme Co"},
                        {"value": CLASS_A},
                        {"value": "1200.00"},
                    ]
                }
            ]
        },
    }


def test_transaction_list_does_not_claim_class(monkeypatch):
    # QBO's TransactionList report silently DROPS klass_name even when asked
    # (verified live on real class-tracked books 2026-10). So the tool must NOT
    # request it — requesting a column QBO ignores is a misleading contract.
    # Class belongs to qb_general_ledger / qb_transaction_detail.
    captured = {}

    async def fake_request(method, endpoint, **kw):
        assert "TransactionList" in endpoint
        captured["columns"] = (kw.get("params", {}) or {}).get("columns", "")
        return _report_with_class()

    monkeypatch.setattr(s, "qb_request", fake_request)
    asyncio.run(s.qb_transaction_list("2026-07-01", "2026-08-31"))
    assert "klass_name" not in captured["columns"]


def test_general_ledger_renders_class_column(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        assert "GeneralLedger" in endpoint
        assert "klass_name" in (kw.get("params", {}) or {}).get("columns", "")
        return _report_with_class()

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_general_ledger("2026-07-01", "2026-08-31"))
    assert "Class" in out and CLASS_A in out
