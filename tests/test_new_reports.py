"""Missing-receipts report + change audit trail (CDC)."""

import asyncio

import accountingqb.server as s


def test_missing_receipts_flags_unattached_over_threshold(monkeypatch):
    async def fake_query(q, **kw):
        if "FROM Attachable" in q:
            return {"QueryResponse": {"Attachable": [
                {"AttachableRef": [{"EntityRef": {"type": "Purchase", "value": "1"}}]}]}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": [
                {"Id": "1", "TxnDate": "2026-03-01", "TotalAmt": 500.0,
                 "EntityRef": {"name": "Has Receipt"}},        # attached -> skip
                {"Id": "2", "TxnDate": "2026-03-02", "TotalAmt": 800.0,
                 "EntityRef": {"name": "No Receipt"}},          # flag
                {"Id": "3", "TxnDate": "2026-03-03", "TotalAmt": 40.0,
                 "EntityRef": {"name": "Under Threshold"}},     # below $75 -> skip
            ]}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_missing_receipts(75.0, "2026-01-01", "2026-12-31"))
    assert "No Receipt" in out and "800" in out
    assert "Has Receipt" not in out          # already attached
    assert "Under Threshold" not in out      # below threshold
    assert "1 transactions" in out


def test_missing_receipts_all_covered(monkeypatch):
    async def fake_query(q, **kw):
        if "FROM Attachable" in q:
            return {"QueryResponse": {"Attachable": [
                {"AttachableRef": [{"EntityRef": {"type": "Purchase", "value": "1"}}]}]}}
        if "FROM Purchase" in q:
            return {"QueryResponse": {"Purchase": [
                {"Id": "1", "TxnDate": "2026-03-01", "TotalAmt": 500.0,
                 "EntityRef": {"name": "X"}}]}}
        return {"QueryResponse": {}}
    monkeypatch.setattr(s, "qb_query", fake_query)
    out = asyncio.run(s.qb_missing_receipts())
    assert "Every expense" in out and "✅" in out


def test_change_audit_trail_surfaces_deleted(monkeypatch):
    cdc = {"CDCResponse": [{"QueryResponse": [
        {"Purchase": [
            {"Id": "10", "status": "Deleted"},
            {"Id": "11", "TotalAmt": 200.0, "EntityRef": {"name": "New Vendor"},
             "MetaData": {"CreateTime": "2026-03-05T10:00:00",
                          "LastUpdatedTime": "2026-03-05T10:00:00"}},
        ]},
        {"Invoice": [
            {"Id": "20", "TotalAmt": 900.0, "CustomerRef": {"name": "Acme"},
             "MetaData": {"CreateTime": "2026-01-01T00:00:00",
                          "LastUpdatedTime": "2026-03-06T09:00:00"}},
        ]},
    ]}]}

    async def fake_request(method, endpoint, **kw):
        return cdc if endpoint == "cdc" else {}
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_change_audit_trail("2026-03-01"))
    assert "Deleted 1" in out and "🗑️ Deleted" in out
    assert "New Vendor" in out       # created after since
    assert "Acme" in out             # created earlier, updated in window -> Updated


def test_new_tools_registered():
    for name in ("qb_missing_receipts", "qb_change_audit_trail"):
        assert name in s.mcp._tool_manager._tools
