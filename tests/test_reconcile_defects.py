"""Seven defects from an owner-run live reconciliation session (v3.28.0).
Three produced confidently-wrong answers; each test reproduces the exact shape.
All fixture data is fictional per the PII policy."""

import asyncio
import json

import accountingqb.server as s

# ---------------------------------------------------------------------------
# P0 — month-end close must notice MISSING transactions (volume baseline)
# ---------------------------------------------------------------------------


def _purchases(n, month, year=2026):
    return [
        {
            "Id": str(i),
            "TxnDate": f"{year:04d}-{month:02d}-10",
            "TotalAmt": 50.0,
            "EntityRef": {"name": f"Vendor {i}"},
            "Line": [],
        }
        for i in range(n)
    ]


def _wire_close(monkeypatch, per_month_counts):
    """per_month_counts: {(year, month): purchase_count}"""

    async def fake_query_all(query, **kw):
        if "FROM Purchase" in query:
            import re

            m = re.search(r"TxnDate >= '(\d{4})-(\d{2})-01'", query)
            y, mo = int(m.group(1)), int(m.group(2))
            return {
                "QueryResponse": {
                    "Purchase": _purchases(per_month_counts.get((y, mo), 0), mo, y)
                }
            }
        if "FROM Deposit" in query or "FROM JournalEntry" in query:
            return {"QueryResponse": {}}
        if "FROM Account" in query:
            return {"QueryResponse": {"Account": []}}
        return {"QueryResponse": {}}

    async def fake_query(query, **kw):
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "qb_query", fake_query)


def test_month_end_close_blocks_on_volume_collapse(monkeypatch):
    # 6 months × 20 purchases, then a month with 4 — the false-READY shape.
    counts = {(2026, m): 20 for m in range(3, 9)}
    counts[(2026, 9)] = 4
    _wire_close(monkeypatch, counts)
    out = asyncio.run(s.qb_month_end_close(2026, 9))
    assert "READY TO CLOSE" not in out  # never a green light on a hollow month
    assert "below" in out and "median" in out
    assert "For Review" in out  # names the likely cause


def test_month_end_close_no_false_blocker_for_new_company(monkeypatch):
    # Brand-new company: 2 months of history — baseline must not penalize.
    counts = {(2026, 8): 5, (2026, 9): 6}
    _wire_close(monkeypatch, counts)
    out = asyncio.run(s.qb_month_end_close(2026, 9))
    assert "below baseline" not in out


def test_month_end_close_normal_volume_still_ready(monkeypatch):
    counts = {(2026, m): 20 for m in range(3, 10)}
    _wire_close(monkeypatch, counts)
    out = asyncio.run(s.qb_month_end_close(2026, 9))
    assert "in line with the 6-month median" in out


# ---------------------------------------------------------------------------
# P0 — expense summary excludes equity / balance-sheet / inactive accounts
# ---------------------------------------------------------------------------


def test_expense_summary_excludes_non_expense_accounts(monkeypatch):
    purchases = [
        {
            "EntityRef": {"name": "Card Issuer"},
            "Line": [
                {
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Amount": amt,
                    "AccountBasedExpenseLineDetail": {"AccountRef": {"name": acct}},
                }
            ],
        }
        for acct, amt in [
            ("Software", 100.0),
            ("Owner investments", 10500.0),  # Equity — the $12K overstatement
            ("Business Card (deleted)", 1500.0),  # inactive Credit Card
        ]
    ]
    accounts = [
        {"Name": "Software", "Classification": "Expense", "Active": True},
        {"Name": "Owner investments", "Classification": "Equity", "Active": True},
        {"Name": "Business Card", "Classification": "Liability", "Active": False},
    ]

    async def fake_query_all(query, **kw):
        if "FROM Purchase" in query:
            return {"QueryResponse": {"Purchase": purchases}}
        if "FROM Account" in query:
            return {"QueryResponse": {"Account": accounts}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_expense_summary("2026-01-01", "2026-12-31"))
    assert "**Grand Total: $100.00**" in out  # only the true expense
    assert "Owner investments" not in out.split("Excluded")[0].split("###")[1]
    assert "Excluded 2 non-expense account(s)" in out
    assert "$10,500.00" in out and "$1,500.00" in out  # auditable footnote
    assert "Equity" in out


# ---------------------------------------------------------------------------
# P1 — loss framing depends on entity type
# ---------------------------------------------------------------------------


def test_loss_framing_by_entity_type():
    sole = s._loss_framing("sole_prop", -24995.89, revenue=100.0)
    assert "THIS YEAR" in sole and "§461(l)" in sole
    assert "§183" in sole  # tiny revenue vs loss → hobby-loss prompt
    sole_rev = s._loss_framing("sole_prop", -5000.0, revenue=100000.0)
    assert "§183" not in sole_rev  # healthy revenue → no hobby-loss nag

    corp = s._loss_framing("corporation", -24995.89)
    assert "NOL" in corp and "forward" in corp

    passthru = s._loss_framing("s_corp", -24995.89)
    assert "basis" in passthru

    unknown = s._loss_framing("", -24995.89)
    assert "qb_allocation_profile" in unknown  # asks, never asserts
    assert "depends on your entity type" in unknown  # a menu, not a conclusion


# ---------------------------------------------------------------------------
# P2 — void guard: unsupported types refuse BEFORE any HTTP call
# ---------------------------------------------------------------------------


def test_void_purchase_refuses_without_http(monkeypatch):
    called = {}

    async def fake_read(*a, **k):
        called["read"] = True
        return {}

    async def fake_request(*a, **k):
        called["request"] = True
        return {}

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_void_transaction("Purchase", "2338"))
    assert called == {}  # no QBO round-trip for a known-unsupported type
    assert "cannot void a Purchase" in out
    assert "qb_delete_transaction" in out


def test_void_invoice_still_proceeds(monkeypatch):
    async def fake_read(entity, entity_id):
        return {"Invoice": {"Id": entity_id, "SyncToken": "0"}}

    posted = {}

    async def fake_request(method, endpoint, json_body=None, **kw):
        posted["endpoint"] = endpoint
        return {"Invoice": {"Id": "1"}}

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_void_transaction("Invoice", "1"))
    assert posted  # supported type goes through


# ---------------------------------------------------------------------------
# P2 — 6480 fault: complete message with the Banking-UI fix
# ---------------------------------------------------------------------------


def test_6480_fault_explains_feed_match():
    class FakeResp:
        def json(self):
            return {
                "Fault": {
                    "Error": [
                        {
                            "code": "6480",
                            "Message": "Matched Transaction Delete Error",
                            "Detail": "You can not delete this transaction because it is matched to a downloaded bank transaction.",
                        }
                    ]
                }
            }

    try:
        s._raise_qb_fault(FakeResp())
        msg = ""
    except RuntimeError as e:
        msg = str(e)
    assert "matched to a downloaded bank" in msg  # full message, not cut off
    assert "Undo" in msg and "Exclude" in msg  # the two-minute fix, named


# ---------------------------------------------------------------------------
# P1 — stripe reconcile: stock-name default + near-miss instead of create
# ---------------------------------------------------------------------------

STRIPE_TXNS = json.dumps([{"type": "charge", "amount": 10000, "fee": 300, "net": 9700}])


def _wire_stripe(monkeypatch, account_names, posted_periods=()):
    accounts = [
        {"Id": str(i), "Name": n, "FullyQualifiedName": n, "Classification": "Expense"}
        for i, n in enumerate(account_names, 1)
    ]

    async def fake_resolve(name, **kw):
        hit = next((a for a in accounts if a["Name"].lower() == name.lower()), None)
        if hit:
            return hit, None
        return None, f"No account matches '{name}'."

    async def fake_query_all(query, **kw):
        if "FROM Account" in query:
            return {"QueryResponse": {"Account": accounts}}
        return {"QueryResponse": {}}

    async def fake_query(query, **kw):
        import re

        m = re.search(r"TxnDate >= '(\d{4})-(\d{2})-01'", query)
        if m and f"{m.group(1)}-{m.group(2)}" in posted_periods:
            return {
                "QueryResponse": {
                    "JournalEntry": [
                        {
                            "Id": "9",
                            "PrivateNote": f"[stripe:{m.group(1)}-{m.group(2)}]",
                            "Line": [],
                        }
                    ]
                }
            }
        return {"QueryResponse": {}}

    async def fake_balance(acct, as_of):
        return 112.04

    creates = []

    async def fake_request(method, endpoint, json_body=None, **kw):
        if endpoint == "account":
            creates.append(json_body)
        return {}

    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_clearing_balance_as_of", fake_balance)
    monkeypatch.setattr(s, "qb_request", fake_request)
    return creates


def test_stripe_default_matches_qbo_stock_account(monkeypatch):
    creates = _wire_stripe(
        monkeypatch,
        [
            "Sales",
            "Merchant account fees",
            "Software & Apps",
            "Refunds to customers",
            "Stripe Clearing",
        ],
    )
    out = asyncio.run(s.qb_stripe_reconcile("2026-10", report_json=STRIPE_TXNS))
    # Stock-name defaults resolve the EXISTING accounts — no forked history.
    assert "Merchant account fees" in out
    assert "will be created" not in out
    assert creates == []


def test_stripe_near_miss_proposed_never_created(monkeypatch):
    creates = _wire_stripe(
        monkeypatch,
        [
            "Sales",
            "Merchant account fees",
            "Software & Apps",
            "Refunds to customers",
            "Stripe Clearing",
        ],
    )
    out = asyncio.run(
        s.qb_stripe_reconcile(
            "2026-10", report_json=STRIPE_TXNS, fee_account="Merchant Fees"
        )
    )
    # Token-set near-miss: every word of "Merchant Fees" appears in the stock
    # account — propose it, create nothing.
    assert "Merchant account fees" in out
    assert "Re-run with the exact name" in out
    assert creates == []


def test_stripe_dry_run_names_unposted_gaps(monkeypatch):
    _wire_stripe(
        monkeypatch,
        [
            "Sales",
            "Merchant account fees",
            "Software & Apps",
            "Refunds to customers",
            "Stripe Clearing",
        ],
        posted_periods=("2026-07",),  # Jul posted; Aug + Sep missing
    )
    out = asyncio.run(s.qb_stripe_reconcile("2026-10", report_json=STRIPE_TXNS))
    assert "Gap" in out
    assert "2026-08" in out and "2026-09" in out
    assert "post periods in order" in out


# ---------------------------------------------------------------------------
# v3.29.1 — owner's regression pass: 1 partial + 2 new
# ---------------------------------------------------------------------------


def test_expense_summary_queries_inactive_accounts_too(monkeypatch):
    # QBO omits inactive accounts by default; the deleted credit-card account
    # had no classification and fell through as expense (regression on #2).
    queries = []

    async def fake_query_all(query, **kw):
        queries.append(query)
        if "FROM Purchase" in query:
            return {
                "QueryResponse": {
                    "Purchase": [
                        {
                            "EntityRef": {"name": "Card Issuer"},
                            "Line": [
                                {
                                    "DetailType": "AccountBasedExpenseLineDetail",
                                    "Amount": 1500.0,
                                    "AccountBasedExpenseLineDetail": {
                                        "AccountRef": {"name": "Old Card (deleted)"}
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        return {
            "QueryResponse": {
                "Account": [
                    {"Name": "Old Card", "Classification": "Liability", "Active": False}
                ]
            }
        }

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_expense_summary("2026-01-01", "2026-12-31"))
    acct_q = next(q for q in queries if "FROM Account" in q)
    assert "Active IN (true, false)" in acct_q  # inactive must be fetched
    assert "**Grand Total: $0.00**" in out  # liability line fully excluded
    assert "Liability" in out and "$1,500.00" in out  # ...and itemized


def test_resolve_account_reaches_inactive_by_exact_name(monkeypatch):
    # New #8: a deleted account's residual activity was unauditable — not
    # resolvable even by exact name.
    queries = []

    async def fake_query(query, **kw):
        queries.append(query)
        if "Name = 'Old Card (deleted)'" in query:
            return {
                "QueryResponse": {
                    "Account": [
                        {"Id": "88", "Name": "Old Card (deleted)", "Active": False}
                    ]
                }
            }
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    acct, err = asyncio.run(s._resolve_account("Old Card (deleted)"))
    assert err is None and acct["Id"] == "88" and acct["Active"] is False
    assert all("Active IN (true, false)" in q for q in queries)


def test_find_duplicates_labels_feed_pairs_and_never_says_void(monkeypatch):
    # New #9: pending+posted Amex pairs look like duplicates but are two real
    # charges — and purchases can't be voided anyway.
    pair = [
        {
            "Id": str(i),
            "TxnDate": "2026-08-01",
            "TotalAmt": 212.50,
            "EntityRef": {"name": "Cloud Vendor"},
            "PrivateNote": "CLOUD SVC XXXX1008 - per Amex statement",
        }
        for i in (2336, 2338)
    ]

    async def fake_query_all(query, **kw):
        if "FROM Purchase" in query:
            return {"QueryResponse": {"Purchase": pair}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_find_duplicates("2026-08-01", "2026-08-31"))
    assert "qb_void_transaction" not in out  # never recommends voiding a Purchase
    assert "two REAL charges" in out and "Undo → Exclude" in out
    assert "qb_delete_transaction" in out
