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


def test_bill_payment_traced_to_bill_accounts(monkeypatch):
    # A contractor is paid through the AP workflow: a $7,000 bill split across two
    # accounts (Contract Labor $5,000 + Reimbursements $2,000), paid in full by a
    # check BillPayment in 2025. The report must trace the payment back to the bill
    # and break the total out BY ACCOUNT (QBO puts no accounts on the payment itself).
    vendors = [
        {
            "Id": "1",
            "DisplayName": "Contractor Jane",
            "Vendor1099": True,
            "TaxIdentifier": "12-3456789",
            "BillAddr": {"Line1": "1 St", "City": "X"},
        }
    ]
    bill = {
        "Id": "301",
        "TotalAmt": 7000.0,
        "VendorRef": {"value": "1"},
        "Line": [
            {
                "Amount": 5000.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"name": "Contract Labor"}
                },
            },
            {
                "Amount": 2000.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"name": "Reimbursements"}
                },
            },
        ],
    }
    bill_payments = [
        {
            "VendorRef": {"value": "1"},
            "TotalAmt": 7000.0,
            "PayType": "Check",
            "Line": [
                {"Amount": 7000.0, "LinkedTxn": [{"TxnId": "301", "TxnType": "Bill"}]}
            ],
        }
    ]

    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {"QueryResponse": {"Vendor": vendors}}
        if "FROM BillPayment" in q:  # before "FROM Bill" (substring)
            return {"QueryResponse": {"BillPayment": bill_payments}}
        if "FROM Bill WHERE Id IN" in q:  # the traced-bill fetch
            return {"QueryResponse": {"Bill": [bill]}}
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
    assert "$7,000" in out  # full amount attributed
    # broken out by the bill's accounts, not lumped as "unresolved"
    assert "Contract Labor: $5,000.00" in out
    assert "Reimbursements: $2,000.00" in out
    assert "unresolved" not in out.lower()


def test_allocation_profile_sets_1099_map(monkeypatch):
    # The 1099 box→account map is set through qb_allocation_profile (QBO doesn't
    # expose its own mapping via the API) and persists in the taxpayer profile.
    saved = {}

    async def fake_save(year, profile):
        saved.clear()
        saved.update(profile)
        return True

    async def fake_get(year):
        return dict(saved)

    async def fake_chart():
        return {}  # skip chart-name validation

    monkeypatch.setattr(s, "_save_allocation_profile", fake_save)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_get)
    monkeypatch.setattr(s, "_account_subtype_map", fake_chart)
    out = asyncio.run(
        s.qb_allocation_profile(
            tax_year=2025,
            nec_1099_accounts_json='{"Contract Labor": "box1", "Reimbursements": "exclude"}',
        )
    )
    assert "saved" in out.lower()
    assert saved["nec_1099_accounts"]["Contract Labor"] == "box1"
    assert saved["nec_1099_accounts"]["Reimbursements"] == "exclude"
    assert "1099 account mapping (NEC + MISC)" in out  # rendered in the profile view
    # A bad treatment value is rejected, not silently stored.
    bad = asyncio.run(
        s.qb_allocation_profile(tax_year=2025, nec_1099_accounts_json='{"Foo": "box9"}')
    )
    assert "box1" in bad and "exclude" in bad  # error names the valid values


def test_report_counts_only_box1_when_mapped(monkeypatch):
    # With a mapping, the reportable total is the box-1 (comp) portion only; the
    # excluded reimbursement is shown but NOT counted.
    vendors = [
        {
            "Id": "1",
            "DisplayName": "Contractor Jane",
            "Vendor1099": True,
            "TaxIdentifier": "12-3456789",
            "BillAddr": {"Line1": "1 St", "City": "X"},
        }
    ]
    bill = {
        "Id": "301",
        "TotalAmt": 7000.0,
        "VendorRef": {"value": "1"},
        "Line": [
            {
                "Amount": 5000.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"name": "Contract Labor"}
                },
            },
            {
                "Amount": 2000.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"name": "Reimbursements"}
                },
            },
        ],
    }
    bill_payments = [
        {
            "VendorRef": {"value": "1"},
            "TotalAmt": 7000.0,
            "PayType": "Check",
            "Line": [
                {"Amount": 7000.0, "LinkedTxn": [{"TxnId": "301", "TxnType": "Bill"}]}
            ],
        }
    ]

    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {"QueryResponse": {"Vendor": vendors}}
        if "FROM BillPayment" in q:
            return {"QueryResponse": {"BillPayment": bill_payments}}
        if "FROM Bill WHERE Id IN" in q:
            return {"QueryResponse": {"Bill": [bill]}}
        return {"QueryResponse": {}}

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    async def fake_profile(year):
        return {
            "nec_1099_accounts": {
                "Contract Labor": "box1",
                "Reimbursements": "exclude",
            }
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_profile)
    out = asyncio.run(s.qb_1099_contractor_report("2025"))
    assert "Account mapping ACTIVE" in out
    assert "1099-NEC box 1: $5,000.00" in out  # only the comp portion
    assert "Reportable (1099-flagged) payments: $5,000.00" in out  # not $7,000
    assert "$7,000.00 paid" in out  # full amount still shown for context
    assert "(excluded)" in out  # reimbursement tagged, not counted


def _misc_fixtures():
    """A landlord + a royalty payee, paid by check purchases with account lines."""
    vendors = [
        {
            "Id": "1",
            "DisplayName": "Main St Properties",
            "Vendor1099": True,
            "TaxIdentifier": "11-1111111",
            "BillAddr": {"Line1": "9 Main St", "City": "X"},
        },
        {
            "Id": "2",
            "DisplayName": "Songwriter Sam",
            "Vendor1099": True,
            "TaxIdentifier": "22-2222222",
            "BillAddr": {"Line1": "2 Tune Ave", "City": "Y"},
        },
    ]
    purchases = [
        # $12,000 rent (misc_rents, over $600) + a $50 royalty (misc_royalties,
        # over $10 but UNDER $600 — must still report; royalties use §6050N $10).
        {
            "EntityRef": {"value": "1"},
            "TotalAmt": 12000.0,
            "PaymentType": "Check",
            "AccountRef": {"name": "Rent - Office"},
        },
        {
            "EntityRef": {"value": "2"},
            "TotalAmt": 50.0,
            "PaymentType": "Check",
            "AccountRef": {"name": "Royalty Payments"},
        },
        # A card-paid rent must be excluded (1099-K).
        {
            "EntityRef": {"value": "1"},
            "TotalAmt": 3000.0,
            "PaymentType": "CreditCard",
            "AccountRef": {"name": "Rent - Office"},
        },
    ]
    return vendors, purchases


def _misc_patch(monkeypatch, vendors, purchases, mapping):
    async def fake_query(q, **kw):
        if "FROM Vendor" in q:
            return {"QueryResponse": {"Vendor": vendors}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}

    async def fake_region():
        return {
            "region": "US",
            "subdivision": "",
            "home_currency": "USD",
            "multicurrency": False,
        }

    async def fake_profile(year):
        return {"nec_1099_accounts": mapping}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_profile)


def test_misc_report_requires_mapping(monkeypatch):
    # With no MISC-mapped accounts, the report refuses to guess and explains how
    # to map — it never invents a rents/royalties classification.
    vendors, purchases = _misc_fixtures()
    _misc_patch(monkeypatch, vendors, purchases, {})
    out = asyncio.run(s.qb_1099_misc_report("2025"))
    assert "No accounts are mapped" in out
    assert "misc_rents" in out and "misc_royalties" in out
    assert "Main St Properties" not in out  # nothing counted


def test_misc_report_boxes_and_royalty_threshold(monkeypatch):
    vendors, purchases = _misc_fixtures()
    _misc_patch(
        monkeypatch,
        vendors,
        purchases,
        {"Rent - Office": "misc_rents", "Royalty Payments": "misc_royalties"},
    )
    out = asyncio.run(s.qb_1099_misc_report("2025"))
    # Rents: only the check payment counts — the $3k card rent is 1099-K.
    assert "Box 1 — Rents" in out and "$12,000.00" in out
    assert "$15,000" not in out  # card payment never counted
    # Royalties: $50 is under $600 but OVER the $10 §6050N threshold → reportable.
    assert "Songwriter Sam" in out
    assert "Box 2 — Royalties" in out and "$50.00" in out
    assert "**Reportable vendors:** 2" in out
    assert "Workpaper, not a filing" in out


def test_misc_mapped_accounts_leave_the_nec_report(monkeypatch):
    # An account mapped to a MISC box must NOT count as NEC comp — and must not
    # show as "unmapped" either (it's designated, just on the other form).
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
        {
            "EntityRef": {"value": "1"},
            "TotalAmt": 5000.0,
            "PaymentType": "Check",
            "AccountRef": {"name": "Contract Labor"},
        },
        {
            "EntityRef": {"value": "1"},
            "TotalAmt": 9000.0,
            "PaymentType": "Check",
            "AccountRef": {"name": "Rent - Office"},
        },
    ]
    _misc_patch(
        monkeypatch,
        vendors,
        purchases,
        {"Contract Labor": "box1", "Rent - Office": "misc_rents"},
    )
    out = asyncio.run(s.qb_1099_contractor_report("2025"))
    assert "1099-NEC box 1: $5,000.00" in out  # rent not in NEC comp
    assert "Reportable (1099-flagged) payments: $5,000.00" in out
    assert "(→ 1099-MISC)" in out  # tagged as designated elsewhere
    # NOT tagged as an unmapped account (the header's standing "still-unmapped"
    # explanation is fine — the account line and warning must not appear)
    assert "⚠️ unmapped" not in out
    assert "in unmapped accounts is NOT counted" not in out


def test_misc_accepts_and_persists_mapping_values(monkeypatch):
    saved = {}

    async def fake_save(year, profile):
        saved.clear()
        saved.update(profile)
        return True

    async def fake_get(year):
        return dict(saved)

    async def fake_chart():
        return {}

    monkeypatch.setattr(s, "_save_allocation_profile", fake_save)
    monkeypatch.setattr(s, "_get_allocation_profile", fake_get)
    monkeypatch.setattr(s, "_account_subtype_map", fake_chart)
    out = asyncio.run(
        s.qb_allocation_profile(
            tax_year=2025,
            nec_1099_accounts_json='{"Rent - Office": "misc_rents"}',
        )
    )
    assert "saved" in out.lower()
    assert saved["nec_1099_accounts"]["Rent - Office"] == "misc_rents"
    assert "MISC Box 1 — Rents" in out  # profile view labels the box
