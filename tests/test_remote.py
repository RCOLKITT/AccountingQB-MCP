"""Unit tests for the remote MCP service's auth middleware (Phase 6).

BearerAuthMiddleware is tested in isolation around a trivial downstream ASGI
app — the real streamable-HTTP MCP app is not wired in, so these tests do not
depend on accountingqb.server internals (conftest.py imports it for sys.path
setup, but nothing here calls into it).
"""

import json
import time

import jwt as pyjwt
import pytest
from starlette.testclient import TestClient

from accountingqb.context import get_ctx
from accountingqb.remote import PROTECTED_RESOURCE_PATH, BearerAuthMiddleware

SECRET = "test-secret"
RESOURCE = "https://mcp.accountingqb.com"
AS_URL = "https://accountingqb.com"


async def echo_ctx_app(scope, receive, send):
    """Downstream stand-in for the MCP app: echoes the current QBContext."""
    assert scope["type"] == "http"
    ctx = get_ctx()
    body = json.dumps(
        {
            "license_key": getattr(ctx, "license_key", None),
            "realm_id": ctx.realm_id,
            "hosted_mode": ctx.hosted_mode,
            "persist_tokens": ctx.persist_tokens,
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def stub_realm_resolver(license_key: str):
    return "REALM-" + license_key


def make_app(realm_resolver=stub_realm_resolver, secret=SECRET):
    return BearerAuthMiddleware(
        echo_ctx_app,
        jwt_secret=secret,
        resource_url=RESOURCE,
        auth_server_url=AS_URL,
        realm_resolver=realm_resolver,
        version="9.9.9",
        tool_count=135,
    )


def make_token(
    license_key="LK-TEST-1234",
    aud=RESOURCE,
    exp_delta=900,
    secret=SECRET,
    **extra,
):
    claims = {
        "license_key": license_key,
        "sub": "user_123",
        "aud": aud,
        "exp": int(time.time()) + exp_delta,
        **extra,
    }
    return pyjwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def client():
    return TestClient(make_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_version_endpoint_public(client):
    # Unauthenticated deploy-verification endpoint used by scripts/deploy-smoke.py.
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "9.9.9"
    assert data["tools"] == 135
    assert "hosted connector" in data["deployment"]


def test_tax_data_endpoint_public():
    # Public tax-data provenance — no auth, cacheable, statutory facts only.
    app = BearerAuthMiddleware(
        echo_ctx_app,
        jwt_secret=SECRET,
        resource_url=RESOURCE,
        auth_server_url=AS_URL,
        realm_resolver=stub_realm_resolver,
        tax_data={
            "version": "2026.6",
            "verified": "2026-08-03",
            "highlights": [
                {
                    "label": "Business meals — 50% deductible",
                    "source": "IRC §274(n)",
                    "jurisdiction": "US",
                }
            ],
            "ledger": {"chain_ok": True},
        },
    )
    resp = TestClient(app).get("/tax-data")
    assert resp.status_code == 200
    assert "public" in (resp.headers.get("cache-control") or "")
    data = resp.json()
    assert data["version"] == "2026.6"
    assert data["ledger"]["chain_ok"] is True
    assert data["highlights"][0]["source"] == "IRC §274(n)"


def test_protected_resource_metadata(client):
    resp = client.get(PROTECTED_RESOURCE_PATH)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "resource": RESOURCE,
        "authorization_servers": [AS_URL],
        "bearer_methods_supported": ["header"],
    }


# ---------------------------------------------------------------------------
# Auth failures → 401 + WWW-Authenticate challenge
# ---------------------------------------------------------------------------
def assert_401_with_challenge(resp):
    assert resp.status_code == 401
    challenge = resp.headers.get("www-authenticate", "")
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="{RESOURCE}{PROTECTED_RESOURCE_PATH}"' in challenge
    assert resp.json()["error"] == "invalid_token"


def test_missing_token(client):
    assert_401_with_challenge(client.post("/mcp"))


def test_malformed_authorization_header(client):
    resp = client.post("/mcp", headers={"Authorization": "Basic abc123"})
    assert_401_with_challenge(resp)


def test_expired_token(client):
    token = make_token(exp_delta=-60)
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert_401_with_challenge(resp)
    assert "expired" in resp.json()["error_description"].lower()


def test_wrong_audience(client):
    token = make_token(aud="https://evil.example.com")
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert_401_with_challenge(resp)
    assert "audience" in resp.json()["error_description"].lower()


def test_wrong_signature(client):
    token = make_token(secret="some-other-secret")
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert_401_with_challenge(resp)


def test_missing_license_key_claim(client):
    claims = {"sub": "u", "aud": RESOURCE, "exp": int(time.time()) + 900}
    token = pyjwt.encode(claims, SECRET, algorithm="HS256")
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert_401_with_challenge(resp)


def test_unconfigured_secret_fails_closed():
    client = TestClient(make_app(secret=""))
    token = make_token()  # even a validly-formed token is rejected
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert_401_with_challenge(resp)


# ---------------------------------------------------------------------------
# Auth success → downstream reached with a per-request QBContext
# ---------------------------------------------------------------------------
def test_valid_token_reaches_downstream_with_ctx(client):
    token = make_token(license_key="LK-ABC")
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["license_key"] == "LK-ABC"
    assert data["realm_id"] == "REALM-LK-ABC"  # from stub_realm_resolver
    assert data["hosted_mode"] is True
    assert data["persist_tokens"] is False


def test_realm_resolver_failure_is_non_fatal():
    async def broken_resolver(license_key):
        raise RuntimeError("broker down")

    client = TestClient(make_app(realm_resolver=broken_resolver))
    token = make_token()
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["realm_id"] == ""  # falls back to first company


def test_no_realm_resolver():
    client = TestClient(make_app(realm_resolver=None))
    token = make_token()
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["realm_id"] == ""


def test_ctx_reset_after_request(client):
    """The default (test-scrubbed) context is restored once a request ends."""
    token = make_token(license_key="LK-RESET")
    client.post("/mcp", headers={"Authorization": f"Bearer {token}"})
    ctx = get_ctx()
    assert getattr(ctx, "license_key", None) != "LK-RESET"


# ---------------------------------------------------------------------------
# 2026-07-28 spec adoption (edge layer)
# ---------------------------------------------------------------------------
from accountingqb.remote import (  # noqa: E402
    MCP_CAPABILITIES_PATH,
    SPEC_PROTOCOL_VERSION,
    TOOLS_LIST_TTL_MS,
)


async def tools_list_app(scope, receive, send):
    """Downstream stand-in that returns a JSON-RPC tools/list result."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "qb_profit_loss"}]}}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _authed_app(downstream):
    return BearerAuthMiddleware(
        downstream,
        jwt_secret=SECRET,
        resource_url=RESOURCE,
        auth_server_url=AS_URL,
        realm_resolver=stub_realm_resolver,
    )


def test_capabilities_endpoint_advertises_2026_spec():
    client = TestClient(_authed_app(echo_ctx_app))
    r = client.get(MCP_CAPABILITIES_PATH)  # public, no auth
    assert r.status_code == 200
    data = r.json()
    assert "2026-07-28" in data["protocolVersions"]
    assert data["deprecatedFeaturesUsed"] == []  # our selling point
    assert data["transport"]["stateless"] is True
    assert data["cacheable"]["tools/list"]["cacheScope"] == "public"


def test_tools_list_response_gets_cache_hints_and_version_header():
    client = TestClient(_authed_app(tools_list_app))
    token = make_token()
    r = client.post("/mcp", headers={"Authorization": f"Bearer {token}"}, json={})
    assert r.status_code == 200
    assert r.headers.get("mcp-protocol-version") == SPEC_PROTOCOL_VERSION
    result = r.json()["result"]
    assert result["ttlMs"] == TOOLS_LIST_TTL_MS
    assert result["cacheScope"] == "public"
    assert result["tools"][0]["name"] == "qb_profit_loss"  # original preserved


def test_non_tools_response_untouched_but_versioned():
    client = TestClient(_authed_app(echo_ctx_app))
    token = make_token()
    r = client.post("/mcp", headers={"Authorization": f"Bearer {token}"}, json={})
    assert r.headers.get("mcp-protocol-version") == SPEC_PROTOCOL_VERSION
    assert "ttlMs" not in r.text and "cacheScope" not in r.text
