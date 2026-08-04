"""Runway/burn sign convention + anomaly-detection noise reduction (QA queue)."""

import asyncio

import accountingqb.server as s


def _pl(income, expenses, net):
    return {"Rows": {"Row": [
        {"Summary": {"ColData": [{"value": "Total Income"}, {"value": f"{income}"}]}},
        {"Summary": {"ColData": [{"value": "Total Expenses"}, {"value": f"{expenses}"}]}},
        {"Summary": {"ColData": [{"value": "Net Operating Income"}, {"value": f"{net}"}]}},
        {"Summary": {"ColData": [{"value": "Net Income"}, {"value": f"{net}"}]}},
    ]}}


def test_income_helper_excludes_net_income():
    inc, exp = s._pl_income_expense_totals(_pl(57.06, 6300, -6242.94))
    assert inc == 57.06 and exp == 6300.0  # Net Income NOT read as revenue


def _patch_runway(monkeypatch, bank_balance, income, expenses, net):
    async def fake_query(q, **kw):
        if "AccountType = 'Bank'" in q:
            return {"QueryResponse": {"Account": [{"CurrentBalance": bank_balance}]}}
        return {"QueryResponse": {}}

    async def fake_request(method, endpoint, **kw):
        return _pl(income, expenses, net) if "ProfitAndLoss" in endpoint else {}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_request", fake_request)


def test_runway_positive_no_negative_revenue(monkeypatch):
    # 3-month P&L: income 3000, expenses 9000 -> $1k rev, $3k exp, $2k burn/mo
    _patch_runway(monkeypatch, 10000, 3000, 9000, -6000)
    out = asyncio.run(s.qb_runway_calculator())
    assert "-$" not in out                       # no negative revenue/burn/runway
    assert "Monthly revenue:** $1,000" in out
    assert "Net monthly burn:** $2,000" in out
    assert "Runway: 5.0 months" in out


def test_runway_negative_cash_is_no_runway(monkeypatch):
    _patch_runway(monkeypatch, -500, 3000, 9000, -6000)
    out = asyncio.run(s.qb_runway_calculator())
    assert "No runway" in out
    assert "months" not in out.split("No runway")[0][-40:]  # not "-x months"


# --- anomaly detection ---------------------------------------------------------
def _purchase(pid, vendor, date, amt):
    return {"Id": pid, "TxnDate": date, "TotalAmt": amt,
            "EntityRef": {"name": vendor}, "Line": []}


def _patch_anomaly(monkeypatch, purchases):
    async def fake_query(q, **kw):
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": purchases}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)


def test_recurring_vendor_not_weekend_flagged(monkeypatch):
    # Cursor appears 3x on weekends -> recurring -> exempt. OneOff once -> flagged.
    purchases = [
        _purchase("1", "Cursor", "2026-08-01", 50),   # Sat
        _purchase("2", "Cursor", "2026-08-08", 50),   # Sat
        _purchase("3", "Cursor", "2026-08-15", 50),   # Sat
        _purchase("9", "OneOff Corp", "2026-08-02", 500),  # Sun, single
    ]
    _patch_anomaly(monkeypatch, purchases)
    out = asyncio.run(s.qb_anomaly_detection("2026-08-01", "2026-08-31", "low"))
    weekend = [ln for ln in out.splitlines() if "Weekend" in ln or "Saturday" in ln
               or "Sunday" in ln]
    joined = "\n".join(weekend)
    assert "Cursor" not in joined            # recurring vendor exempt
    assert "OneOff Corp" in out              # single-shot weekend still flagged


def test_duplicates_same_day_only(monkeypatch):
    purchases = [
        # Acme: same amount, SAME day -> duplicate
        _purchase("1", "Acme", "2026-08-05", 200),
        _purchase("2", "Acme", "2026-08-05", 200),
        # Beta: same amount, ADJACENT day (2 txns, not recurring) -> NOT duplicate
        _purchase("3", "Beta", "2026-08-10", 75),
        _purchase("4", "Beta", "2026-08-11", 75),
    ]
    _patch_anomaly(monkeypatch, purchases)
    out = asyncio.run(s.qb_anomaly_detection("2026-08-01", "2026-08-31", "low"))
    dup = "\n".join(ln for ln in out.splitlines() if "Duplicate" in ln or "&" in ln)
    assert "Acme" in dup                     # same-day duplicate flagged
    assert "Beta" not in dup                 # adjacent-day not a duplicate


def test_weekend_bulk_batch_suppressed(monkeypatch):
    """5 distinct vendors all stamped one weekend date = a bulk data-entry /
    reclassification batch, not weekend spending. Suppress the noise, disclose it,
    but still flag a genuine single weekend transaction on a different date."""
    batch = [_purchase(str(i), f"Vendor {i}", "2026-03-01", 100 + i)   # Sun, bulk of 5
             for i in range(5)]
    lone = [_purchase("99", "Real Weekend Corp", "2026-03-07", 800)]   # Sat, single
    _patch_anomaly(monkeypatch, batch + lone)
    out = asyncio.run(s.qb_anomaly_detection("2026-03-01", "2026-03-31", "low"))
    weekend = "\n".join(ln for ln in out.splitlines()
                        if "Weekend" in ln or "Saturday" in ln or "Sunday" in ln)
    assert "Vendor 0" not in weekend and "Vendor 4" not in weekend   # batch suppressed
    assert "Real Weekend Corp" in out                                # genuine one kept
    assert "weekend flags suppressed" in out                         # disclosed
