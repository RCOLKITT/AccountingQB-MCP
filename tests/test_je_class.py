"""Per-line class on journal-entry writes (requested by a CPA who posts class-only
reclassification entries: same GL account debited and credited in two different
classes, or a mix of classed + unclassed lines). QBO carries ClassRef on each
JournalEntryLineDetail; these lock that the write tools place it per line and that
qb_set_transaction_class can target a single line."""

import asyncio
import json

import accountingqb.server as s

CLASS_A = "Ahous Adventures"
CLASS_B = "Wahous Wilderness Lodge"


def _acct(acct_id, name):
    return {"Id": acct_id, "Name": name, "AccountType": "Expense"}


async def _resolve_class_stub(class_name="", class_id=""):
    if not class_name and not class_id:
        return None, None
    ids = {CLASS_A: "9", CLASS_B: "8"}
    if class_name not in ids and not class_id:
        return None, f"Class '{class_name}' not found. Run qb_list_classes."
    return {"value": ids.get(class_name, class_id or "1"), "name": class_name}, None


# --- _resolve_class ---------------------------------------------------------


def test_resolve_class_empty_is_no_class():
    ref, err = asyncio.run(s._resolve_class("", ""))
    assert ref is None and err is None


def test_resolve_class_exact_over_prefix(monkeypatch):
    async def fake_query(q):
        return {
            "QueryResponse": {
                "Class": [
                    {"Id": "1", "Name": "Outreach", "FullyQualifiedName": "Outreach"},
                    {
                        "Id": "2",
                        "Name": "Outreach East",
                        "FullyQualifiedName": "Outreach East",
                    },
                ]
            }
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    ref, err = asyncio.run(s._resolve_class("Outreach"))
    assert err is None and ref == {"value": "1", "name": "Outreach"}


def test_resolve_class_ambiguous_errors(monkeypatch):
    async def fake_query(q):
        return {
            "QueryResponse": {
                "Class": [
                    {"Id": "1", "Name": "Lodge A", "FullyQualifiedName": "Lodge A"},
                    {"Id": "2", "Name": "Lodge B", "FullyQualifiedName": "Lodge B"},
                ]
            }
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    ref, err = asyncio.run(s._resolve_class("Lodge"))
    assert ref is None and "Multiple classes match" in err


def test_resolve_class_not_found(monkeypatch):
    async def fake_query(q):
        return {"QueryResponse": {"Class": []}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    ref, err = asyncio.run(s._resolve_class("Nope"))
    assert ref is None and "not found" in err


# --- qb_create_journal_entry: per-line class --------------------------------


def _wire_create(monkeypatch):
    captured = {}

    async def fake_resolve_account(name, **kw):
        return _acct("1650", name or "WIP"), None

    async def fake_request(method, endpoint, json_body=None, **kw):
        captured["body"] = json_body
        return {"JournalEntry": {"Id": "555", "TotalAmt": 100.0}}

    monkeypatch.setattr(s, "_resolve_account", fake_resolve_account)
    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_request", fake_request)
    return captured


def test_create_je_class_only_reclass(monkeypatch):
    # The exact CPA case: same account, debit in one class, credit in another.
    captured = _wire_create(monkeypatch)
    lines = json.dumps(
        [
            {
                "account_name": "Work in progress",
                "amount": 100,
                "type": "Debit",
                "class_name": CLASS_A,
            },
            {
                "account_name": "Work in progress",
                "amount": 100,
                "type": "Credit",
                "class_name": CLASS_B,
            },
        ]
    )
    out = asyncio.run(s.qb_create_journal_entry("2026-07-15", lines, "reclass"))
    body = captured["body"]
    assert body["Line"][0]["JournalEntryLineDetail"]["ClassRef"] == {
        "value": "9",
        "name": CLASS_A,
    }
    assert body["Line"][1]["JournalEntryLineDetail"]["ClassRef"] == {
        "value": "8",
        "name": CLASS_B,
    }
    assert CLASS_A in out and CLASS_B in out


def test_create_je_mix_classed_and_unclassed(monkeypatch):
    # One line classed, the other left Not Specified (no class_name).
    captured = _wire_create(monkeypatch)
    lines = json.dumps(
        [
            {
                "account_name": "WIP",
                "amount": 50,
                "type": "Debit",
                "class_name": CLASS_A,
            },
            {"account_name": "WIP", "amount": 50, "type": "Credit"},
        ]
    )
    asyncio.run(s.qb_create_journal_entry("2026-07-15", lines))
    d0 = captured["body"]["Line"][0]["JournalEntryLineDetail"]
    d1 = captured["body"]["Line"][1]["JournalEntryLineDetail"]
    assert d0["ClassRef"]["name"] == CLASS_A
    assert "ClassRef" not in d1  # unclassed → Not Specified


def test_create_je_unknown_class_errors(monkeypatch):
    _wire_create(monkeypatch)
    lines = json.dumps(
        [
            {
                "account_name": "WIP",
                "amount": 10,
                "type": "Debit",
                "class_name": "Ghost",
            },
            {"account_name": "WIP", "amount": 10, "type": "Credit"},
        ]
    )
    out = asyncio.run(s.qb_create_journal_entry("2026-07-15", lines))
    assert "not found" in out and "line 1" in out


def test_create_je_still_rejects_unknown_field(monkeypatch):
    _wire_create(monkeypatch)
    lines = json.dumps(
        [{"account_name": "WIP", "amount": 10, "type": "Debit", "klass": "x"}]
    )
    out = asyncio.run(s.qb_create_journal_entry("2026-07-15", lines))
    assert "unrecognized field(s): klass" in out


# --- qb_batch_create_journal_entries: per-line class ------------------------


def test_batch_je_per_line_class(monkeypatch):
    captured = {"bodies": []}

    async def fake_query(q):
        if "FROM Account" in q:
            return {"QueryResponse": {"Account": [_acct("1650", "WIP")]}}
        return {"QueryResponse": {}}

    async def fake_request(method, endpoint, json_body=None, **kw):
        captured["bodies"].append(json_body)
        return {"JournalEntry": {"Id": "900", "TotalAmt": 100.0}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_request", fake_request)

    entries = json.dumps(
        [
            {
                "date": "2026-07-15",
                "memo": "reclass",
                "lines": [
                    {
                        "account_name": "WIP",
                        "amount": 100,
                        "type": "Debit",
                        "class_name": CLASS_A,
                    },
                    {
                        "account_name": "WIP",
                        "amount": 100,
                        "type": "Credit",
                        "class_name": CLASS_B,
                    },
                ],
            }
        ]
    )
    out = asyncio.run(s.qb_batch_create_journal_entries(entries))
    body = captured["bodies"][0]
    assert body["Line"][0]["JournalEntryLineDetail"]["ClassRef"]["name"] == CLASS_A
    assert body["Line"][1]["JournalEntryLineDetail"]["ClassRef"]["name"] == CLASS_B
    assert "Created: 1" in out


# --- qb_set_transaction_class: single-line targeting ------------------------


def _two_line_je():
    return {
        "JournalEntry": {
            "Id": "70",
            "SyncToken": "3",
            "Line": [
                {
                    "DetailType": "JournalEntryLineDetail",
                    "Amount": 100.0,
                    "JournalEntryLineDetail": {"PostingType": "Debit"},
                },
                {
                    "DetailType": "JournalEntryLineDetail",
                    "Amount": 100.0,
                    "JournalEntryLineDetail": {"PostingType": "Credit"},
                },
            ],
        }
    }


def test_set_class_single_line(monkeypatch):
    captured = {}

    async def fake_read(entity, entity_id):
        return _two_line_je()

    async def fake_request(method, endpoint, json_body=None, **kw):
        captured["body"] = json_body
        return {"JournalEntry": {"SyncToken": "4"}}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)

    out = asyncio.run(
        s.qb_set_transaction_class("JournalEntry", "70", CLASS_A, line_number=1)
    )
    lines = captured["body"]["Line"]
    assert lines[0]["JournalEntryLineDetail"]["ClassRef"]["name"] == CLASS_A
    assert "ClassRef" not in lines[1]["JournalEntryLineDetail"]  # line 2 untouched
    assert "line 1" in out


def test_set_class_line_out_of_range(monkeypatch):
    async def fake_read(entity, entity_id):
        return _two_line_je()

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_read", fake_read)
    out = asyncio.run(
        s.qb_set_transaction_class("JournalEntry", "70", CLASS_A, line_number=5)
    )
    assert "out of range" in out


def test_set_class_all_lines_default(monkeypatch):
    captured = {}

    async def fake_read(entity, entity_id):
        return _two_line_je()

    async def fake_request(method, endpoint, json_body=None, **kw):
        captured["body"] = json_body
        return {"JournalEntry": {"SyncToken": "4"}}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)

    out = asyncio.run(s.qb_set_transaction_class("JournalEntry", "70", CLASS_A))
    lines = captured["body"]["Line"]
    assert lines[0]["JournalEntryLineDetail"]["ClassRef"]["name"] == CLASS_A
    assert lines[1]["JournalEntryLineDetail"]["ClassRef"]["name"] == CLASS_A
    assert "2 lines" in out
