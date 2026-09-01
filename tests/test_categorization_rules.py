"""Categorization-at-scale (reach roadmap Phase 2): saved per-company rules +
a preview-first bulk apply. The invariants: rules persist in the company-wide
(tax_year=0) taxpayer store; preview NEVER writes; longest pattern wins;
unmatched transactions are surfaced, never guessed."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcpb" / "src"))

import accountingqb.server as s  # noqa: E402


def _store(monkeypatch, initial=None):
    store = {"profile": dict(initial or {})}

    async def fake_get(year):
        assert int(year) == 0  # rules are company-wide → the year-0 bucket
        return dict(store["profile"])

    async def fake_save(year, profile):
        assert int(year) == 0
        store["profile"] = dict(profile)
        return True

    async def fake_chart():
        return {"Travel": "Travel", "Software & Subscriptions": "OfficeExpenses"}

    monkeypatch.setattr(s, "_get_allocation_profile", fake_get)
    monkeypatch.setattr(s, "_save_allocation_profile", fake_save)
    monkeypatch.setattr(s, "_account_subtype_map", fake_chart)
    return store


def _uncat_world(monkeypatch):
    """One Uncategorized account with three purchases: Uber ride, AWS bill,
    and a mystery vendor no rule matches."""
    txns = [
        {
            "Id": "1",
            "TxnDate": "2026-08-01",
            "TotalAmt": 42.0,
            "EntityRef": {"name": "Uber Trip 8341"},
            "Line": [],
        },
        {
            "Id": "2",
            "TxnDate": "2026-08-02",
            "TotalAmt": 350.0,
            "EntityRef": {"name": "Amazon Web Services"},
            "Line": [],
        },
        {
            "Id": "3",
            "TxnDate": "2026-08-03",
            "TotalAmt": 99.0,
            "EntityRef": {"name": "Mystery Vendor LLC"},
            "Line": [],
        },
    ]

    async def fake_query(q, **kw):
        if "ncategorized" in q:
            return {
                "QueryResponse": {
                    "Account": [{"Id": "50", "Name": "Uncategorized Expense"}]
                }
            }
        return {"QueryResponse": {}}

    async def fake_query_all(q, **kw):
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": txns}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    return txns


def test_rules_roundtrip(monkeypatch):
    store = _store(monkeypatch)
    out = asyncio.run(
        s.qb_categorization_rules(
            rules_json='{"Uber": "Travel", "amazon web services": "Software & Subscriptions"}'
        )
    )
    assert "2 rule(s) now active" in out
    # normalized lowercase patterns persisted in the year-0 bucket
    rules = store["profile"]["categorization_rules"]
    assert rules["uber"] == "Travel"
    assert rules["amazon web services"] == "Software & Subscriptions"
    # view
    view = asyncio.run(s.qb_categorization_rules())
    assert '"uber" → Travel' in view
    # remove
    out2 = asyncio.run(s.qb_categorization_rules(remove_json='["uber"]'))
    assert "1 rule(s) now active" in out2
    assert "uber" not in store["profile"]["categorization_rules"]


def test_unknown_account_warns(monkeypatch):
    _store(monkeypatch)
    out = asyncio.run(
        s.qb_categorization_rules(rules_json='{"uber": "Travle"}')  # typo'd account
    )
    assert "not an account in this chart" in out


def test_preview_never_writes(monkeypatch):
    _store(
        monkeypatch,
        {
            "categorization_rules": {
                "uber": "Travel",
                "amazon web services": "Software & Subscriptions",
            }
        },
    )
    _uncat_world(monkeypatch)
    calls = []

    async def spy_reclassify(*a, **kw):
        calls.append(a)
        return "✅"

    monkeypatch.setattr(s, "qb_reclassify_transaction", spy_reclassify)
    out = asyncio.run(s.qb_apply_categorization_rules())
    assert "Nothing has been changed" in out
    assert calls == []  # preview NEVER writes
    assert "Uber Trip 8341" in out and "→ **Travel**" in out
    assert "Amazon Web Services" in out and "Software & Subscriptions" in out
    assert "No rule matched (1)" in out and "Mystery Vendor LLC" in out


def test_apply_reclassifies_matches_only(monkeypatch):
    _store(
        monkeypatch,
        {
            "categorization_rules": {
                "amazon": "Travel",  # shorter — must LOSE to the longer pattern
                "amazon web services": "Software & Subscriptions",
                "uber": "Travel",
            }
        },
    )
    _uncat_world(monkeypatch)
    calls = []

    async def spy_reclassify(entity_type, entity_id, account, memo=""):
        calls.append((entity_type, entity_id, account))
        return "✅ reclassified"

    monkeypatch.setattr(s, "qb_reclassify_transaction", spy_reclassify)
    out = asyncio.run(s.qb_apply_categorization_rules(apply=True))
    assert "Reclassified: 2" in out
    assert ("Purchase", "1", "Travel") in calls
    # longest pattern wins: AWS → Software, not the shorter "amazon" → Travel
    assert ("Purchase", "2", "Software & Subscriptions") in calls
    assert all(c[1] != "3" for c in calls)  # unmatched mystery vendor untouched
    assert "Still unmatched (need rules): 1" in out


def test_no_rules_guides_instead_of_guessing(monkeypatch):
    _store(monkeypatch)
    _uncat_world(monkeypatch)
    out = asyncio.run(s.qb_apply_categorization_rules(apply=True))
    assert "No categorization rules saved yet" in out
