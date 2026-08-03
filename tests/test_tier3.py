"""Tier-3 report tools + the P&L-by-dimension enum fix.

The headline: qb_profit_loss_by_class used summarize_column_by='Class' (singular),
which QBO silently ignores — the documented enum is PLURAL ('Classes'). These
lock the plural value and the new PO / VendorExpenses tools."""

import asyncio

import accountingqb.server as s


def _report(cols, rows):
    return {"Header": {"StartPeriod": "2026-01-01", "EndPeriod": "2026-12-31"},
            "Columns": {"Column": [{"ColTitle": c} for c in cols]},
            "Rows": {"Row": rows}}


def _row(vals):
    return {"ColData": [{"value": v} for v in vals]}


def _capture_request(monkeypatch, report):
    seen = {}

    async def fake(method, endpoint, params=None, json_body=None):
        seen["endpoint"] = endpoint
        seen["params"] = params or {}
        return report
    monkeypatch.setattr(s, "qb_request", fake)
    return seen


def test_pl_by_class_uses_plural_enum(monkeypatch):
    seen = _capture_request(
        monkeypatch,
        _report(["", "Retail", "Wholesale", "Total"], [_row(["Income", "100", "50", "150"])]))
    out = asyncio.run(s.qb_profit_loss_by_class("2026-01-01", "2026-12-31"))
    assert seen["endpoint"] == "reports/ProfitAndLoss"
    assert seen["params"]["summarize_column_by"] == "Classes"   # the fix
    assert "Profit & Loss by Class" in out


def test_pl_by_department_uses_plural_enum(monkeypatch):
    seen = _capture_request(
        monkeypatch,
        _report(["", "East", "West", "Total"], [_row(["Income", "1", "2", "3"])]))
    out = asyncio.run(s.qb_profit_loss_by_department("2026-01-01", "2026-12-31"))
    assert seen["params"]["summarize_column_by"] == "Departments"
    assert "Profit & Loss by Department" in out


def test_pl_by_class_empty_when_no_classes(monkeypatch):
    _capture_request(monkeypatch, _report(["", "Total"], []))  # <=2 columns
    out = asyncio.run(s.qb_profit_loss_by_class("2026-01-01", "2026-12-31"))
    assert "No class breakdown available" in out


def test_pl_by_department_not_specified_only(monkeypatch):
    # Tracking OFF: QuickBooks returns an ungrouped P&L under a single
    # "Not Specified" column — must be reported as unavailable, not a
    # single-department result.
    _capture_request(monkeypatch, _report(
        ["", "Not Specified", "Total"],
        [_row(["Sales", "195.00", "195.00"])]))
    out = asyncio.run(s.qb_profit_loss_by_department("2026-01-01", "2026-12-31"))
    assert "No department breakdown available" in out
    assert "NOT a single-department" in out


def test_vendor_expenses_endpoint(monkeypatch):
    seen = _capture_request(
        monkeypatch, _report(["Vendor", "Total"], [_row(["Amazon", "500"])]))
    out = asyncio.run(s.qb_vendor_expenses("2026-01-01", "2026-12-31"))
    assert seen["endpoint"] == "reports/VendorExpenses"
    assert "Vendor Expenses" in out


def test_purchase_orders_list_and_status_filter(monkeypatch):
    pos = [
        {"Id": "1", "TxnDate": "2026-05-01", "DocNumber": "PO-1", "TotalAmt": 1000.0,
         "VendorRef": {"name": "Acme"}, "POStatus": "Open"},
        {"Id": "2", "TxnDate": "2026-05-02", "DocNumber": "PO-2", "TotalAmt": 500.0,
         "VendorRef": {"name": "Beta"}, "POStatus": "Closed"},
    ]

    async def fake_all(q, **kw):
        assert "FROM PurchaseOrder" in q
        return {"QueryResponse": {"PurchaseOrder": pos}}
    monkeypatch.setattr(s, "qb_query_all", fake_all)

    out = asyncio.run(s.qb_list_purchase_orders("2026-01-01", "2026-12-31"))
    assert "PO-1" in out and "PO-2" in out and "Acme" in out
    assert "$1,500.00" in out  # total

    open_only = asyncio.run(
        s.qb_list_purchase_orders("2026-01-01", "2026-12-31", status="Open"))
    assert "PO-1" in open_only and "PO-2" not in open_only
