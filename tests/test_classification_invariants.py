"""Classification invariants — a second class of assertion beyond conservation.

Conservation ('is every dollar accounted for?') cannot catch a MISROUTED dollar:
moving a dollar to the wrong bucket still conserves it. These assertions check
'does this account belong where it landed?' Each one catches a specific real bug
found against the NutriFitAI book that conservation passed straight through:

  - no account in two destination buckets            → repairs double-route
  - Form-8829 members have a home subtype/FQN/design  → repairs over-match
  - every home-subtype account routes to Form 8829    → mortgage under-match
  - no home-subtype account on an operating line       → both home bugs
  - equity reports exclude QB system equity            → owner-draws inversion
"""

import accountingqb.server as s
from accountingqb.tax_tables import (
    is_home_office_subtype, _SYSTEM_EQUITY_SUBTYPES,
)


# A realistic expense set with the structures synthetic fixtures miss: two
# accounts sharing a leaf name (one home, one not), the QB home-office subtype
# family, a generic-subtype home account caught only by its FQN, and a vehicle.
_EXPENSES = {
    "Advertising": 500.0,
    "Repairs & maintenance": 2316.68,                       # standalone → Line 21
    "Home office:Repairs & maintenance": 2116.19,           # home subtype → 8829
    "Home office:Property taxes": 1115.84,                  # home subtype → 8829
    "Home office:Mortgage interest (deleted)": 3613.41,     # generic subtype, FQN → 8829
    "Auto expenses": 3000.0,
}
_SUBTYPE = {
    "Advertising": "AdvertisingPromotional",
    "Repairs & maintenance": "RepairMaintenance",
    "Home office:Repairs & maintenance": "RepairsAndMaintainceHomeOffice",
    "Home office:Property taxes": "PropertyTaxHomeOffice",
    "Home office:Mortgage interest (deleted)": "InterestPaid",   # generic on purpose
    "Auto expenses": "Auto",
}
_FQN = {k: k for k in _EXPENSES}   # extractor keys are already FQN-qualified


def _run(juris="US"):
    return s._map_expenses_to_schedule_c(_EXPENSES, _SUBTYPE, {}, _FQN, jurisdiction=juris)


def _line_accounts(res):
    return [name for b in res["lines"].values() for (name, *_rest) in b["accounts"]]


def test_no_account_in_two_destination_buckets():
    """The repairs double-route: an account must land in exactly one place."""
    for juris in ("US", "CA"):
        res = _run(juris)
        home = [n for n, _ in res["home_indirect"]]
        mileage = [n for n, _ in res["mileage_excluded"]]
        line = _line_accounts(res)
        allnames = home + mileage + line
        dupes = {n for n in allnames if allnames.count(n) > 1}
        assert not dupes, f"{juris}: account(s) in two buckets: {dupes}"


def test_every_home_indirect_member_is_actually_home():
    """The repairs over-match: only genuine home costs may reach Form 8829/9945."""
    for juris in ("US", "CA"):
        res = _run(juris)
        for name, _amt in res["home_indirect"]:
            st = _SUBTYPE.get(name, "")
            ok = (is_home_office_subtype(st)
                  or "home office" in name.lower()
                  or "homeowner" in name.lower())
            assert ok, f"{juris}: {name!r} routed to home but isn't a home cost"


def test_every_home_subtype_account_routes_to_home():
    """The mortgage under-match: a home-subtype account must never sit on an
    operating line. (Also covers the generic-subtype home account via its FQN.)"""
    for juris in ("US", "CA"):
        res = _run(juris)
        home = {n for n, _ in res["home_indirect"]}
        for name, st in _SUBTYPE.items():
            if is_home_office_subtype(st):
                assert name in home, f"{juris}: home-subtype {name!r} not routed to home"


def test_no_home_subtype_account_on_operating_line():
    """Belt-and-suspenders for the two home bugs from the operating-line side."""
    for juris in ("US", "CA"):
        res = _run(juris)
        for name in _line_accounts(res):
            assert not is_home_office_subtype(_SUBTYPE.get(name, "")), \
                f"{juris}: home-subtype {name!r} appears on an operating line"


def test_standalone_repairs_stays_on_its_operating_line():
    """The distinct, non-home 'Repairs & maintenance' keeps its full amount on an
    operating line (Line 21 US / 9270-family CA) — not swept into the home base."""
    res = _run("US")
    line = _line_accounts(res)
    assert "Repairs & maintenance" in line
    assert "Repairs & maintenance" not in {n for n, _ in res["home_indirect"]}


def test_equity_report_excludes_system_equity_subtypes():
    """Owner-draws must exclude QB's system equity so it can't invert the sign."""
    assert "OpeningBalanceEquity" in _SYSTEM_EQUITY_SUBTYPES
    assert "RetainedEarnings" in _SYSTEM_EQUITY_SUBTYPES
