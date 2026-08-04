"""End-to-end assertions against the golden book (see golden_book.py). This is
the fixture the v3.16.2 audit recommended: a single realistic chart that carries
the structures which broke every release this week. If one of these fails, a real
book would have surfaced it before shipping."""

import asyncio

from golden_book import patch_book, GOLDEN_ACCOUNTS

import accountingqb.server as s

HOME_10 = {"home_office": {"percentage": 0.10, "basis_note": "250/2500 sqft"}}


def _unwrap(tool):
    return getattr(tool, "__wrapped__", tool)


def _sched_c(profile=HOME_10):
    with patch_book(profile=profile):
        return asyncio.run(_unwrap(s.qb_schedule_c)("2025"))


def test_parent_posted_travel_residual_captured():
    """(1) The $200 posted directly to the Travel parent is not dropped — Line 24a
    is 2,200 (800 + 1,200 + 200), not 2,000."""
    out = _sched_c()
    assert "Line 24a" in out
    # Travel children + the parent residual all land on 24a (2,200); Cell phone
    # (mistyped Travel) adds 1,200 → 3,400 total on the line.
    assert "$3,400.00" in out


def test_duplicate_leaf_repairs_split_correctly():
    """(2) Standalone 'Repairs & maintenance' ($500) stays on Line 21; the
    Home office one ($400) is in the 8829 base — they do NOT merge."""
    out = _sched_c()
    assert "Line 21" in out and "$500.00" in out
    # home base = 400 + 1000 + 600 + 2000 = 4000 → Line 30 at 10% = 400
    assert "$4,000.00 × 10.00% business use" in out
    assert "Line 30 — Home office (Form 8829): $400.00" in out


def test_inactive_home_account_routes():
    """(3) The INACTIVE 'Mortgage interest (deleted)' ($2,000) is inside the home
    base, not deducted at 100% on an interest line."""
    out = _sched_c()
    assert "Line 16" not in out                    # not on the interest line
    # 2,000 is folded into the 4,000 home base (asserted above), not a standalone line
    assert "home expenses $4,000.00" in out


def test_home_personal_share_reconciles():
    """(5) Conservation holds: deductible + statutory + personal home share tie to
    the P&L. Personal home share = 4,000 × 90% = 3,600."""
    out = _sched_c()
    assert "3,600.00 personal home share" in out
    assert "Does not reconcile" not in out


def test_meals_50_percent():
    out = _sched_c()
    assert "× 50% (IRC §274(n)) = $500.00" in out   # 1,000 meals at 50%


def test_allocation_candidate_flagged_when_no_profile():
    """(7) With no allocation set, the mixed Internet & TV / Cell phone accounts
    are flagged as needing a business-use %, not silently deducted at 100%."""
    out = _sched_c(profile={})
    assert "Likely need a business-use %" in out


def test_owner_draws_excludes_system_equity_on_golden_book():
    """(6) Owner draws counts only real owner activity: +40,000 from Owner
    investments; Opening Balance Equity's −130,000 adjustment is excluded."""
    with patch_book():
        out = asyncio.run(_unwrap(s.qb_owner_draws)(2025))
    assert "Net owner activity: $40,000.00" in out
    assert "net contribution" in out
    assert "($130,000.00)" not in out
    assert "Excluded QuickBooks system equity" in out


def test_t2125_on_golden_book_routes_home_to_9945():
    """The same book through the Canadian path: home → line 9945, meals 50%,
    standalone repairs off the home base."""
    with patch_book(profile=HOME_10, region="CA"):
        out = asyncio.run(_unwrap(s.qb_t2125_summary)(2025))
    assert "Line 9945 — Business-use-of-home: $400.00" in out
    assert "$4,000.00 × 10.00%" in out
    assert "Line 30" not in out and "Form 8829" not in out


def test_golden_book_has_the_seven_structural_properties():
    """Guardrail: the fixture must keep the properties that make it valuable — if
    someone simplifies it away, this fails and explains why."""
    subs = [a["AccountSubType"] for a in GOLDEN_ACCOUNTS]
    fqns = [a["FullyQualifiedName"] for a in GOLDEN_ACCOUNTS]
    names = [a["Name"] for a in GOLDEN_ACCOUNTS]
    assert any(":" in f for f in fqns)                              # sub-accounts
    assert names.count("Repairs & maintenance") == 2               # duplicate leaf
    assert any(not a["Active"] for a in GOLDEN_ACCOUNTS)           # inactive
    assert any(st.endswith("HomeOffice") for st in subs)          # home subtype family
    assert "OpeningBalanceEquity" in subs and "RetainedEarnings" in subs   # system equity
    # name↔subtype disagreement: Cell phone typed Travel
    assert any(a["Name"] == "Cell phone" and a["AccountSubType"] == "Travel"
               for a in GOLDEN_ACCOUNTS)
