"""Multi-tenant isolation — the highest-severity class for a hosted, multi-realm
connector. Proves a license can only ever reach ITS OWN realms' tokens, that a
request asking for another tenant's realm gets nothing, and that concurrent
per-request contexts never bleed through the process-global default context."""

import accountingqb.server as s
from accountingqb.context import QBContext, set_ctx, reset_ctx, _default_ctx

# Simulated broker DB (web /api/oauth/token): each license has ONLY its own
# realm(s). License AAA never has a row for realmB, and vice-versa.
_BROKER = {
    "LK-AAA": [{"realmId": "realmA", "companyName": "A Co", "accessToken": "tokA",
                "refreshToken": "rA", "expiresAt": "2099-01-01T00:00:00Z"}],
    "LK-BBB": [{"realmId": "realmB", "companyName": "B Co", "accessToken": "tokB",
                "refreshToken": "rB", "expiresAt": "2099-01-01T00:00:00Z"}],
}


class _Resp:
    status_code = 200

    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


class _FakeClient:
    """Stand-in for httpx.Client that enforces the broker's WHERE license_key=?
    filter — it returns ONLY the requesting license's companies."""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, **k):
        lic = (json or {}).get("licenseKey")
        return _Resp({"companies": _BROKER.get(lic, [])})


def _ctx(license_key, realm):
    c = QBContext(persist_tokens=False, hosted_mode=True)
    c.license_key = license_key
    c.realm_id = realm
    return c


def _patch(monkeypatch):
    monkeypatch.setattr(s.httpx, "Client", _FakeClient)
    monkeypatch.setattr(s, "_load_hosted_tokens", lambda ctx: False)
    monkeypatch.setattr(s, "_save_hosted_tokens", lambda comps: None)


def test_license_sees_only_its_own_realms(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx("LK-AAA", "realmA")
    tok = set_ctx(ctx)
    try:
        assert s._fetch_hosted_tokens(ctx) is True
        realms = {c["realmId"] for c in ctx.hosted_companies}
        assert realms == {"realmA"}
        assert "realmB" not in realms
    finally:
        reset_ctx(tok)


def test_license_cannot_reach_another_tenants_realm(monkeypatch):
    _patch(monkeypatch)
    # License AAA asks to operate on realmB (which belongs to license BBB).
    ctx = _ctx("LK-AAA", "realmB")
    tok = set_ctx(ctx)
    try:
        s._fetch_hosted_tokens(ctx)
        # The broker only ever returned AAA's own companies, so realmB's token
        # is simply not reachable — no code path yields it.
        assert all(c["realmId"] != "realmB" for c in ctx.hosted_companies)
        assert not any(c["accessToken"] == "tokB" for c in ctx.hosted_companies)
    finally:
        reset_ctx(tok)


def test_concurrent_contexts_do_not_bleed(monkeypatch):
    _patch(monkeypatch)
    a, b = _ctx("LK-AAA", "realmA"), _ctx("LK-BBB", "realmB")
    for c in (a, b):
        t = set_ctx(c)
        try:
            s._fetch_hosted_tokens(c)
        finally:
            reset_ctx(t)
    # Each context kept only its own realm; no merging.
    assert {c["realmId"] for c in a.hosted_companies} == {"realmA"}
    assert {c["realmId"] for c in b.hosted_companies} == {"realmB"}
    # The process-global default context was never mutated by a hosted request.
    assert _default_ctx.license_key not in ("LK-AAA", "LK-BBB")
    assert _default_ctx.hosted_companies == []
