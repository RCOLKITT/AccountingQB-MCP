"""get_access_token error paths: hosted no-company vs self-hosted no-creds."""

import asyncio

import pytest
import respx
from httpx import Response

import accountingqb.server as qb_server

TOKEN_URL = f"{qb_server.QB_API_URL}/api/oauth/token"


def test_hosted_mode_empty_broker_raises_no_company_message(qb_ctx, monkeypatch):
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "LK-TEST-123")
    qb_ctx.hosted_mode = True

    with respx.mock(assert_all_called=True) as router:
        router.post(TOKEN_URL).mock(return_value=Response(200, json={"companies": []}))
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(qb_server.get_access_token())

    msg = str(exc_info.value)
    assert "No QuickBooks company is connected to your AccountingQB account yet" in msg
    assert "https://accountingqb.com/dashboard" in msg
    assert "qb_refresh_connection" in msg
    # Must NOT be the self-hosted guidance
    assert "QB_CLIENT_ID" not in msg


def test_hosted_mode_404_broker_raises_no_company_message(qb_ctx, monkeypatch):
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "LK-TEST-123")
    qb_ctx.hosted_mode = True

    with respx.mock:
        respx.post(TOKEN_URL).mock(return_value=Response(404, json={"error": "not found"}))
        with pytest.raises(RuntimeError, match="No QuickBooks company is connected"):
            asyncio.run(qb_server.get_access_token())


def test_hosted_mode_lazy_fetch_returns_token(qb_ctx, monkeypatch):
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "LK-TEST-123")
    qb_ctx.hosted_mode = True

    companies = [{
        "realmId": "111222333",
        "companyName": "Acme LLC",
        "accessToken": "hosted-tok",
        "refreshToken": "hosted-rt",
        "expiresAt": "2099-01-01T00:00:00Z",
    }]
    with respx.mock:
        respx.post(TOKEN_URL).mock(return_value=Response(200, json={"companies": companies}))
        token = asyncio.run(qb_server.get_access_token())

    assert token == "hosted-tok"
    assert qb_ctx.realm_id == "111222333"
    assert qb_ctx.hosted_loaded is True
    assert qb_ctx.token_expiry.tzinfo is not None  # aware UTC — no naive compares


def test_self_hosted_without_credentials_raises_setup_message(qb_ctx, monkeypatch):
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "")
    monkeypatch.setattr(qb_server, "QB_CLIENT_ID", "")
    monkeypatch.setattr(qb_server, "QB_CLIENT_SECRET", "")
    # qb_ctx: hosted_mode False, no refresh_token

    with respx.mock:  # no routes: any network call would error loudly
        with pytest.raises(ValueError, match="Set QB_CLIENT_ID"):
            asyncio.run(qb_server.get_access_token())
