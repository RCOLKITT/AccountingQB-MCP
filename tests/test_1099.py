"""1099-NEC report must respect QuickBooks' Vendor1099 flag — never report
banks, credit-card payments, corporations, product purchases, or the owner."""

import asyncio

import accountingqb.server as s


def _vendors():
    return [
        {
            "Id": "1",
            "DisplayName": "Contractor Jane",
            "Vendor1099": True,
            "TaxIdentifier": "12-3456789",
            "BillAddr": {"Line1": "1 St", "City": "X"},
        },
        {"Id": "2", "DisplayName": "JPMorgan Chase", "Vendor1099": False},
        {"Id": "3", "DisplayName": "Ryan Colkitt (Owner)", "Vendor1099": False},
        {"Id": "4", "DisplayName": "Anthropic", "Vendor1099": False},
    ]


def _purchases():
    return [
        {"EntityRef": {"value": "1"}, "TotalAmt": 5000.0},  # flagged contractor
        {"EntityRef": {"value": "2"}, "TotalAmt": 8269.76},  # bank
        {"EntityRef": {"value": "3"}, "TotalAmt": 20350.0},  # owner
        {"EntityRef": {"value": "4"}, "TotalAmt": 3000.0},  # SaaS corp
    ]


def _patch(monkeypatch):
    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {"QueryResponse": {"Vendor": _vendors()}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": _purchases()}}
        return {"QueryResponse": {}}  # BillPayment, Bill

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)


def test_only_flagged_vendors_are_reportable(monkeypatch):
    _patch(monkeypatch)
    out = asyncio.run(s.qb_1099_contractor_report("2025"))
    # exactly one reportable vendor (the flagged contractor)
    assert "**Reportable vendors:** 1" in out
    assert "Contractor Jane" in out
    # banks / owner / SaaS never counted as reportable
    assert "Vendors requiring 1099-NEC: 1" in out
    assert "Reportable (1099-flagged) payments: $5,000" in out
    # they appear only in the advisory review list, clearly not reportable
    assert "Not marked for 1099 — review" in out
    for name in ("JPMorgan Chase", "Ryan Colkitt", "Anthropic"):
        assert name in out  # shown for review
    # the grand total is NOT the $36k sum of everything
    assert "$36," not in out and "$53," not in out


def test_empty_state_when_nothing_flagged(monkeypatch):
    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {
                "QueryResponse": {
                    "Vendor": [
                        {
                            "Id": "2",
                            "DisplayName": "JPMorgan Chase",
                            "Vendor1099": False,
                        }
                    ]
                }
            }
        if "FROM Purchase" in q:
            return {
                "QueryResponse": {
                    "Purchase": [{"EntityRef": {"value": "2"}, "TotalAmt": 8000.0}]
                }
            }
        return {"QueryResponse": {}}

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    out = asyncio.run(s.qb_1099_contractor_report("2025"))
    assert "**Reportable vendors:** 0" in out
    assert "Track payments for 1099" in out  # guidance to flag contractors


def test_cash_basis_and_card_exclusion(monkeypatch):
    # 1099-NEC is cash-basis and excludes card payments. Contractor Jane, flagged,
    # in 2025:  $3,000 check purchase (counts) + $2,000 credit-card purchase
    # (EXCLUDED → 1099-K) + $4,000 bill payment by check (counts). A $9,000 unpaid
    # Bill must NOT count — the tool now totals payments, not accrual obligations.
    vendors = [
        {
            "Id": "1",
            "DisplayName": "Contractor Jane",
            "Vendor1099": True,
            "TaxIdentifier": "12-3456789",
            "BillAddr": {"Line1": "1 St", "City": "X"},
        }
    ]
    purchases = [
        {"EntityRef": {"value": "1"}, "TotalAmt": 3000.0, "PaymentType": "Check"},
        {"EntityRef": {"value": "1"}, "TotalAmt": 2000.0, "PaymentType": "CreditCard"},
    ]
    bill_payments = [
        {"VendorRef": {"value": "1"}, "TotalAmt": 4000.0, "PayType": "Check"},
    ]

    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {"QueryResponse": {"Vendor": vendors}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        if "FROM BillPayment" in q:  # check before "FROM Bill" (substring)
            return {"QueryResponse": {"BillPayment": bill_payments}}
        return {"QueryResponse": {}}

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    out = asyncio.run(s.qb_1099_contractor_report("2025"))
    # $3,000 check + $4,000 bill payment = $7,000; card ($2k) + any bill excluded.
    assert "$7,000" in out
    assert "$9,000" not in out  # accrual bill never counted
    assert "$11,000" not in out and "$16,000" not in out  # not summing card/bill
    assert "2 payments" in out  # the check purchase + the bill payment only
    # Honest workpaper framing.
    assert "Card payments are excluded" in out
    assert "Workpaper, not a filing" in out
