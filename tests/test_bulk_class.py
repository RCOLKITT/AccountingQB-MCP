"""qb_bulk_set_class (bulk class reclassification, preview-first) and the
qb_general_ledger class filter. Constitution 'Writes Are Sacred': the bulk tool
must preview by default (write nothing), report per-item success/failure when
applying, cap per call, and say exactly how many remain."""

import asyncio

import accountingqb.server as s

CLASS_A = "Ahous Adventures"
CLASS_B = "Wahous Wilderness Lodge"
IDS = {CLASS_A: "9", CLASS_B: "8"}


async def _resolve_class_stub(class_name="", class_id=""):
    if not class_name and not class_id:
        return None, None
    if class_name not in IDS:
        return None, f"Class '{class_name}' not found. Run qb_list_classes."
    return {"value": IDS[class_name], "name": class_name}, None


def _bill(bill_id, cls_value, cls_name):
    detail = {"AccountRef": {"value": "1650", "name": "WIP"}}
    if cls_value:
        detail["ClassRef"] = {"value": cls_value, "name": cls_name}
    return {
        "Id": bill_id,
        "TxnDate": "2026-07-15",
        "DocNumber": bill_id,
        "TotalAmt": 100.0,
        "VendorRef": {"name": "Acme"},
        "Line": [
            {
                "Amount": 100.0,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": detail,
            }
        ],
    }


def _wire(monkeypatch, bills, posts):
    async def fake_query_all(query, **kw):
        if "FROM Bill " in query:
            return {"QueryResponse": {"Bill": bills}}
        return {"QueryResponse": {}}

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append((endpoint, json_body))
        return {endpoint.capitalize(): {"Id": json_body.get("Id")}}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "qb_request", fake_request)


# --- preview (default) -------------------------------------------------------


def test_bulk_preview_writes_nothing(monkeypatch):
    posts = []
    bills = [_bill("1", "", ""), _bill("2", IDS[CLASS_A], CLASS_A)]
    _wire(monkeypatch, bills, posts)
    out = asyncio.run(
        s.qb_bulk_set_class("Not Specified", CLASS_B, "2026-07-01", "2026-08-31")
    )
    assert "PREVIEW" in out and "nothing changed" in out.lower()
    assert posts == []  # Constitution: preview writes nothing
    # Only the UNclassed bill (#1) matches the Not Specified filter.
    assert "| Bill | 1 |" in out and "| Bill | 2 |" not in out


def test_bulk_unclassed_sentinel_variants(monkeypatch):
    posts = []
    bills = [_bill("1", "", "")]
    _wire(monkeypatch, bills, posts)
    for sentinel in ("Not Specified", "unclassed", "NOT SPECIFIED"):
        out = asyncio.run(
            s.qb_bulk_set_class(sentinel, CLASS_B, "2026-07-01", "2026-08-31")
        )
        assert "1 transaction(s) would be updated" in out


# --- apply -------------------------------------------------------------------


def test_bulk_apply_retags_only_matching_lines(monkeypatch):
    posts = []
    bills = [
        _bill("1", IDS[CLASS_A], CLASS_A),  # matches from_class A
        _bill("2", IDS[CLASS_B], CLASS_B),  # already B — untouched
        _bill("3", "", ""),  # unclassed — untouched (from_class is A)
    ]
    _wire(monkeypatch, bills, posts)
    out = asyncio.run(
        s.qb_bulk_set_class(CLASS_A, CLASS_B, "2026-07-01", "2026-08-31", confirm=True)
    )
    assert len(posts) == 1  # only bill #1 written
    endpoint, body = posts[0]
    assert endpoint == "bill" and body["Id"] == "1"
    assert body["Line"][0]["AccountBasedExpenseLineDetail"]["ClassRef"] == {
        "value": IDS[CLASS_B],
        "name": CLASS_B,
    }
    assert "Applied: 1" in out and "Failed: 0" in out


def test_bulk_apply_cap_reports_remaining(monkeypatch):
    posts = []
    bills = [_bill(str(i), IDS[CLASS_A], CLASS_A) for i in range(1, 31)]  # 30 matches
    _wire(monkeypatch, bills, posts)
    out = asyncio.run(
        s.qb_bulk_set_class(
            CLASS_A,
            CLASS_B,
            "2026-07-01",
            "2026-08-31",
            confirm=True,
            max_transactions=25,
        )
    )
    assert len(posts) == 25  # capped
    assert "Applied: 25" in out and "Remaining: 5" in out
    assert "run the same call again" in out


def test_bulk_apply_reports_per_item_failure(monkeypatch):
    posts = []
    bills = [_bill("1", IDS[CLASS_A], CLASS_A), _bill("2", IDS[CLASS_A], CLASS_A)]

    async def fake_query_all(query, **kw):
        if "FROM Bill " in query:
            return {"QueryResponse": {"Bill": bills}}
        return {"QueryResponse": {}}

    async def flaky_request(method, endpoint, json_body=None, **kw):
        if json_body.get("Id") == "2":
            raise RuntimeError("QBO 500")
        posts.append(json_body["Id"])
        return {"Bill": {"Id": json_body["Id"]}}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "qb_request", flaky_request)
    out = asyncio.run(
        s.qb_bulk_set_class(CLASS_A, CLASS_B, "2026-07-01", "2026-08-31", confirm=True)
    )
    # Per-item reporting: the success AND the failure are both named.
    assert "Applied: 1" in out and "Failed: 1" in out
    assert "✅ Bill #1" in out and "❌ Bill #2" in out


def test_bulk_same_class_refused(monkeypatch):
    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    out = asyncio.run(s.qb_bulk_set_class(CLASS_A, CLASS_A, "2026-07-01", "2026-08-31"))
    assert "same class" in out


# --- qb_general_ledger class filter ------------------------------------------


def test_general_ledger_passes_classid(monkeypatch):
    captured = {}

    async def fake_request(method, endpoint, **kw):
        captured["params"] = kw.get("params", {})
        return {"Header": {}, "Rows": {"Row": []}}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_general_ledger("2026-01-01", "2026-12-31", class_name=CLASS_A)
    )
    assert captured["params"]["classid"] == IDS[CLASS_A]
    assert f"Class: {CLASS_A}" in out


def test_general_ledger_unknown_class_errors_before_request(monkeypatch):
    called = {}

    async def fake_request(method, endpoint, **kw):
        called["yes"] = True
        return {}

    monkeypatch.setattr(s, "_resolve_class", _resolve_class_stub)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_general_ledger("2026-01-01", "2026-12-31", class_name="Ghost")
    )
    assert "not found" in out and "yes" not in called
