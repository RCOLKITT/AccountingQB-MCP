"""User incident (v3.31.0): parallel bulk-recode batch — three fixes.

1. Broker 429s surfaced as "QuickBooks connection expired" (~1 in 10 parallel
   calls) — actually the broker's per-IP token rate limit. Now: shared
   per-license token cache + single-flight collapse the stampede, 429 waits out
   Retry-After, and an exhausted retry says "rate-limited, retry" — never
   "reconnect".
2. Capped list displays were an arbitrary Id-ordered slice — now newest-first
   by date with an offset parameter for paging.
3. 130 single reclassify calls = 130 client approvals — qb_bulk_reclassify
   recodes a whole batch in one call.

All fixtures fictional.
"""

import asyncio
import inspect

import accountingqb.server as s
import httpx
import pytest
import respx

# ---------------------------------------------------------------------------
# 1. token stampede / 429 honesty
# ---------------------------------------------------------------------------


def _fresh_ctx(license_key="LK-TEST-FICTIONAL"):
    ctx = s.QBContext()
    ctx.hosted_mode = True
    ctx.license_key = license_key
    ctx.realm_id = "1111111111"
    ctx.persist_tokens = False
    return ctx


COMPANIES = [
    {
        "realmId": "1111111111",
        "companyName": "Fictional Co",
        "accessToken": "at-1",
        "refreshToken": "rt-1",
        "expiresAt": "2099-01-01T00:00:00Z",
    }
]


@pytest.fixture(autouse=True)
def _clear_token_cache():
    s._HOSTED_TOKEN_CACHE.clear()
    s._HOSTED_TOKEN_LOCKS.clear()
    yield
    s._HOSTED_TOKEN_CACHE.clear()
    s._HOSTED_TOKEN_LOCKS.clear()


@respx.mock
def test_parallel_calls_make_one_broker_request():
    route = respx.post(f"{s.QB_API_URL}/api/oauth/token").mock(
        return_value=httpx.Response(200, json={"companies": COMPANIES})
    )

    async def run():
        async def one():
            ctx = _fresh_ctx()
            tok = s.ctx_var.set(ctx) if hasattr(s, "ctx_var") else None
            try:
                monkey_ctx = ctx

                # call get_access_token with this ctx active
                orig = s.get_ctx
                s.get_ctx = lambda: monkey_ctx
                try:
                    return await s.get_access_token()
                finally:
                    s.get_ctx = orig
            finally:
                if tok:
                    s.ctx_var.reset(tok)

        return await asyncio.gather(*[one() for _ in range(10)])

    results = asyncio.run(run())
    assert all(r == "at-1" for r in results)
    # single-flight + shared cache: 10 parallel calls, ONE broker POST
    assert route.call_count == 1


@respx.mock
def test_double_429_says_rate_limited_not_expired():
    respx.post(f"{s.QB_API_URL}/api/oauth/token").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0.5"})
    )

    async def run():
        ctx = _fresh_ctx("LK-TEST-FICTIONAL-429")
        orig = s.get_ctx
        s.get_ctx = lambda: ctx
        try:
            await s.get_access_token()
        finally:
            s.get_ctx = orig

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(run())
    msg = str(exc.value)
    assert "rate-limited" in msg and "retry" in msg.lower()
    assert "expired" not in msg.lower()  # the old lie
    assert "reconnect" not in msg.lower()


# ---------------------------------------------------------------------------
# 2. date sort + offset
# ---------------------------------------------------------------------------


def test_page_window_sorts_newest_first_and_pages():
    rows = [
        {"Id": "15050", "TxnDate": "2026-04-29"},
        {"Id": "19893", "TxnDate": "2026-11-10"},
        {"Id": "17000", "TxnDate": "2026-07-01"},
        {"Id": "17001", "TxnDate": "2026-07-01"},
    ]
    shown, note = s._page_window(rows, 2, 0)
    assert [r["Id"] for r in shown] == ["19893", "17001"]  # newest first, Id tiebreak
    assert "showing 1–2 of 4, newest first" in note
    assert "pass offset=2 for the next page" in note

    page2, note2 = s._page_window(rows, 2, 2)
    assert [r["Id"] for r in page2] == ["17000", "15050"]
    assert "showing 3–4 of 4" in note2
    assert "next page" not in note2  # last page

    everything, no_note = s._page_window(rows, 500, 0)
    assert len(everything) == 4 and no_note == ""


def test_all_dated_list_tools_take_offset():
    for name in (
        "qb_list_bills",
        "qb_list_bill_payments",
        "qb_list_payments",
        "qb_list_deposits",
        "qb_list_transfers",
        "qb_list_journal_entries",
        "qb_list_sales_receipts",
        "qb_list_credit_memos",
        "qb_list_vendor_credits",
        "qb_list_estimates",
    ):
        fn = getattr(s, name)
        fn = getattr(fn, "__wrapped__", fn)
        params = inspect.signature(fn).parameters
        assert "offset" in params, name
        assert "_page_window(" in inspect.getsource(fn), name


# ---------------------------------------------------------------------------
# 3. bulk reclassify
# ---------------------------------------------------------------------------


def test_bulk_reclassify_continues_past_failures(monkeypatch):
    async def fake_query(query, **kw):
        return {
            "QueryResponse": {
                "Account": [{"Id": "77", "Name": "Software subscriptions"}]
            }
        }

    async def fake_read(entity, tid):
        if tid == "205":
            return {}  # not found → per-ID failure, batch continues
        return {
            "Purchase": {
                "Id": tid,
                "SyncToken": "0",
                "Line": [
                    {
                        "DetailType": "AccountBasedExpenseLineDetail",
                        "Amount": 10.0,
                        "AccountBasedExpenseLineDetail": {
                            "AccountRef": {"value": "1", "name": "Uncategorized"}
                        },
                    }
                ],
            }
        }

    async def fake_request(method, entity, json_body=None, **kw):
        return {"Purchase": {"Id": json_body["Id"], "SyncToken": "1"}}

    monkeypatch.setattr(s, "qb_query", fake_query)
    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)

    out = asyncio.run(s.qb_bulk_reclassify("101, 205, 318", "Software subscriptions"))
    assert "✅ 2 reclassified to Software subscriptions" in out
    assert "❌ 1 failed" in out and "#205" in out
    assert "101" in out and "318" in out


def test_bulk_reclassify_caps_batch_size():
    ids = ",".join(str(i) for i in range(201))
    out = asyncio.run(s.qb_bulk_reclassify(ids, "Software subscriptions"))
    assert "limit of 200" in out
