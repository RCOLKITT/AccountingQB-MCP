"""The silent-MAXRESULTS bug class (user incident, v3.30.0).

Incident shape: qb_list_bill_payments with max_results=500 over a 7-month range
returned exactly 500 payments and a clean-looking "Total Paid" — but QBO sorts
by transaction Id, so the cap silently dropped OLDER payments while the listed
dates still spanned the whole range. Nothing indicated truncation.

The contract now (matching qb_list_bills / qb_list_payments): every list tool
fetches ALL matching rows via qb_query_all; max_results caps only the DISPLAYED
rows; counts and dollar totals always cover the full set; truncated display
carries an explicit "showing the first N" note. All fixtures are fictional.
"""

import asyncio
import inspect
import re

import accountingqb.server as s

# Every list tool that totals/counts across a range must page. (Tools with a
# deliberately bounded read — MAXRESULTS 1 lookups, recent-N previews — are
# exempt per qb_query_all's docstring.)
PAGED_LIST_TOOLS = [
    "qb_list_bills",
    "qb_list_bill_payments",
    "qb_list_payments",
    "qb_list_deposits",
    "qb_list_transfers",
    "qb_list_journal_entries",
    "qb_list_sales_receipts",
    "qb_list_credit_memos",
    "qb_list_vendor_credits",
    "qb_list_estimates",
    "qb_list_items",
    "qb_list_attachments",
    "qb_unknown_vendor_report",
]


def _source(name: str) -> str:
    fn = getattr(s, name)
    return inspect.getsource(getattr(fn, "__wrapped__", fn))


def test_no_list_tool_passes_max_results_into_the_query():
    # The bug class: f"... MAXRESULTS {max_results}" hands the user-visible
    # display knob to QBO as a silent fetch cap.
    for name in PAGED_LIST_TOOLS:
        assert "MAXRESULTS {max_results}" not in _source(name), name


def test_paged_tools_use_qb_query_all():
    for name in PAGED_LIST_TOOLS:
        assert "qb_query_all(" in _source(name), name


def _bill_payment(i: int, date: str, amount: float) -> dict:
    return {
        "Id": str(i),
        "TxnDate": date,
        "TotalAmt": amount,
        "PayType": "Check",
        "VendorRef": {"name": f"Vendor {i % 7}"},
        "CheckPayment": {"BankAccountRef": {"name": "Operating"}},
    }


def test_bill_payments_total_covers_all_pages(monkeypatch):
    # 1,250 payments => two QBO pages (1000 + 250). The old code would have
    # stopped at max_results with a confident partial total.
    pages = {
        1: [_bill_payment(i, "2026-05-15", 100.0) for i in range(1, 1001)],
        1001: [_bill_payment(i, "2026-04-29", 100.0) for i in range(1001, 1251)],
    }

    async def fake_query(query, **kw):
        m = re.search(r"STARTPOSITION (\d+)", query)
        pos = int(m.group(1)) if m else 1
        return {"QueryResponse": {"BillPayment": pages.get(pos, [])}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_list_bill_payments("2026-04-15", "2026-11-12", 500))
    assert "(1250 payments" in out
    assert "$125,000.00" in out  # full-set total, not 500 × $100
    assert "showing the first 500" in out  # truncated display says so
    # the display really is capped
    assert out.count("| Check via Operating |") == 500


def test_bill_payments_no_note_when_everything_fits(monkeypatch):
    async def fake_query(query, **kw):
        if "STARTPOSITION 1 " in query or query.endswith("MAXRESULTS 1000"):
            return {
                "QueryResponse": {
                    "BillPayment": [_bill_payment(1, "2026-05-01", 250.0)]
                }
            }
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_list_bill_payments("2026-04-15", "2026-11-12", 500))
    assert "(1 payments" in out and "$250.00" in out
    assert "showing the first" not in out


def test_deposits_total_covers_all_while_display_caps(monkeypatch):
    deposits = [
        {
            "Id": str(i),
            "TxnDate": "2026-06-01",
            "TotalAmt": 10.0,
            "DepositToAccountRef": {"name": "Checking"},
            "Line": [],
        }
        for i in range(1, 8)
    ]

    async def fake_query(query, **kw):
        if "STARTPOSITION 1 " in query:
            return {"QueryResponse": {"Deposit": deposits}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_list_deposits("2026-01-01", "2026-12-31", 3))
    assert "$70.00" in out and "(7 deposits" in out  # totals = all 7
    assert "showing the first 3" in out
