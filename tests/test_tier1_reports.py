"""Tier-1 native report tools: correct QBO report endpoint names (a wrong name
is a 400 in prod) and the column-aware table formatter."""

import asyncio

import accountingqb.server as s


def _report(cols, groups):
    """Build a QBO-shaped report: columns + sections (label, data rows, summary)."""
    rows = []
    for label, datarows, summ in groups:
        sec = {
            "Header": {"ColData": [{"value": label}]},
            "Rows": {"Row": [{"ColData": [{"value": v} for v in r]} for r in datarows]},
        }
        if summ:
            sec["Summary"] = {"ColData": [{"value": v} for v in summ]}
        rows.append(sec)
    return {
        "Header": {"StartPeriod": "2026-01-01", "EndPeriod": "2026-12-31"},
        "Columns": {"Column": [{"ColTitle": c} for c in cols]},
        "Rows": {"Row": rows},
    }


# ---- column-aware formatter ------------------------------------------------


def test_format_report_table_keeps_all_columns():
    rep = _report(
        ["Date", "Transaction Type", "Amount"],
        [
            (
                "Acme Co",
                [
                    ["2026-01-05", "Invoice", "1,000.00"],
                    ["2026-02-01", "Invoice", "500.00"],
                ],
                ["Total for Acme Co", "", "1,500.00"],
            ),
        ],
    )
    lines = []
    s._format_report_table(rep, lines)
    out = "\n".join(lines)
    assert "| Date | Transaction Type | Amount |" in out  # every column kept
    assert "| **Acme Co** |" in out  # group header bolded
    assert "| 2026-01-05 | Invoice | 1,000.00 |" in out  # middle column preserved
    assert "**1,500.00**" in out  # summary bolded


def test_format_report_table_truncates():
    big = [["2026-01-01", "Invoice", str(i)] for i in range(10)]
    rep = _report(["Date", "Type", "Amount"], [("G", big, None)])
    lines = []
    s._format_report_table(rep, lines, max_rows=3)
    out = "\n".join(lines)
    assert "Showing the first 3 rows" in out
    assert out.count("| 2026-01-01 | Invoice |") == 3  # capped


def test_format_report_table_falls_back_without_columns():
    # No Columns metadata -> summary parser (name: amount), not a broken table.
    rep = {"Rows": {"Row": [{"ColData": [{"value": "Income"}, {"value": "100.00"}]}]}}
    lines = []
    s._format_report_table(rep, lines)
    assert any("Income" in ln for ln in lines)


# ---- endpoint wiring (the wrong-name risk) ---------------------------------


def _capture(monkeypatch):
    seen = {}

    async def fake_request(method, endpoint, params=None, json_body=None):
        seen["endpoint"] = endpoint
        seen["params"] = params or {}
        return _report(["Name", "Total"], [("", [["Acme", "1,000.00"]], None)])

    monkeypatch.setattr(s, "qb_request", fake_request)
    return seen


def test_report_tools_use_exact_endpoint_names(monkeypatch):
    seen = _capture(monkeypatch)
    cases = [
        (
            lambda: s.qb_sales_by_customer("2026-01-01", "2026-12-31"),
            "reports/SalesByCustomer",
        ),
        (
            lambda: s.qb_sales_by_product("2026-01-01", "2026-12-31"),
            "reports/SalesByProduct",
        ),
        (
            lambda: s.qb_profit_loss_detail("2026-01-01", "2026-12-31"),
            "reports/ProfitAndLossDetail",
        ),
        (
            lambda: s.qb_transaction_list("2026-01-01", "2026-12-31"),
            "reports/TransactionList",
        ),
        (
            lambda: s.qb_customer_balance_detail("2026-06-30"),
            "reports/CustomerBalanceDetail",
        ),
        (
            lambda: s.qb_vendor_balance_detail("2026-06-30"),
            "reports/VendorBalanceDetail",
        ),
    ]
    for call, expected in cases:
        asyncio.run(call())
        assert seen["endpoint"] == expected, f"{expected} != {seen['endpoint']}"


def test_balance_detail_passes_report_date(monkeypatch):
    seen = _capture(monkeypatch)
    asyncio.run(s.qb_customer_balance_detail("2026-06-30"))
    assert seen["params"].get("report_date") == "2026-06-30"


def test_sales_tools_pass_date_range(monkeypatch):
    seen = _capture(monkeypatch)
    asyncio.run(s.qb_sales_by_customer("2026-01-01", "2026-03-31"))
    assert seen["params"]["start_date"] == "2026-01-01"
    assert seen["params"]["end_date"] == "2026-03-31"


def test_accrual_basis_maps_through(monkeypatch):
    seen = _capture(monkeypatch)
    asyncio.run(s.qb_profit_loss_detail("2026-01-01", "2026-12-31", "accrual"))
    assert seen["params"].get("accounting_method") == "Accrual"
