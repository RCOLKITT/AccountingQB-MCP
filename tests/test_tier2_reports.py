"""Tier-2 dimension + inventory reports: exact endpoint/entity wiring (a wrong
report name is a 400 in prod) and graceful empty handling when a company doesn't
use class/location tracking or inventory."""

import asyncio

import accountingqb.server as s


def _report(cols, rows_data):
    return {"Header": {"StartPeriod": "2026-01-01", "EndPeriod": "2026-12-31"},
            "Columns": {"Column": [{"ColTitle": c} for c in cols]},
            "Rows": {"Row": [{"ColData": [{"value": v} for v in r]} for r in rows_data]}}


# ---- entity-list tools -----------------------------------------------------

def test_list_classes_and_departments(monkeypatch):
    async def fake_all(q, **kw):
        if "FROM Class" in q:
            return {"QueryResponse": {"Class": [
                {"Name": "Retail", "FullyQualifiedName": "Retail", "Active": True},
                {"Name": "Wholesale", "FullyQualifiedName": "Wholesale", "Active": False}]}}
        if "FROM Department" in q:
            return {"QueryResponse": {"Department": [
                {"Name": "East", "FullyQualifiedName": "East", "Active": True}]}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query_all", fake_all)

    out_c = asyncio.run(s.qb_list_classes())
    assert "Retail" in out_c and "Wholesale" in out_c and "Inactive" in out_c
    out_d = asyncio.run(s.qb_list_departments())
    assert "East" in out_d and "Departments / Locations (1)" in out_d


def test_list_classes_empty_is_friendly(monkeypatch):
    async def fake_all(q, **kw):
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query_all", fake_all)
    out = asyncio.run(s.qb_list_classes())
    assert "No classes found" in out and "class tracking" in out


# ---- dimension + inventory reports: endpoint wiring ------------------------

def _capture(monkeypatch, report):
    seen = {}

    async def fake_request(method, endpoint, params=None, json_body=None):
        seen["endpoint"] = endpoint
        seen["params"] = params or {}
        return report
    monkeypatch.setattr(s, "qb_request", fake_request)
    return seen


def test_dimension_reports_use_exact_endpoint_names(monkeypatch):
    rep = _report(["", "Retail", "Total"], [["Design income", "1,000.00", "1,000.00"]])
    seen = _capture(monkeypatch, rep)
    cases = [
        (lambda: s.qb_sales_by_class("2026-01-01", "2026-12-31"), "reports/SalesByClassSummary"),
        (lambda: s.qb_sales_by_department("2026-01-01", "2026-12-31"), "reports/SalesByDepartment"),
        (lambda: s.qb_inventory_valuation("2026-06-30"), "reports/InventoryValuationSummary"),
    ]
    for call, expected in cases:
        asyncio.run(call())
        assert seen["endpoint"] == expected, f"{expected} != {seen['endpoint']}"


def test_sales_by_class_renders_all_columns(monkeypatch):
    rep = _report(["", "Retail", "Wholesale", "Total"],
                  [["Design income", "1,000.00", "500.00", "1,500.00"]])
    _capture(monkeypatch, rep)
    out = asyncio.run(s.qb_sales_by_class("2026-01-01", "2026-12-31"))
    assert "| Retail | Wholesale | Total |" in out
    assert "1,000.00" in out and "500.00" in out


def test_inventory_valuation_uses_as_of_date(monkeypatch):
    rep = _report(["", "Qty", "Asset Value"], [["Widget", "10", "250.00"]])
    seen = _capture(monkeypatch, rep)
    asyncio.run(s.qb_inventory_valuation("2026-06-30"))
    assert seen["params"].get("end_date") == "2026-06-30"


def test_dimension_report_empty_is_friendly(monkeypatch):
    _capture(monkeypatch, {"Header": {}, "Columns": {"Column": []}, "Rows": {}})
    out = asyncio.run(s.qb_sales_by_class("2026-01-01", "2026-12-31"))
    assert "class tracking" in out.lower()


def test_accrual_basis_maps_through(monkeypatch):
    seen = _capture(monkeypatch, _report(["", "Total"], [["x", "1.00"]]))
    asyncio.run(s.qb_sales_by_department("2026-01-01", "2026-12-31", "accrual"))
    assert seen["params"].get("accounting_method") == "Accrual"
