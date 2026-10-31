"""qb_enable_class_tracking + qb_create_class — the class-administration write
tools (built so a company can be made class-capable through the product; also
what upgrades the contract-canary realm to full class assertions)."""

import asyncio

import accountingqb.server as s


def _wire(monkeypatch, prefs, posts, post_result=None):
    async def fake_request(method, endpoint, json_body=None, **kw):
        if method == "GET" and endpoint == "preferences":
            return {"Preferences": prefs}
        posts.append((method, endpoint, json_body))
        return post_result or {}

    monkeypatch.setattr(s, "qb_request", fake_request)


# --- qb_enable_class_tracking -------------------------------------------------


def test_enable_class_tracking_sparse_update(monkeypatch):
    posts = []
    prefs = {"Id": "1", "SyncToken": "7", "AccountingInfoPrefs": {}}
    _wire(
        monkeypatch,
        prefs,
        posts,
        post_result={
            "Preferences": {"AccountingInfoPrefs": {"ClassTrackingPerTxnLine": True}}
        },
    )
    out = asyncio.run(s.qb_enable_class_tracking())
    assert "✅" in out and "ON" in out
    assert len(posts) == 1
    method, endpoint, body = posts[0]
    assert (method, endpoint) == ("POST", "preferences")
    # Read-modify-write: Id + SyncToken preserved, sparse, per-LINE tracking.
    assert body["Id"] == "1" and body["SyncToken"] == "7" and body["sparse"] is True
    assert body["AccountingInfoPrefs"] == {"ClassTrackingPerTxnLine": True}


def test_enable_class_tracking_already_on_writes_nothing(monkeypatch):
    posts = []
    prefs = {
        "Id": "1",
        "SyncToken": "7",
        "AccountingInfoPrefs": {"ClassTrackingPerTxnLine": True},
    }
    _wire(monkeypatch, prefs, posts)
    out = asyncio.run(s.qb_enable_class_tracking())
    assert "already ON" in out
    assert posts == []  # idempotent — no write when nothing to change


def test_enable_class_tracking_reports_refusal_honestly(monkeypatch):
    prefs = {"Id": "1", "SyncToken": "7", "AccountingInfoPrefs": {}}

    async def fake_request(method, endpoint, json_body=None, **kw):
        if method == "GET":
            return {"Preferences": prefs}
        raise RuntimeError("Business Validation Error: plan does not support")

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_enable_class_tracking())
    assert "refused" in out and "Plus or Advanced" in out


def test_enable_class_tracking_verifies_result(monkeypatch):
    # QBO can accept the POST but not actually flip the flag (plan limits) —
    # the tool must verify the response instead of declaring success.
    posts = []
    prefs = {"Id": "1", "SyncToken": "7", "AccountingInfoPrefs": {}}
    _wire(
        monkeypatch,
        prefs,
        posts,
        post_result={"Preferences": {"AccountingInfoPrefs": {}}},
    )
    out = asyncio.run(s.qb_enable_class_tracking())
    assert "does not read as enabled" in out
    assert "✅" not in out


# --- qb_create_class ----------------------------------------------------------


def test_create_class_posts_name(monkeypatch):
    posts = []

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append((method, endpoint, json_body))
        return {"Class": {"Id": "42", "Name": "Canary", "FullyQualifiedName": "Canary"}}

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_create_class("Canary"))
    assert "✅" in out and "Canary" in out and "42" in out
    assert posts == [("POST", "class", {"Name": "Canary"})]


def test_create_subclass_resolves_parent(monkeypatch):
    posts = []

    async def fake_resolve(class_name="", class_id=""):
        assert class_name == "Programs"
        return {"value": "9", "name": "Programs"}, None

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append(json_body)
        return {
            "Class": {
                "Id": "43",
                "Name": "Outreach",
                "FullyQualifiedName": "Programs:Outreach",
            }
        }

    monkeypatch.setattr(s, "_resolve_class", fake_resolve)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_create_class("Outreach", parent_name="Programs"))
    assert "Programs:Outreach" in out
    assert posts[0] == {
        "Name": "Outreach",
        "SubClass": True,
        "ParentRef": {"value": "9"},
    }


def test_create_class_duplicate_reported(monkeypatch):
    async def fake_request(method, endpoint, json_body=None, **kw):
        raise RuntimeError("Duplicate Name Exists Error")

    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(s.qb_create_class("Canary"))
    assert "refused" in out and "already exists" in out


def test_create_class_requires_name(monkeypatch):
    out = asyncio.run(s.qb_create_class("   "))
    assert "name is required" in out
