"""Fixed-asset register: pair Accumulated Depreciation contra accounts to cost
accounts; land is not depreciable; cost = net + accumulated."""

import asyncio

import accountingqb.server as s


def _patch(monkeypatch, accounts):
    async def fake_query(q, **kw):
        if "AccountType IN ('Fixed Asset'" in q:
            return {"QueryResponse": {"Account": accounts}}
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


def test_register_pairs_contra_and_excludes_land(monkeypatch):
    _patch(
        monkeypatch,
        [
            {
                "Name": "Furniture & Fixtures",
                "CurrentBalance": 2526.0,
                "AccountType": "Fixed Asset",
            },
            {
                "Name": "Accumulated Depreciation - Furniture",
                "CurrentBalance": -2555.0,
                "AccountType": "Fixed Asset",
            },
            {
                "Name": "Computers",
                "CurrentBalance": 3000.0,
                "AccountType": "Fixed Asset",
            },
            {"Name": "Land", "CurrentBalance": 50000.0, "AccountType": "Fixed Asset"},
        ],
    )
    out = asyncio.run(s.qb_depreciation_schedule("2025"))
    # Furniture: cost = net 2526 + accum 2555 = 5081
    assert "Furniture & Fixtures | $5,081.00 | $2,555.00 | $2,526.00" in out
    # Land is not depreciable and contributes $0 to the estimate
    assert "Land | $50,000.00 | Not depreciable" in out
    # honest caveat about QBO not exposing in-service dates
    assert "acquisition / in-service dates" in out
    # register framing
    assert "Fixed-Asset Register" in out
