"""qb_stripe_reconcile — the processor-clearing model, the processing-vs-platform
fee split (the differentiator), the tie-out gate, idempotency, and dry-run safety.
Golden fixture = the real NutriFitAI numbers from the Cowork review."""

import json
import asyncio

import accountingqb.server as s

# 5 charges @ $39 ($2.02 fee each), one $39 refund, $33.86 of platform fees
# (Sigma/Billing/Radar). Nets to $112.04 retained — the review's exact figures.
REPORT = json.dumps([
    {"type": "charge", "amount": 3900, "fee": 202},
    {"type": "charge", "amount": 3900, "fee": 202},
    {"type": "charge", "amount": 3900, "fee": 202},
    {"type": "charge", "amount": 3900, "fee": 202},
    {"type": "charge", "amount": 3900, "fee": 202},
    {"type": "refund", "amount": -3900, "fee": 0},
    {"type": "stripe_fee", "amount": -3386, "fee": 0, "description": "Sigma"},
])


def _no_accounts(monkeypatch):
    async def fake_query(q):
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)


def test_classify_matches_review_numbers(monkeypatch):
    _no_accounts(monkeypatch)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT,
                                            expected_ending_balance=112.04))
    assert "$195.00" in out            # gross
    assert "$39.00" in out             # refunds
    assert "$10.10" in out             # processing fees
    assert "$33.86" in out             # platform fees
    assert "$112.04" in out            # clearing / net retained
    assert "ties" in out               # tie-out passes (prior 0 + 112.04)
    assert "Dry run" in out            # default is dry-run


def test_platform_fee_ratio_called_out(monkeypatch):
    _no_accounts(monkeypatch)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT))
    # 33.86 / 10.10 = 3.4x — the "everyone misses this" differentiator
    assert "3.4×" in out and "most reconciliations miss" in out


def test_tie_out_off_blocks(monkeypatch):
    _no_accounts(monkeypatch)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT, dry_run=False,
                                            expected_ending_balance=100.00))
    assert "OFF" in out and "Unreconciled difference" in out
    assert "Not posting" in out


def test_dry_run_posts_nothing(monkeypatch):
    _no_accounts(monkeypatch)

    async def boom(*a, **k):
        raise AssertionError("dry_run must not POST")
    monkeypatch.setattr(s, "qb_request", boom)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT,
                                            expected_ending_balance=112.04))
    assert "Proposed journal entry" in out


def test_proposed_entry_balances(monkeypatch):
    _no_accounts(monkeypatch)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT))
    # the JE table: debits (refunds+fees+clearing) must equal the sales credit
    assert "| Sales | | $195.00 |" in out
    assert "| Stripe Clearing | $112.04 | |" in out


def _post_setup(monkeypatch, dup=False):
    accts = {
        "Stripe Clearing": {"Id": "155", "Name": "Stripe Clearing", "CurrentBalance": 0},
        "Sales": {"Id": "5", "Name": "Sales"},
        "Merchant Fees": {"Id": "60", "Name": "Merchant Fees"},
        "Software & Apps": {"Id": "8", "Name": "Software & Apps"},
        "Refunds": {"Id": "70", "Name": "Refunds"},
    }

    async def fake_resolve(name, **kw):
        a = accts.get(name)
        return (a, None) if a else (None, f"'{name}' not found")
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)

    async def fake_query(q):
        # A previously-posted reconciliation JE that touches Stripe Clearing (155)
        # and carries our period marker — the idempotency scan must catch it.
        if "JournalEntry" in q and dup:
            return {"QueryResponse": {"JournalEntry": [{
                "Id": "999",
                "PrivateNote": "Stripe reconciliation 2026-07 [stripe:2026-07]",
                "Line": [{"JournalEntryLineDetail": {"AccountRef": {"value": "155"}}}],
            }]}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)

    posts = []

    async def fake_request(method, endpoint, params=None, json_body=None):
        posts.append((endpoint, json_body))
        return {"JournalEntry": {"Id": "2201"}, "Account": {"Id": "X", "Name": "X"}}
    monkeypatch.setattr(s, "qb_request", fake_request)
    return posts


def test_posts_balanced_entry(monkeypatch):
    posts = _post_setup(monkeypatch)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT, dry_run=False,
                                            expected_ending_balance=112.04))
    assert "Posted activity journal entry #2201" in out and "[stripe:2026-07]" in out
    je = [b for e, b in posts if e == "journalentry"][0]
    d = sum(l["Amount"] for l in je["Line"]
            if l["JournalEntryLineDetail"]["PostingType"] == "Debit")
    c = sum(l["Amount"] for l in je["Line"]
            if l["JournalEntryLineDetail"]["PostingType"] == "Credit")
    assert abs(d - c) < 0.01 and abs(d - 195.00) < 0.01
    assert je["PrivateNote"].endswith("[stripe:2026-07]")


def test_idempotent_refuses_duplicate(monkeypatch):
    posts = _post_setup(monkeypatch, dup=True)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT, dry_run=False,
                                            expected_ending_balance=112.04))
    assert "Already reconciled" in out
    assert not any(e == "journalentry" for e, _ in posts)  # nothing posted


def test_unmapped_blocks_posting(monkeypatch):
    _post_setup(monkeypatch)
    weird = json.loads(REPORT) + [{"type": "dispute", "amount": -1500, "fee": 0}]
    out = asyncio.run(s.qb_stripe_reconcile(
        "2026-07", json.dumps(weird), dry_run=False, expected_ending_balance=100.0))
    assert "unmapped" in out.lower() and "Not posting" in out


def test_stripe_fee_uses_net_incl_tax(monkeypatch):
    """On a stripe_fee, `amount` is the fee net of tax and `fee` is the tax —
    the platform total must use `net` (amount+tax), not bare `amount`. Regression
    for the review's $10.62-vs-$11.30 understatement."""
    _no_accounts(monkeypatch)
    report = json.dumps([
        {"type": "charge", "amount": 5000, "fee": 175, "net": 4825},
        # fee -$10.62 net of tax, +$0.68 sales tax => true fee $11.30 (net -11.30)
        {"type": "stripe_fee", "amount": -1062, "fee": 68, "net": -1130,
         "description": "Billing"},
    ])
    out = asyncio.run(s.qb_stripe_reconcile("2026-07", report))
    assert "$11.30" in out and "$10.62" not in out
    # Activity net and tie-out net change must agree (no 0.68 drift):
    b, _ = s._classify_stripe(json.loads(report), 100.0)
    assert abs(b["activity_net"] - b["net_change"]) < 0.01     # no payouts here


def test_detects_manual_entry_in_period(monkeypatch):
    """An untagged JE touching the clearing account in the period must block a
    post (avoids double-booking a manually-entered reconciliation)."""
    accts = {"Stripe Clearing": {"Id": "155", "Name": "Stripe Clearing"},
             "Sales": {"Id": "5", "Name": "Sales"},
             "Merchant Fees": {"Id": "60", "Name": "Merchant Fees"},
             "Software & Apps": {"Id": "8", "Name": "Software & Apps"},
             "Refunds": {"Id": "70", "Name": "Refunds"}}

    async def fake_resolve(name, **kw):
        a = accts.get(name)
        return (a, None) if a else (None, f"'{name}' not found")
    monkeypatch.setattr(s, "_resolve_account", fake_resolve)

    async def fake_query(q):
        if "JournalEntry" in q:
            return {"QueryResponse": {"JournalEntry": [{
                "Id": "888", "PrivateNote": "manual clearing cleanup",
                "Line": [{"JournalEntryLineDetail": {"AccountRef": {"value": "155"}}}],
            }]}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)

    async def fake_request(method, endpoint, params=None, json_body=None):
        return {"JournalEntry": {"Id": "2201"}}
    monkeypatch.setattr(s, "qb_request", fake_request)

    out = asyncio.run(s.qb_stripe_reconcile("2026-07", REPORT, dry_run=False,
                                            expected_ending_balance=112.04))
    assert "posted manually" in out and "Not posting" in out
    assert "#888" in out


# ---- live Stripe fetch (v2) ------------------------------------------------

def test_no_report_no_key_is_helpful(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    out = asyncio.run(s.qb_stripe_reconcile("2026-07"))
    assert "STRIPE_API_KEY" in out and "export" in out


def test_live_fetch_reconciles(monkeypatch):
    _no_accounts(monkeypatch)
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_x")

    async def fake_fetch(period, api_key):
        assert api_key == "sk_test_x"
        return json.loads(REPORT), 112.04   # (txns, current balance)
    monkeypatch.setattr(s, "_fetch_stripe_activity", fake_fetch)
    # current month -> live balance auto-used as the tie-out target
    monkeypatch.setattr(s, "_is_current_month", lambda p: True)

    out = asyncio.run(s.qb_stripe_reconcile("2026-07"))
    assert "source: live Stripe API" in out
    assert "$112.04" in out and "ties" in out


def test_live_historical_month_warns_no_autotie(monkeypatch):
    _no_accounts(monkeypatch)
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_x")

    async def fake_fetch(period, api_key):
        return json.loads(REPORT), 500.00
    monkeypatch.setattr(s, "_fetch_stripe_activity", fake_fetch)
    monkeypatch.setattr(s, "_is_current_month", lambda p: False)

    out = asyncio.run(s.qb_stripe_reconcile("2026-04"))
    # past month: current balance is NOT the tie-out target
    assert "not the period-end balance" in out
    assert "Pass expected_ending_balance" in out
