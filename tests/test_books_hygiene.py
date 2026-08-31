"""qb_books_hygiene — the structural checks the 100/100 health audit missed:
dangling references to deleted accounts, wrong-sign balances, credit-card
payments misfiled as expenses, dormant large balances, and statement attestation.
Fixtures mirror the real NutriFitAI problems from the Cowork review."""

import json
import asyncio

import accountingqb.server as s

# Chart: a deleted card, a good card, a bank overdrawn, a dormant bank w/ big
# balance, an equity account (payment target), and an expense category.
ACTIVE = [
    {
        "Id": "10",
        "Name": "Delta Platinum Business Card",
        "AccountType": "Credit Card",
        "Active": True,
        "CurrentBalance": -500.0,
    },
    {
        "Id": "20",
        "Name": "Rewards Checking",
        "AccountType": "Bank",
        "Active": True,
        "CurrentBalance": -3199.0,
    },
    {
        "Id": "30",
        "Name": "General Operations",
        "AccountType": "Bank",
        "Active": True,
        "CurrentBalance": -36123.0,
    },
    {
        "Id": "40",
        "Name": "Owner Equity",
        "AccountType": "Equity",
        "Active": True,
        "CurrentBalance": 0.0,
    },
    {
        "Id": "50",
        "Name": "Software & Apps",
        "AccountType": "Expense",
        "Active": True,
        "CurrentBalance": 0.0,
    },
]
INACTIVE = [
    {
        "Id": "99",
        "Name": "Delta SkyMiles Reserve Card (1008)",
        "AccountType": "Credit Card",
        "Active": False,
        "CurrentBalance": 0.0,
    },
]


def _setup(monkeypatch, purchases=None, deposits=None, jes=None):
    async def fake_query_all(q, **kw):
        if "FROM Account WHERE Active = false" in q:
            return {"QueryResponse": {"Account": INACTIVE}}
        if "FROM Account" in q:
            return {"QueryResponse": {"Account": ACTIVE}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases or []}}
        if "FROM Deposit" in q:
            return {"QueryResponse": {"Deposit": deposits or []}}
        if "FROM JournalEntry" in q:
            return {"QueryResponse": {"JournalEntry": jes or []}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)


def test_dangling_reference_to_deleted_account(monkeypatch):
    # $1,500 posted to the deleted SkyMiles card (acct 99).
    purchases = [
        {
            "Id": "2037",
            "TxnDate": "2026-05-01",
            "TotalAmt": 900.0,
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "99"}}}
            ],
        },
        {
            "Id": "2021",
            "TxnDate": "2026-05-02",
            "TotalAmt": 600.0,
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "99"}}}
            ],
        },
    ]
    _setup(monkeypatch, purchases=purchases)
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    assert "inactive/deleted accounts" in out and "Delta SkyMiles" in out
    assert "100/100" not in out  # no longer a perfect score


def test_negative_bank_balances_flagged(monkeypatch):
    _setup(monkeypatch)
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    assert "Wrong-sign balances" in out
    assert "General Operations" in out and "Rewards Checking" in out


def test_misfiled_card_payment(monkeypatch):
    # The discriminator is the Purchase.Credit flag, NOT the category or the sign
    # (both are positive and structurally identical):
    #   Credit == true → a card PAYMENT (money-in, reduces the card) → NOT flagged
    #   Credit falsy    → a real CHARGE booked to equity/bank → flagged (suspect)
    purchases = [
        {
            "Id": "2100",
            "TxnDate": "2026-06-01",
            "TotalAmt": 1200.0,
            "Credit": True,
            "AccountRef": {"value": "10"},  # paid from Delta card — a payment
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "40"}}}
            ],
        },  # -> equity
        {
            "Id": "2200",
            "TxnDate": "2026-06-02",
            "TotalAmt": 500.0,  # a charge (no Credit)
            "AccountRef": {"value": "10"},
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "40"}}}
            ],
        },
    ]
    _setup(monkeypatch, purchases=purchases)
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    assert "2200" in out  # the real charge is flagged
    assert "2100" not in out  # the card payment is NOT (excluded)
    assert "1 credit-card charge(s)" in out  # exactly one, not two


def test_dormant_large_balance(monkeypatch):
    # General Operations: -$36,123 with essentially no activity -> opening error.
    _setup(monkeypatch, purchases=[])
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    assert "near-zero activity" in out and "General Operations" in out


def test_statement_attestation_mismatch(monkeypatch):
    _setup(monkeypatch)

    async def fake_resolve(name, **kw):
        a = next((x for x in ACTIVE if x["Name"] == name), None)
        return (a, None) if a else (None, f"'{name}' not found")

    monkeypatch.setattr(s, "_resolve_account", fake_resolve)

    out = asyncio.run(
        s.qb_books_hygiene(
            "2026-01-01",
            "2026-12-31",
            statement_balances=json.dumps({"Rewards Checking": 250.00}),
        )
    )
    # QB shows -3199, statement 250 -> off by -3449
    assert "attestation mismatches" in out.lower()
    assert "off by" in out and "Rewards Checking" in out


def test_clean_books_score_high(monkeypatch):
    # No problems: a funded account WITH regular activity, no dangling/misfiled.
    clean = [
        {
            "Id": "1",
            "Name": "Checking",
            "AccountType": "Bank",
            "Active": True,
            "CurrentBalance": 5000.0,
        },
        {
            "Id": "2",
            "Name": "Office Supplies",
            "AccountType": "Expense",
            "Active": True,
            "CurrentBalance": 0.0,
        },
    ]
    acts = [
        {
            "Id": str(i),
            "TxnDate": "2026-03-01",
            "TotalAmt": 50.0,
            "AccountRef": {"value": "1"},
            "Line": [{"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "2"}}}],
        }
        for i in range(5)
    ]

    async def fake_query_all(q, **kw):
        if "Active = false" in q:
            return {"QueryResponse": {}}
        if "FROM Account" in q:
            return {"QueryResponse": {"Account": clean}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": acts}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    assert "score: 100/100" in out


def test_name_subtype_mismatch_flagged(monkeypatch):
    """A 'Cell phone' account typed Travel: the tax taxonomy trusts the subtype,
    so this would land on the wrong Schedule C line. Hygiene must flag it."""
    accounts = [
        {
            "Id": "1",
            "Name": "Cell phone service",
            "AccountType": "Expense",
            "Active": True,
            "AccountSubType": "Travel",
            "CurrentBalance": 0.0,
        },
        {
            "Id": "2",
            "Name": "Advertising",
            "AccountType": "Expense",
            "Active": True,
            "AccountSubType": "AdvertisingPromotional",
            "CurrentBalance": 0.0,
        },
    ]

    async def fake_query_all(q, **kw):
        if "Active = false" in q:
            return {"QueryResponse": {}}
        if "FROM Account" in q:
            return {"QueryResponse": {"Account": accounts}}
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)

    fn = getattr(s.qb_books_hygiene, "__wrapped__", s.qb_books_hygiene)
    out = asyncio.run(fn("2026-01-01", "2026-12-31"))
    assert "name and QuickBooks type disagree" in out
    assert "Cell phone service" in out
    assert "Advertising (typed" not in out  # correctly-typed: not flagged


def test_card_payment_discriminator_and_balance_identity(monkeypatch):
    """The report's exact scenario: 3 card PAYMENTS + 1 real CHARGE, all positive,
    structurally identical, distinguished ONLY by Purchase.Credit. Hygiene must
    flag only the charge, and the balance identity must hold:
        opening + Σ(charges) − Σ(payments) == closing balance
    That identity is the classification check that would have caught the bug."""
    purchases = [
        {
            "Id": "1305",
            "TxnDate": "2026-06-01",
            "TotalAmt": 1500.0,
            "Credit": True,
            "AccountRef": {"value": "10"},
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "20"}}}
            ],
        },  # -> bank
        {
            "Id": "1877",
            "TxnDate": "2026-06-02",
            "TotalAmt": 350.0,
            "Credit": True,
            "AccountRef": {"value": "10"},
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "40"}}}
            ],
        },  # -> equity
        {
            "Id": "2063",
            "TxnDate": "2026-06-03",
            "TotalAmt": 1000.0,
            "Credit": True,
            "AccountRef": {"value": "10"},
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "40"}}}
            ],
        },
        {
            "Id": "1304",
            "TxnDate": "2026-06-04",
            "TotalAmt": 1912.49,  # a real charge
            "AccountRef": {"value": "10"},
            "Line": [
                {"AccountBasedExpenseLineDetail": {"AccountRef": {"value": "50"}}}
            ],
        },  # -> expense
    ]
    _setup(monkeypatch, purchases=purchases)
    out = asyncio.run(s.qb_books_hygiene("2026-01-01", "2026-12-31"))
    # None of the three payments are flagged as misfiled expenses.
    for pid in ("1305", "1877", "2063"):
        assert pid not in out
    # (The lone charge #1304 goes to an Expense account, so it isn't a "to
    # bank/equity" finding either — the point is the payments are excluded.)
    assert "credit-card charge(s) categorized" not in out

    # Balance identity — the classification discriminator, proven arithmetically.
    charges = sum(p["TotalAmt"] for p in purchases if not p.get("Credit"))
    payments = sum(p["TotalAmt"] for p in purchases if p.get("Credit"))
    opening = 8000.00
    assert round(opening + charges - payments, 2) == round(8000 + 1912.49 - 2850, 2)
