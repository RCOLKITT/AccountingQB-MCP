"""The golden book — one anonymized fixture with the structural properties that
real charts of accounts have and synthetic fixtures don't. Every property below
corresponds to a class of bug found only against a real book (NutriFitAI):

  1. amounts posted DIRECTLY to a parent account that also has children
     (Travel parent carries $200 of its own)                → parent-residual drop
  2. DUPLICATE leaf names under different parents
     (standalone 'Repairs & maintenance' vs. Home office's)  → home over-match / merge
  3. INACTIVE accounts carrying balances
     ('Mortgage interest (deleted)')                         → home under-match
  4. name ↔ subtype DISAGREEMENT ('Cell phone' typed Travel) → misclassification
  5. the home-office AccountSubType FAMILY, populated        → home routing
  6. SYSTEM equity with large balances (Opening Balance
     Equity, Retained Earnings)                              → owner-draws inversion
  7. a mixed personal/business account (Internet & TV)       → allocation candidate

Amounts are round and fictional; the STRUCTURE is what matters. Reuse this across
tests via `patch_book()` rather than hand-rolling one-off fixtures.
"""

from contextlib import contextmanager
from unittest.mock import patch

import accountingqb.server as s


# --- Chart of accounts (active + inactive) ----------------------------------
GOLDEN_ACCOUNTS = [
    {"Id": "1", "Name": "Sales", "AccountType": "Income",
     "AccountSubType": "SalesOfProductIncome", "FullyQualifiedName": "Sales", "Active": True},
    {"Id": "10", "Name": "Advertising", "AccountType": "Expense",
     "AccountSubType": "AdvertisingPromotional", "FullyQualifiedName": "Advertising", "Active": True},
    # (1) parent with a direct posting + (children)
    {"Id": "20", "Name": "Travel", "AccountType": "Expense",
     "AccountSubType": "Travel", "FullyQualifiedName": "Travel", "Active": True},
    {"Id": "21", "Name": "Hotels", "AccountType": "Expense",
     "AccountSubType": "Travel", "FullyQualifiedName": "Travel:Hotels", "Active": True},
    {"Id": "22", "Name": "Airfare", "AccountType": "Expense",
     "AccountSubType": "Travel", "FullyQualifiedName": "Travel:Airfare", "Active": True},
    # (2) duplicate leaf name — this one is the STANDALONE business repairs
    {"Id": "30", "Name": "Repairs & maintenance", "AccountType": "Expense",
     "AccountSubType": "RepairMaintenance",
     "FullyQualifiedName": "Repairs & maintenance", "Active": True},
    # (5) home-office subtype family, under a 'Home office' parent
    {"Id": "40", "Name": "Repairs & maintenance", "AccountType": "Expense",
     "AccountSubType": "RepairsAndMaintainceHomeOffice",
     "FullyQualifiedName": "Home office:Repairs & maintenance", "Active": True},
    {"Id": "41", "Name": "Property taxes", "AccountType": "Expense",
     "AccountSubType": "PropertyTaxHomeOffice",
     "FullyQualifiedName": "Home office:Property taxes", "Active": True},
    {"Id": "42", "Name": "Home utilities", "AccountType": "Expense",
     "AccountSubType": "UtilitiesHomeOffice",
     "FullyQualifiedName": "Home office:Home utilities", "Active": True},
    # (3) INACTIVE home cost with a generic subtype (caught only by FQN + inactive)
    {"Id": "43", "Name": "Mortgage interest (deleted)", "AccountType": "Expense",
     "AccountSubType": "InterestPaid",
     "FullyQualifiedName": "Home office:Mortgage interest (deleted)", "Active": False},
    {"Id": "50", "Name": "Business meals", "AccountType": "Expense",
     "AccountSubType": "EntertainmentMeals", "FullyQualifiedName": "Business meals", "Active": True},
    # (4) name ↔ subtype disagreement: a phone account mistyped as Travel
    {"Id": "60", "Name": "Cell phone", "AccountType": "Expense",
     "AccountSubType": "Travel", "FullyQualifiedName": "Cell phone", "Active": True},
    # (7) mixed personal/business — an allocation candidate (utilities)
    {"Id": "70", "Name": "Internet & TV", "AccountType": "Expense",
     "AccountSubType": "Utilities", "FullyQualifiedName": "Internet & TV", "Active": True},
    # (6) system + owner equity
    {"Id": "80", "Name": "Owner investments", "AccountType": "Equity",
     "AccountSubType": "OwnersEquity", "FullyQualifiedName": "Owner investments", "Active": True},
    {"Id": "81", "Name": "Opening balance equity", "AccountType": "Equity",
     "AccountSubType": "OpeningBalanceEquity",
     "FullyQualifiedName": "Opening balance equity", "Active": True},
    {"Id": "82", "Name": "Retained earnings", "AccountType": "Equity",
     "AccountSubType": "RetainedEarnings", "FullyQualifiedName": "Retained earnings", "Active": True},
]


def _leaf(name, amt):
    return {"ColData": [{"value": name}, {"value": f"{amt:.2f}"}]}


# --- P&L (nested, with a parent residual) -----------------------------------
# Income $50,000. Expenses total $10,100:
#   Advertising 1000 · Travel 2200 (800+1200 children + 200 posted to parent)
#   Repairs 500 (standalone) · Home office 4000 (400+1000+600+2000, incl. inactive)
#   Meals 1000 · Cell phone 1200 · Internet & TV 200
GOLDEN_PL = {"Rows": {"Row": [
    {"Header": {"ColData": [{"value": "Income"}]},
     "Rows": {"Row": [_leaf("Sales", 50000.00)]},
     "Summary": {"ColData": [{"value": "Total Income"}, {"value": "50000.00"}]}},
    {"Header": {"ColData": [{"value": "Expenses"}]},
     "Rows": {"Row": [
         _leaf("Advertising", 1000.00),
         {"Header": {"ColData": [{"value": "Travel"}]},
          "Rows": {"Row": [_leaf("Hotels", 800.00), _leaf("Airfare", 1200.00)]},
          "Summary": {"ColData": [{"value": "Total Travel"}, {"value": "2200.00"}]}},  # +200 to parent
         _leaf("Repairs & maintenance", 500.00),
         {"Header": {"ColData": [{"value": "Home office"}]},
          "Rows": {"Row": [
              _leaf("Repairs & maintenance", 400.00),
              _leaf("Property taxes", 1000.00),
              _leaf("Home utilities", 600.00),
              _leaf("Mortgage interest (deleted)", 2000.00)]},
          "Summary": {"ColData": [{"value": "Total Home office"}, {"value": "4000.00"}]}},
         _leaf("Business meals", 1000.00),
         _leaf("Cell phone", 1200.00),
         _leaf("Internet & TV", 200.00)]},
     "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "10100.00"}]}},
]}}


# --- Equity GL for qb_owner_draws (Amount + running-Balance columns) ---------
_GL_COLS = {"Columns": {"Column": [
    {"ColTitle": "Date", "MetaData": [{"Name": "ColKey", "Value": "tx_date"}]},
    {"ColTitle": "Amount", "ColType": "Money",
     "MetaData": [{"Name": "ColKey", "Value": "subt_nat_amount"}]},
    {"ColTitle": "Balance", "ColType": "Money",
     "MetaData": [{"Name": "ColKey", "Value": "rbal_nat_amount"}]}]}}


def _equity_gl(name, rows):
    return {**_GL_COLS, "Rows": {"Row": [
        {"Header": {"ColData": [{"value": name}]}, "Rows": {"Row": rows}}]}}


GOLDEN_EQUITY_GL = {
    "80": _equity_gl("Owner investments", [
        {"ColData": [{"value": ""}, {"value": ""}, {"value": "0.00"}]},
        {"ColData": [{"value": "2025-02-01"}, {"value": "40000.00"}, {"value": "40000.00"}]}]),
    # a huge QB deletion-adjustment JE on OBE — must NOT be counted as a draw
    "81": _equity_gl("Opening balance equity", [
        {"ColData": [{"value": ""}, {"value": ""}, {"value": "0.00"}]},
        {"ColData": [{"value": "2025-03-11"}, {"value": "-130000.00"}, {"value": "-130000.00"}]}]),
}


@contextmanager
def patch_book(profile=None, region="US"):
    """Patch the QuickBooks layer to serve the golden book. ``profile`` is the
    allocation profile qb_schedule_c/qb_t2125_summary will see."""
    async def fake_req(m, p, params=None, **k):
        if "reports/GeneralLedger" in p:
            return GOLDEN_EQUITY_GL.get((params or {}).get("account"), {"Rows": {"Row": []}})
        return GOLDEN_PL     # ProfitAndLoss

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": GOLDEN_ACCOUNTS}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [
            {"CompanyName": "Golden Co", "Country": region}]}}

    async def fake_profile(y):
        return profile or {}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        yield
