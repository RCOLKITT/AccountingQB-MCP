"""qb_query_all pages through every row.

A bare `MAXRESULTS N` truncates a large book at N; the fetch-all reads that
feed totals (sales-tax, 1099, reconciliation) must page via STARTPOSITION or
they silently understate. These tests prove the helper walks all pages, merges
the entity arrays, strips the caller's cap, and terminates."""

import re
import asyncio

import accountingqb.server as s


def _fake_book(total_rows, entity="Invoice"):
    """A QBO-shaped query stub: honors STARTPOSITION/MAXRESULTS over a book of
    `total_rows` rows, so pagination is actually exercised (not ignored)."""
    rows = [{"Id": str(i), "TotalAmt": 100.0} for i in range(1, total_rows + 1)]

    async def fake_query(query):
        assert "STARTPOSITION" in query, "qb_query_all must add a cursor"
        pos = int(re.search(r"STARTPOSITION (\d+)", query).group(1))
        size = int(re.search(r"MAXRESULTS (\d+)", query).group(1))
        page = rows[pos - 1: pos - 1 + size]
        return {"QueryResponse": {entity: page} if page else {}}

    return fake_query


def test_pages_through_all_rows(monkeypatch):
    # 2300 rows > one 1000-row page: naive MAXRESULTS 1000 would drop 1300.
    monkeypatch.setattr(s, "qb_query", _fake_book(2300))
    out = asyncio.run(s.qb_query_all("SELECT * FROM Invoice MAXRESULTS 1000"))
    got = out["QueryResponse"]["Invoice"]
    assert len(got) == 2300
    assert {r["Id"] for r in got} == {str(i) for i in range(1, 2301)}  # no dup/gap


def test_short_first_page_terminates(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_book(12))
    out = asyncio.run(s.qb_query_all("SELECT * FROM Invoice MAXRESULTS 500"))
    assert len(out["QueryResponse"]["Invoice"]) == 12


def test_exact_multiple_of_page_size_terminates(monkeypatch):
    # 2000 rows = exactly 2 full pages; the 3rd (empty) page must stop the loop.
    monkeypatch.setattr(s, "qb_query", _fake_book(2000))
    out = asyncio.run(s.qb_query_all("SELECT * FROM Invoice"))
    assert len(out["QueryResponse"]["Invoice"]) == 2000


def test_empty_result(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_book(0))
    out = asyncio.run(s.qb_query_all("SELECT * FROM Invoice MAXRESULTS 1000"))
    assert out["QueryResponse"].get("Invoice", []) == []


def test_caller_startposition_is_stripped(monkeypatch):
    # Even if a caller pre-wrote a cursor, we page from the top over all rows.
    monkeypatch.setattr(s, "qb_query", _fake_book(1500))
    out = asyncio.run(
        s.qb_query_all("SELECT * FROM Invoice STARTPOSITION 5 MAXRESULTS 500"))
    assert len(out["QueryResponse"]["Invoice"]) == 1500


def test_runaway_guard(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_book(100000))
    out = asyncio.run(s.qb_query_all("SELECT * FROM Invoice", max_records=3000))
    # stops at the guard rather than pulling an unbounded book
    assert len(out["QueryResponse"]["Invoice"]) <= 3000 + 1000
