"""qb_set_transaction_class — tag a transaction with a class BY NAME.

Locks the fix for the reported gap: qb_list_classes hid the internal Class ID
and no write tool could set a class without it. This resolves the class name →
ID at call time (Constitution: per-company IDs are never required from the
caller) and applies ClassRef to every class-capable line.
"""

import asyncio

import accountingqb.server as s


def _patch(monkeypatch, classes, deposit, captured):
    async def fake_query(sql, **kw):
        if "FROM Class" in sql:
            return {"QueryResponse": {"Class": classes}}
        return {"QueryResponse": {}}

    async def fake_read(entity_lower, entity_id):
        # server calls qb_read(entity_type.lower(), id) → {EntityType: {...}}
        return {"Deposit": deposit} if deposit else {}

    async def fake_request(method, endpoint, json_body=None, **kw):
        captured["body"] = json_body
        return {"Deposit": {"Id": "42", "SyncToken": "1"}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)


_INTEREST = {
    "Id": "5",
    "Name": "Interest Income",
    "FullyQualifiedName": "Interest Income",
    "Active": True,
}


def _deposit_two_lines():
    return {
        "Id": "42",
        "SyncToken": "0",
        "Line": [
            {
                "Amount": 100.0,
                "DetailType": "DepositLineDetail",
                "DepositLineDetail": {
                    "AccountRef": {"value": "90", "name": "Interest"}
                },
            },
            {
                "Amount": 50.0,
                "DetailType": "DepositLineDetail",
                "DepositLineDetail": {
                    "AccountRef": {"value": "90", "name": "Interest"}
                },
            },
        ],
    }


def test_sets_class_on_all_deposit_lines(monkeypatch):
    captured = {}
    _patch(monkeypatch, [_INTEREST], _deposit_two_lines(), captured)
    out = asyncio.run(s.qb_set_transaction_class("Deposit", "42", "Interest Income"))
    assert "Set class on Deposit #42" in out
    assert "Interest Income" in out and "Lines tagged: 2" in out
    # Both lines carry the resolved ClassRef (name resolved to ID 5).
    posted = captured["body"]["Line"]
    assert all(
        l["DepositLineDetail"]["ClassRef"] == {"value": "5", "name": "Interest Income"}
        for l in posted
    )


def test_class_not_found_is_actionable(monkeypatch):
    captured = {}
    _patch(monkeypatch, [], _deposit_two_lines(), captured)
    out = asyncio.run(s.qb_set_transaction_class("Deposit", "42", "Nope"))
    assert "not found" in out and "qb_list_classes" in out
    assert "body" not in captured  # never wrote


def test_ambiguous_class_refuses(monkeypatch):
    captured = {}
    two = [
        {"Id": "5", "Name": "Outreach East", "FullyQualifiedName": "Outreach East"},
        {"Id": "6", "Name": "Outreach West", "FullyQualifiedName": "Outreach West"},
    ]
    _patch(monkeypatch, two, _deposit_two_lines(), captured)
    out = asyncio.run(s.qb_set_transaction_class("Deposit", "42", "Outreach"))
    assert "Multiple classes match" in out
    assert "body" not in captured  # refuses rather than guess


def test_exact_match_wins_over_substring(monkeypatch):
    # 'Travel' is an exact name even though 'Travel Meals' also LIKE-matches.
    captured = {}
    classes = [
        {"Id": "5", "Name": "Travel", "FullyQualifiedName": "Travel"},
        {"Id": "6", "Name": "Travel Meals", "FullyQualifiedName": "Travel Meals"},
    ]
    _patch(monkeypatch, classes, _deposit_two_lines(), captured)
    out = asyncio.run(s.qb_set_transaction_class("Deposit", "42", "Travel"))
    assert "Lines tagged: 2" in out
    assert captured["body"]["Line"][0]["DepositLineDetail"]["ClassRef"]["value"] == "5"


def test_no_class_capable_lines(monkeypatch):
    captured = {}
    deposit = {"Id": "42", "SyncToken": "0", "Line": [{"DetailType": "TaxLineDetail"}]}
    _patch(monkeypatch, [_INTEREST], deposit, captured)
    out = asyncio.run(s.qb_set_transaction_class("Deposit", "42", "Interest Income"))
    assert "no class-capable lines" in out
    assert "body" not in captured
