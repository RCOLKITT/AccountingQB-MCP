"""Silent-truncation fixes: fetch-then-filter tools must paginate the FETCH so
counts are accurate (the '17 vs 230' bug), qb_list_accounts must honor
account_type, and search must see bank-feed line Descriptions."""

import re
import asyncio

import accountingqb.server as s


def _paged(rows, entity):
    """A qb_query stub honoring STARTPOSITION/MAXRESULTS over `rows` — so a caller
    that does NOT paginate would only ever see the first page."""

    async def fake_query(q):
        pos = int((re.search(r"STARTPOSITION (\d+)", q) or [0, 1])[1])
        size = int((re.search(r"MAXRESULTS (\d+)", q) or [0, 1000])[1])
        page = rows[pos - 1 : pos - 1 + size] if "STARTPOSITION" in q else rows[:size]
        return {"QueryResponse": {entity: page} if page else {}}

    return fake_query


def test_account_transactions_counts_all_230(monkeypatch):
    # 230 purchases in the range, all hitting the target account. The old code
    # fetched the first 100 and filtered -> a confidently wrong count.
    purchases = [
        {
            "Id": str(i),
            "TxnDate": "2026-06-01",
            "TotalAmt": 10.0,
            "AccountRef": {"value": "77"},
        }
        for i in range(1, 231)
    ]

    async def fake_query(q):  # account lookup (unpaginated) + others empty
        if "FROM Account" in q:
            return {
                "QueryResponse": {
                    "Account": [
                        {
                            "Id": "77",
                            "Name": "Delta Platinum Business Card",
                            "AccountType": "Credit Card",
                            "Active": True,
                            "CurrentBalance": 0,
                        }
                    ]
                }
            }
        return {"QueryResponse": {}}

    async def fake_query_all(q, **kw):
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(
        s.qb_account_transactions(
            "Delta Platinum Business Card", "2026-03-05", "2026-08-01", max_results=100
        )
    )
    assert "Transactions Found:** 230" in out  # accurate count
    assert "showing the first 100" in out  # honest display cap


def test_list_accounts_paginates_and_filters(monkeypatch):
    # 110 accounts total; a Bank filter must push into the query and NOT be dropped.
    accts = [
        {"Id": str(i), "Name": f"Acct{i}", "AccountType": "Expense", "Active": True}
        for i in range(1, 109)
    ] + [
        {"Id": "200", "Name": "Checking", "AccountType": "Bank", "Active": True},
        {
            "Id": "201",
            "Name": "Delta Card",
            "AccountType": "Credit Card",
            "Active": True,
        },
    ]

    async def fake_query_all(q, **kw):
        rows = accts
        m = re.search(r"AccountType = '([^']+)'", q)
        if m:
            rows = [a for a in rows if a["AccountType"] == m.group(1)]
        return {"QueryResponse": {"Account": rows}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "_demo_active", lambda: False)

    full = asyncio.run(s.qb_list_accounts())
    assert "110 accounts" in full  # not truncated at 100
    bank = asyncio.run(s.qb_list_accounts(account_type="Bank"))
    assert "Checking" in bank and "Delta Card" not in bank  # filter honored


def test_search_finds_bank_feed_line_description(monkeypatch):
    # The descriptor is on the line Description, not PrivateNote.
    purchases = [
        {
            "Id": "1",
            "TxnDate": "2026-05-01",
            "TotalAmt": 600.0,
            "PrivateNote": "",
            "EntityRef": {"name": "Amex"},
            "Line": [{"Description": "MOBILE PAYMENT THANK YOU"}],
        }
    ]

    async def fake_query_all(q, **kw):
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)

    out = asyncio.run(
        s.qb_search_transactions("2026-01-01", "2026-12-31", "MOBILE PAYMENT")
    )
    assert "1 transactions" in out  # found via line Description
    assert "MOBILE PAYMENT" in out


def test_find_duplicates_sees_full_set(monkeypatch):
    # Two identical same-day charges at opposite ends of a set that would span
    # fetch pages — must be caught under the default same-day window.
    purchases = (
        [
            {
                "Id": "1",
                "TxnDate": "2026-01-01",
                "TotalAmt": 498.0,
                "EntityRef": {"name": "Tailor Brands"},
            }
        ]
        + [
            {
                "Id": str(i),
                "TxnDate": "2026-01-01",
                "TotalAmt": float(i),
                "EntityRef": {"name": f"V{i}"},
            }
            for i in range(2, 260)
        ]
        + [
            {
                "Id": "999",
                "TxnDate": "2026-01-01",
                "TotalAmt": 498.0,
                "EntityRef": {"name": "Tailor Brands"},
            }
        ]
    )

    async def fake_query_all(q, **kw):
        return {"QueryResponse": {"Purchase": purchases}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_find_duplicates("2026-01-01", "2026-12-31"))
    assert "Tailor Brands" in out and "498" in out  # dupe across pages caught
