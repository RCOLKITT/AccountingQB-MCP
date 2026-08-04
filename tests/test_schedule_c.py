"""Schedule C mapping correctness — the CPA-facing numbers must be right.

Guards the bugs QA found: substring mis-maps (car in "Credit Card", tax in
"Taxis"), qb_schedule_c_detailed summing account balances, and Line 28 silently
dropping unmapped expenses. Golden vector: the two Schedule C tools must AGREE
and both must reconcile to the P&L expense total.
"""

import asyncio
import re

import accountingqb.server as s


# --- Synthetic P&L with the exact account names QA flagged --------------------
_EXPENSES = {
    "Taxis or shared rides": 690.94,      # must be Travel (24a), NOT Taxes (23)
    "Credit Card Interest": 7417.04,      # Other interest (16b), NOT 16a
    "Mortgage Interest": 3613.41,         # 16a
    "Business Licences": 806.00,          # Taxes & licenses (23)
    "Hotels": 690.30,                     # Travel (24a)
    "Electricity": 317.00,                # Utilities (25)
    "Advertising": 500.00,                # 8
    "Office Supplies": 1200.00,           # 18
}
_INCOME = 57.06
_EXP_TOTAL = round(sum(_EXPENSES.values()), 2)  # 15234.69


def _pl_fixture():
    exp_rows = [{"ColData": [{"value": n}, {"value": f"{v}"}]}
                for n, v in _EXPENSES.items()]
    return {"Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [{"ColData": [{"value": "Other Income"},
                                       {"value": f"{_INCOME}"}]}]},
         "Summary": {"ColData": [{"value": "Total Income"},
                                 {"value": f"{_INCOME}"}]}},
        {"Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": exp_rows},
         "Summary": {"ColData": [{"value": "Total Expenses"},
                                 {"value": f"{_EXP_TOTAL}"}]}},
    ]}}


def _patch(monkeypatch):
    async def fake_request(method, endpoint, **kw):
        return _pl_fixture() if "ProfitAndLoss" in endpoint else {}

    async def fake_query(q, **kw):
        return {"QueryResponse": {}}

    async def fake_region():
        return {"region": "US", "subdivision": "", "home_currency": "USD",
                "multicurrency": False}

    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)


def _dollar(text, label):
    m = re.search(re.escape(label) + r".*?\$([\d,]+\.\d{2})", text)
    return float(m.group(1).replace(",", "")) if m else None


# --- matcher unit checks (via the canonical taxonomy, name fallback) ---------
def _line(name):
    return s.classify_account(name, None, "US")[0]


def test_matcher_no_substring_bugs():
    assert _line("Delta Platinum Business Card") == "27a"  # not car (catch-all)
    assert _line("Taxis or shared rides") == "24a"         # not tax
    assert _line("Credit Card Interest") == "16b"          # not mortgage
    assert _line("Mortgage Interest") == "16a"
    assert _line("Advertising") == "8"                     # stem match
    assert _line("Electricity") == "25"


def test_nothing_dropped_reconciles():
    res = s._map_expenses_to_schedule_c(_EXPENSES)
    total = sum(d["amount"] for d in res["lines"].values())
    total += sum(a for _, a in res["home_indirect"]) + sum(a for _, a in res["mileage_excluded"])
    assert abs(total - _EXP_TOTAL) < 0.01  # every dollar lands somewhere


# --- golden vector: both tools agree and reconcile to the P&L -----------------
def test_schedule_c_reconciles_to_pl(monkeypatch):
    _patch(monkeypatch)
    out = asyncio.run(s.qb_schedule_c("2025"))
    total = _dollar(out, "Line 28")
    assert total is not None and abs(total - _EXP_TOTAL) < 0.01
    assert "Does not reconcile" not in out
    # Taxis on Travel, not Taxes; credit-card interest on 16b
    assert "Line 24a" in out and "Taxis" in out
    assert "Line 16b" in out


def test_two_schedule_c_tools_agree(monkeypatch):
    _patch(monkeypatch)
    a = _dollar(asyncio.run(s.qb_schedule_c("2025")), "Line 28 — Total expenses")
    b = _dollar(asyncio.run(s.qb_schedule_c_detailed("2025")),
                "Line 28 — Total expenses")
    assert a is not None and b is not None
    assert abs(a - b) < 0.01, f"tools disagree: {a} vs {b}"
    assert abs(a - _EXP_TOTAL) < 0.01
