"""Payroll boundary checklist + bank-reconciliation CSV tie-out."""

import asyncio

import accountingqb.server as s


def test_payroll_checklist_detects_wages(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        if "ProfitAndLoss" in endpoint:
            return {
                "Rows": {
                    "Row": [
                        {
                            "Header": {"ColData": [{"value": "Expenses"}]},
                            "Rows": {
                                "Row": [
                                    {
                                        "ColData": [
                                            {"value": "Wages & Salaries"},
                                            {"value": "820.00"},
                                        ]
                                    },
                                    {
                                        "ColData": [
                                            {"value": "Rent"},
                                            {"value": "1200.00"},
                                        ]
                                    },
                                ]
                            },
                            "Summary": {
                                "ColData": [
                                    {"value": "Total Expenses"},
                                    {"value": "2020.00"},
                                ]
                            },
                        }
                    ]
                }
            }
        return {}

    async def fake_query(q, **kw):
        if "Vendor1099 = true" in q:
            return {"QueryResponse": {"Vendor": [{"Id": "1"}, {"Id": "2"}]}}
        if "Liability" in q:
            return {
                "QueryResponse": {
                    "Account": [{"Name": "Payroll Tax Payable", "CurrentBalance": 63.0}]
                }
            }
        return {"QueryResponse": {}}

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    out = asyncio.run(s.qb_payroll_checklist("2025"))
    assert "Wages/salaries booked" in out and "820" in out
    assert "Form 941" in out and "W-2" in out
    assert "Payroll Tax Payable" in out
    assert "Contractors flagged for 1099:** 2" in out


def test_bank_rec_tie_out(monkeypatch):
    csv_data = (
        "Date,Description,Amount\n"
        "2026-03-01,Coffee Shop,12.50\n"  # matches book
        "2026-03-02,AWS,340.00\n"  # matches book
        "2026-03-03,Unknown Charge,99.99\n"  # NOT in books
    )

    async def fake_query(q, **kw):
        if "FROM Purchase" in q:
            return {
                "QueryResponse": {
                    "Purchase": [
                        {
                            "Id": "1",
                            "TxnDate": "2026-03-01",
                            "TotalAmt": 12.50,
                            "EntityRef": {"name": "Coffee Shop"},
                        },
                        {
                            "Id": "2",
                            "TxnDate": "2026-03-02",
                            "TotalAmt": 340.00,
                            "EntityRef": {"name": "AWS"},
                        },
                        {
                            "Id": "3",
                            "TxnDate": "2026-03-05",
                            "TotalAmt": 500.00,
                            "EntityRef": {"name": "Uncleared Vendor"},
                        },  # in books, not on stmt
                    ]
                }
            }
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_bank_reconciliation("Checking", csv_data))
    assert "Matched:** 2" in out
    assert "In statement, not in books:** 1" in out
    assert "Unknown Charge" in out
    assert "Uncleared Vendor" in out  # in books, not on statement


def test_new_tools_registered():
    for name in ("qb_payroll_checklist", "qb_bank_reconciliation"):
        assert name in s.mcp._tool_manager._tools
