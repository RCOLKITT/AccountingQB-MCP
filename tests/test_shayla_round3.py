"""Shayla's third report (v3.28.0) — four gaps, each test reproduces the exact
incident shape. The serious one is #2: a token expiry or broker hiccup must
NEVER silently switch the active company (wrong-company-write risk)."""

import asyncio
import json

import accountingqb.server as s
from accountingqb.context import QBContext, reset_ctx, set_ctx

MHEI = {"realmId": "222", "companyName": "MHEI", "refreshToken": "rt-mhei"}
AHOUS = {"realmId": "111", "companyName": "Ahous Business", "refreshToken": "rt-ahous"}


# --- #2a: reconnect preserves the active company -----------------------------


def test_adopt_hosted_companies_preserves_active_realm():
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.realm_id = "222"  # working in MHEI
    # Broker returns Ahous FIRST — the old code reset realm to companies[0].
    s._adopt_hosted_companies(ctx, [AHOUS, MHEI])
    assert ctx.realm_id == "222"  # still MHEI
    assert ctx.refresh_token == "rt-mhei"  # and the MATCHING token


def test_adopt_hosted_companies_defaults_only_when_unset_or_stale():
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    s._adopt_hosted_companies(ctx, [AHOUS, MHEI])
    assert ctx.realm_id == "111"  # no realm set → first company (unchanged)
    ctx.realm_id = "999"  # disconnected company
    s._adopt_hosted_companies(ctx, [AHOUS, MHEI])
    assert ctx.realm_id == "111"  # stale realm → falls back, not an error


# --- #2b: failed realm lookup refuses the first-company fallback --------------


def test_failed_realm_lookup_refuses_silent_first_company(monkeypatch, respx_mock):
    import httpx as _httpx

    respx_mock.post(f"{s.QB_API_URL}/api/oauth/token").mock(
        return_value=_httpx.Response(
            200,
            json={
                "companies": [
                    {**AHOUS, "accessToken": "at", "expiresAt": None},
                    {**MHEI, "accessToken": "at2", "expiresAt": None},
                ]
            },
        )
    )
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.license_key = "LK-TEST"
    ctx.realm_id = ""  # middleware couldn't resolve…
    ctx.realm_lookup_failed = True  # …because the lookup FAILED
    token = set_ctx(ctx)
    try:
        try:
            asyncio.run(s.get_access_token())
            raise AssertionError("expected a refusal, got a token")
        except (RuntimeError, ValueError) as e:
            msg = str(e)
        assert "wrong company" in msg or "company selection is safe" in msg
        assert ctx.realm_id == ""  # did NOT silently become Ahous
    finally:
        reset_ctx(token)


def test_no_default_set_still_uses_first_company(respx_mock):
    # Legit case: lookup SUCCEEDED but no default exists (user never switched).
    import httpx as _httpx

    respx_mock.post(f"{s.QB_API_URL}/api/oauth/token").mock(
        return_value=_httpx.Response(
            200,
            json={"companies": [{**AHOUS, "accessToken": "at", "expiresAt": None}]},
        )
    )
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.license_key = "LK-TEST"
    token = set_ctx(ctx)
    try:
        tok = asyncio.run(s.get_access_token())
        assert tok == "at" and ctx.realm_id == "111"
    finally:
        reset_ctx(token)


# --- #2c: broker failure is reported as such, not as "none connected" ---------


def test_list_companies_fetch_failure_is_honest(monkeypatch):
    calls = {"n": 0}

    def failing_fetch(ctx):
        calls["n"] += 1
        return False  # broker unreachable

    monkeypatch.setattr(s, "_fetch_hosted_tokens", failing_fetch)
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    token = set_ctx(ctx)
    try:
        out = asyncio.run(s.qb_list_companies())
    finally:
        reset_ctx(token)
    assert "No QuickBooks companies connected" not in out  # the false claim
    assert "try again" in out.lower()
    assert calls["n"] == 2  # one immediate retry before giving up


def test_switch_company_fetch_failure_does_not_switch(monkeypatch):
    def failing_fetch(ctx):
        return False

    monkeypatch.setattr(s, "_fetch_hosted_tokens", failing_fetch)
    ctx = QBContext(persist_tokens=False, hosted_mode=True)
    ctx.realm_id = "222"
    token = set_ctx(ctx)
    try:
        out = asyncio.run(s.qb_switch_company("111"))
    finally:
        reset_ctx(token)
    assert "NOT performed" in out and ctx.realm_id == "222"
    assert "not found" not in out.lower()  # the old misleading message


# --- #3: apostrophes in names no longer break queries --------------------------


def test_vendor_credit_search_escapes_apostrophe(monkeypatch):
    queries = []

    async def fake_query(q, **kw):
        queries.append(q)
        return {
            "QueryResponse": {"Vendor": [{"Id": "7", "DisplayName": "Rod's Power"}]}
        }

    async def fake_query_all(q, **kw):
        queries.append(q)
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    asyncio.run(
        s.qb_list_vendor_credits(
            "2026-01-01", "2026-12-31", vendor_name="Rod's Power Marine - AA"
        )
    )
    name_queries = [q for q in queries if "Rod" in q]
    assert name_queries, "vendor lookup query not issued"
    for q in name_queries:
        assert "Rod\\'s" in q  # escaped — QueryParserError 4000 shape gone
        assert "'%Rod's" not in q  # no bare apostrophe inside the literal


def test_q_escape_is_used_across_name_lookups(monkeypatch):
    # The bug class, not the instance: a sweep of representative name-taking
    # tools must all escape. (All 41 interpolation sites were wrapped.)
    queries = []

    async def fake_query(q, **kw):
        queries.append(q)
        return {"QueryResponse": {}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_query_all", fake_query)
    name = "O'Brien & Sons"
    asyncio.run(s.qb_list_vendors(name))
    asyncio.run(s.qb_list_customers(name))
    assert len(queries) >= 2
    for q in queries:
        if "Brien" in q:
            assert "O\\'Brien" in q, q


# --- #1: account numbers --------------------------------------------------------


def test_create_sub_account_sets_acctnum(monkeypatch):
    posts = []

    async def fake_query(q, **kw):
        return {
            "QueryResponse": {
                "Account": [
                    {
                        "Id": "50",
                        "Name": "Supplies",
                        "AccountType": "Expense",
                        "AccountSubType": "SuppliesMaterials",
                    }
                ]
            }
        }

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append(json_body)
        return {
            "Account": {
                "Id": "88",
                "Name": json_body["Name"],
                "AcctNum": json_body.get("AcctNum"),
                "FullyQualifiedName": f"Supplies:{json_body['Name']}",
            }
        }

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_create_sub_account(
            "Supplies - Tours & activities",
            "Supplies",
            account_number="6245",
        )
    )
    assert "✅" in out
    assert posts[0]["AcctNum"] == "6245"  # the field that had to be hand-typed


def test_update_account_adds_number_sparse(monkeypatch):
    posts = []

    async def fake_resolve(name, **kw):
        return {"Id": "88", "Name": "Guest amenities - rooms", "SyncToken": "3"}, None

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append((endpoint, json_body))
        return {
            "Account": {
                "Id": "88",
                "Name": json_body["Name"],
                "AcctNum": json_body.get("AcctNum"),
                "FullyQualifiedName": json_body["Name"],
            }
        }

    monkeypatch.setattr(s, "_resolve_account", fake_resolve)
    monkeypatch.setattr(s, "qb_request", fake_request)
    out = asyncio.run(
        s.qb_update_account("Guest amenities - rooms", account_number="6110")
    )
    assert "✅" in out and "6110" in out
    endpoint, body = posts[0]
    assert endpoint == "account"
    # Sparse update: Id + SyncToken preserved, name kept, ONLY AcctNum added.
    assert body["Id"] == "88" and body["SyncToken"] == "3" and body["sparse"] is True
    assert body["Name"] == "Guest amenities - rooms"
    assert body["AcctNum"] == "6110"


def test_update_account_requires_a_change():
    out = asyncio.run(s.qb_update_account("Anything"))
    assert "Nothing to change" in out


# --- #4: reclassify a single line ------------------------------------------------


def _bill_22_lines():
    return {
        "Id": "500",
        "SyncToken": "1",
        "Line": [
            {
                "Amount": 10.0 + i,
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": "1", "name": "Old Account"}
                },
            }
            for i in range(22)
        ],
    }


def _wire_reclassify(monkeypatch, posts):
    async def fake_query(q, **kw):
        return {
            "QueryResponse": {"Account": [{"Id": "9", "Name": "Repairs & Maintenance"}]}
        }

    async def fake_read(entity, entity_id):
        return {"Bill": _bill_22_lines()}

    async def fake_request(method, endpoint, json_body=None, **kw):
        posts.append(json_body)
        return {"Bill": {"Id": "500", "SyncToken": "2"}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)


def test_reclassify_single_line_touches_only_that_line(monkeypatch):
    posts = []
    _wire_reclassify(monkeypatch, posts)
    out = asyncio.run(
        s.qb_reclassify_transaction(
            "Bill", "500", "Repairs & Maintenance", line_number=7
        )
    )
    assert "line 7" in out
    body = posts[0]
    names = [
        l["AccountBasedExpenseLineDetail"]["AccountRef"]["name"] for l in body["Line"]
    ]
    assert names[6] == "Repairs & Maintenance"  # the one targeted line
    assert names.count("Old Account") == 21  # the other 21 untouched


def test_reclassify_default_still_moves_all_lines(monkeypatch):
    posts = []
    _wire_reclassify(monkeypatch, posts)
    out = asyncio.run(
        s.qb_reclassify_transaction("Bill", "500", "Repairs & Maintenance")
    )
    assert "22 line(s)" in out
    names = {
        l["AccountBasedExpenseLineDetail"]["AccountRef"]["name"]
        for l in posts[0]["Line"]
    }
    assert names == {"Repairs & Maintenance"}


def test_reclassify_line_number_out_of_range(monkeypatch):
    posts = []
    _wire_reclassify(monkeypatch, posts)
    out = asyncio.run(
        s.qb_reclassify_transaction(
            "Bill", "500", "Repairs & Maintenance", line_number=23
        )
    )
    assert "out of range" in out and posts == []  # nothing written
