"""Sales-tax economic-nexus screen: destination-state rollup vs sourced
thresholds, the AND-basis states, and the liability rollup."""

import asyncio

import accountingqb.server as s
import accountingqb.tax_tables as tt


def _inv(pid, state, amount, tax=0.0):
    return {"Id": pid, "TxnDate": "2026-06-01", "TotalAmt": amount,
            "ShipAddr": {"CountrySubDivisionCode": state},
            "TxnTaxDetail": {"TotalTax": tax}}


def _patch(monkeypatch, invoices):
    async def fake_query(q, **kw):
        if "FROM Invoice" in q:
            return {"QueryResponse": {"Invoice": invoices}}
        return {"QueryResponse": {}}  # Customer, SalesReceipt

    async def fake_region():
        return {"region": "US", "subdivision": "", "home_currency": "USD",
                "multicurrency": False}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)


def test_dataset_is_sourced_and_ledgered():
    e = tt.TABLES["US_SALES_TAX_NEXUS"]
    assert e["source_url"].startswith("http") and e["verified"]
    assert tt.verify_ledger_chain()  # nexus row didn't break the chain
    assert e["values"]["CA"]["sales"] == 500_000 and e["values"]["CA"]["txns"] is None
    assert e["values"]["NY"]["basis"] == "and"


def test_nexus_screen_buckets_states(monkeypatch):
    _patch(monkeypatch, [
        _inv("1", "CA", 600_000, 45_000),   # > $500k sales-only -> exposure
        _inv("2", "TX", 450_000, 0),        # 90% of $500k -> approaching
        _inv("3", "NV", 50_000, 3_000),     # < $100k -> below
        _inv("4", "NY", 600_000, 40_000),   # $500k AND 100 txns; only 1 txn -> NOT met
    ])
    out = asyncio.run(s.qb_sales_tax_nexus("2026"))
    # framing: screening reference, sourced
    assert "not** a determination" in out and "verified" in out
    # CA over threshold
    assert "Likely nexus" in out
    ca = [ln for ln in out.splitlines() if ln.startswith("| CA ")]
    assert ca and "$600,000" in ca[0]
    # NY: sales over but AND-basis fails on txn count -> approaching, NOT exposure
    exposure_block = out.split("Approaching")[0]
    assert "| NY " not in exposure_block
    assert "Approaching" in out
    # TX approaching
    assert "| TX " in out
    # liability rollup present
    assert "Sales tax collected (liability)" in out
    assert "$88,000" in out  # 45k + 3k + 40k


def test_no_destination_state(monkeypatch):
    async def fake_query(q, **kw):
        return {"QueryResponse": {}}

    async def fake_region():
        return {"region": "US", "subdivision": "", "home_currency": "USD",
                "multicurrency": False}
    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "_get_region", fake_region)
    out = asyncio.run(s.qb_sales_tax_nexus("2026"))
    assert "No ship-to state" in out


def test_tool_registered():
    assert "qb_sales_tax_nexus" in s.mcp._tool_manager._tools
