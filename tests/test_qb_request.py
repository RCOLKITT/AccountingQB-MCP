"""qb_request behavior: 401 retry, 429 friendliness, QBO Fault parsing."""

import asyncio
from datetime import timedelta

import pytest
import respx
from httpx import Response

import accountingqb.server as qb_server

REALM = "9130350000000000"
QUERY_URL = f"{qb_server.BASE_URL}/v3/company/{REALM}/query"


def _prime_ctx(ctx, token="tok-1"):
    ctx.realm_id = REALM
    ctx.access_token = token
    ctx.token_expiry = qb_server._utcnow() + timedelta(hours=1)
    ctx.refresh_token = "rt-1"


def test_401_then_200_retries_with_fresh_token(qb_ctx, monkeypatch):
    _prime_ctx(qb_ctx)
    # Self-hosted refresh needs client credentials
    monkeypatch.setattr(qb_server, "QB_CLIENT_ID", "cid")
    monkeypatch.setattr(qb_server, "QB_CLIENT_SECRET", "csecret")

    with respx.mock(assert_all_called=True) as router:
        api = router.get(QUERY_URL).mock(
            side_effect=[
                Response(401, json={"Fault": {"Error": [{"Message": "expired"}]}}),
                Response(
                    200, json={"QueryResponse": {"CompanyInfo": [{"CompanyName": "X"}]}}
                ),
            ]
        )
        router.post(qb_server.AUTH_URL).mock(
            return_value=Response(
                200, json={"access_token": "tok-2", "expires_in": 3600}
            )
        )

        result = asyncio.run(
            qb_server.qb_request("GET", "query", params={"query": "SELECT *"})
        )

    assert result == {"QueryResponse": {"CompanyInfo": [{"CompanyName": "X"}]}}
    # Second attempt must carry the refreshed token
    assert api.calls[1].request.headers["Authorization"] == "Bearer tok-2"
    assert qb_ctx.access_token == "tok-2"


def test_429_raises_friendly_rate_limit_error(qb_ctx):
    _prime_ctx(qb_ctx)
    with respx.mock:
        respx.get(QUERY_URL).mock(return_value=Response(429, json={}))
        with pytest.raises(RuntimeError, match="rate limit reached"):
            asyncio.run(
                qb_server.qb_request("GET", "query", params={"query": "SELECT *"})
            )


def test_400_fault_raises_runtime_error_with_code_and_message(qb_ctx):
    _prime_ctx(qb_ctx)
    fault = {
        "Fault": {
            "type": "ValidationFault",
            "Error": [
                {
                    "code": "2010",
                    "Message": "Invalid Reference Id",
                    "Detail": "Invalid Reference Id : Accounts element id 999 not found",
                }
            ],
        },
        "time": "2026-07-09T00:00:00Z",
    }
    with respx.mock:
        respx.get(QUERY_URL).mock(return_value=Response(400, json=fault))
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(
                qb_server.qb_request("GET", "query", params={"query": "SELECT *"})
            )

    msg = str(exc_info.value)
    assert "QuickBooks error 2010" in msg
    assert "Invalid Reference Id" in msg
    assert "Accounts element id 999 not found" in msg


def test_6000_gst_hst_fault_includes_tax_code_guidance(qb_ctx):
    _prime_ctx(qb_ctx)
    fault = {
        "Fault": {
            "type": "SystemFault",
            "Error": [
                {
                    "code": "6000",
                    "Message": "A business validation error has occurred while processing your request",
                    "Detail": "Business Validation Error: When you use a GST/HST rate, "
                    "you need to choose a sales tax code for each line item.",
                }
            ],
        },
    }
    with respx.mock:
        respx.post(f"{qb_server.BASE_URL}/v3/company/{REALM}/invoice").mock(
            return_value=Response(400, json=fault)
        )
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(qb_server.qb_request("POST", "invoice", json_body={"Line": []}))

    msg = str(exc_info.value)
    assert "QuickBooks error 6000" in msg
    assert "qb_list_tax_codes" in msg
    assert "pass tax_code to the create tool" in msg


def test_non_fault_400_still_raises_http_error(qb_ctx):
    _prime_ctx(qb_ctx)
    import httpx

    with respx.mock:
        respx.get(QUERY_URL).mock(return_value=Response(400, text="not json"))
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(
                qb_server.qb_request("GET", "query", params={"query": "SELECT *"})
            )
