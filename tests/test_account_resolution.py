"""Safe account resolution + hardened journal entries.

The blocker this guards against: `_resolve_account("Services")` used to match
"Legal & accounting services" via a LIKE and silently post revenue into an
expense account. The resolver must prefer an exact match and REFUSE to guess
when a partial name is ambiguous."""

import re
import asyncio

import accountingqb.server as s

ACCOUNTS = [
    {
        "Id": "2",
        "Name": "Services",
        "FullyQualifiedName": "Services",
        "AccountType": "Income",
    },
    {
        "Id": "44",
        "Name": "Legal & accounting services",
        "FullyQualifiedName": "Legal & accounting services",
        "AccountType": "Expense",
    },
    {
        "Id": "10",
        "Name": "Hotels",
        "FullyQualifiedName": "Travel:Hotels",
        "AccountType": "Expense",
    },
    {
        "Id": "20",
        "Name": "Office Supplies",
        "FullyQualifiedName": "Office Supplies",
        "AccountType": "Expense",
    },
    {
        "Id": "21",
        "Name": "Office Rent",
        "FullyQualifiedName": "Office Rent",
        "AccountType": "Expense",
    },
]


def _fake_qb_query(accounts):
    async def fake(q):
        mt = re.search(r"AccountType = '([^']+)'", q)
        atype = mt.group(1) if mt else None
        keep = lambda a: atype is None or a.get("AccountType") == atype
        if "Name LIKE" in q:
            val = re.search(r"Name LIKE '%(.*?)%'", q).group(1)
            res = [a for a in accounts if val.lower() in a["Name"].lower() and keep(a)]
        elif "FullyQualifiedName =" in q:
            val = re.search(r"FullyQualifiedName = '(.*?)'", q).group(1)
            res = [
                a for a in accounts if a.get("FullyQualifiedName") == val and keep(a)
            ]
        elif "Name =" in q:
            val = re.search(r"Name = '(.*?)'", q).group(1)
            res = [a for a in accounts if a["Name"] == val and keep(a)]
        else:
            res = []
        return {"QueryResponse": {"Account": res}}

    return fake


# ---- resolver ---------------------------------------------------------------


def test_exact_name_beats_like(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    acct, err = asyncio.run(s._resolve_account("Services"))
    assert err is None
    assert acct["Id"] == "2"  # the real "Services", NOT "Legal & accounting services"


def test_ambiguous_like_refuses_to_guess(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    acct, err = asyncio.run(s._resolve_account("Office"))
    assert acct is None
    assert "Multiple accounts match" in err
    assert "Office Supplies" in err and "Office Rent" in err


def test_fully_qualified_name(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    acct, err = asyncio.run(s._resolve_account("Travel:Hotels"))
    assert err is None and acct["Id"] == "10"


def test_not_found(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    acct, err = asyncio.run(s._resolve_account("Nonexistent"))
    assert acct is None and "not found" in err


def test_account_type_filter_narrows(monkeypatch):
    # "Services" as an Expense category resolves to the one Expense match,
    # never the Income "Services" account.
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    acct, err = asyncio.run(s._resolve_account("Services", account_type="Expense"))
    assert err is None and acct["Id"] == "44"


# ---- journal entry hardening -----------------------------------------------


def test_je_rejects_unknown_line_key(monkeypatch):
    # 'posting_type' (instead of 'type') used to make every line a silent debit.
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-01-01",
            '[{"account_name":"Services","amount":100,"posting_type":"Debit"}]',
        )
    )
    assert "unrecognized field" in out and "posting_type" in out


def test_je_rejects_bad_type(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-01-01", '[{"account_name":"Services","amount":100,"type":"Dr"}]'
        )
    )
    assert "Debit" in out and "Credit" in out


def test_je_reports_real_total_not_zero(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))

    async def fake_request(method, endpoint, params=None, json_body=None):
        return {"JournalEntry": {"Id": "999"}}  # QBO omits TotalAmt on JEs

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-01-01",
            '[{"account_name":"Services","amount":100,"type":"Debit"},'
            '{"account_name":"Office Rent","amount":100,"type":"Credit"}]',
        )
    )
    assert "Total: $100.00" in out and "Total: $0.00" not in out


def test_je_accepts_account_id(monkeypatch):
    monkeypatch.setattr(s, "qb_query", _fake_qb_query(ACCOUNTS))

    async def fake_read(entity, eid):
        return {"Account": next((a for a in ACCOUNTS if a["Id"] == eid), None)}

    monkeypatch.setattr(s, "qb_read", fake_read)

    async def fake_request(*a, **k):
        return {"JournalEntry": {"Id": "1"}}

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_create_journal_entry(
            "2026-01-01",
            '[{"account_id":"2","amount":50,"type":"Debit"},'
            '{"account_id":"44","amount":50,"type":"Credit"}]',
        )
    )
    assert "Journal entry created" in out


# ---- create_account length validation --------------------------------------


def test_create_account_rejects_long_description():
    out = asyncio.run(
        s.qb_create_account("Test Acct", "Expense", description="x" * 114)
    )
    assert "114" in out and "100" in out
