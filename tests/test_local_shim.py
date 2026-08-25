"""Phase 2a — local "Door 2" shim (accountingqb-local/serve.py).

Verifies the localhost-only security allowlist, in-process tool invocation over
HTTP, and the BYO-key gate — without starting a real server (Starlette TestClient).
The shim file has a hyphen in its dir, so it's loaded by path.
"""

import importlib.util
import pathlib

import pytest
from starlette.testclient import TestClient

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "aqb_local_serve", _ROOT / "accountingqb-local" / "serve.py"
)
serve = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(serve)  # type: ignore[union-attr]


@pytest.fixture
def client():
    # base_url sets Host to 127.0.0.1 → passes the LocalOnly allowlist.
    return TestClient(serve.app, base_url="http://127.0.0.1:8788")


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.text == "ok"


def test_status_reports_tools(client):
    data = client.get("/api/status").json()
    assert data["toolCount"] == 131
    assert data["connected"] is False  # no QB in tests


def test_mcp_invokes_tool_in_process(client):
    # qb_server_info needs no QuickBooks connection.
    r = client.post("/mcp", json={"tool": "qb_server_info", "args": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "AccountingQB MCP" in body["result"]


def test_mcp_unknown_tool_is_404_not_500(client):
    r = client.post("/mcp", json={"tool": "nope_not_a_tool", "args": {}})
    assert r.status_code == 404
    assert r.json()["isError"] is True


# --- write safety: no silent mutations (Constitution) ---

def test_write_tool_requires_confirmation(client):
    # A book-mutating tool via /mcp is refused (and does nothing) unless confirmed.
    r = client.post("/mcp", json={"tool": "qb_create_expense",
                                  "args": {"vendor_name": "X", "amount": 1,
                                           "account_name": "Office", "date": "2026-01-01"}})
    d = r.json()
    assert d.get("needsConfirm") is True and not d.get("ok")


def test_write_tool_confirmed_passes_and_strips_flag(client, monkeypatch):
    captured = {}

    async def fake_call(name, args):
        captured["name"] = name
        captured["args"] = dict(args)
        return "booked"

    monkeypatch.setattr(serve, "call_tool", fake_call)
    r = client.post("/mcp", json={"tool": "qb_create_expense",
                                  "args": {"vendor_name": "X", "amount": 1, "account_name": "Office",
                                           "date": "2026-01-01", "confirmed": True}})
    d = r.json()
    assert d.get("ok") is True and d.get("result") == "booked"
    assert captured["name"] == "qb_create_expense"
    assert "confirmed" not in captured["args"]  # UI flag never forwarded to the tool


def test_read_tool_not_gated(client):
    assert client.post("/mcp", json={"tool": "qb_server_info", "args": {}}).json().get("ok") is True


def test_sample_without_key_reports_needskey(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(serve, "_anthropic_key", lambda: "")
    r = client.post("/sample", json={"system": "hi", "messages": [{"role": "user", "content": "hi"}]})
    assert r.json()["needsKey"] is True


def test_forbidden_host_and_origin():
    c = TestClient(serve.app, base_url="http://127.0.0.1:8788")
    assert c.get("/healthz", headers={"Host": "evil.com"}).status_code == 403
    assert c.get("/healthz", headers={"Origin": "https://evil.com"}).status_code == 403
    # An allowed cross-origin (localhost) is fine.
    assert c.get("/healthz", headers={"Origin": "http://localhost:8788"}).status_code == 200


def test_oauth_start_without_intuit_creds_redirects_to_broker(client, monkeypatch):
    monkeypatch.delenv("QB_CLIENT_ID", raising=False)
    monkeypatch.setattr(serve, "load_config", lambda: {})
    r = client.get("/oauth/start", follow_redirects=False)
    assert r.status_code == 302
    assert "setup-wizard" in r.headers["location"]


# --- Phase 2b: chat tool exposure + agentic loop ---------------------------------

def test_chat_tools_are_readonly_and_real():
    defs = serve._anthropic_tools()
    assert len(defs) >= 10  # curated set is meaningfully populated
    registry = serve._tool_registry()
    manifest_ro = {t["name"]: t.get("readOnlyHint", False) for t in serve._manifest().get("tools", [])}
    for d in defs:
        assert d["name"] in registry           # real, callable tool
        assert manifest_ro.get(d["name"]) is True  # NEVER expose a write tool to the auto-loop
        assert "input_schema" in d


def test_index_serves_tabbed_artifact(client):
    html = client.get("/").text
    # Ported "Ledger editorial" UI: 9 report tabs + the Ask panel, driven by the window.cowork shim.
    assert "Dashboard" in html and "Ask AccountingQB" in html
    assert 'data-tab="pl"' in html and 'data-tab="workbook"' in html
    assert "window.cowork" in html and "desktopChatRun" in html


def test_chat_without_key(client, monkeypatch):
    monkeypatch.setattr(serve, "_anthropic_key", lambda: "")
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.json()["needsKey"] is True


def test_chat_agentic_loop_runs_a_real_tool(client, monkeypatch):
    """Mock Anthropic: round 1 asks for a tool, round 2 answers. The loop must actually
    execute the tool in-process and return the final text + a trace."""
    monkeypatch.setattr(serve, "_anthropic_key", lambda: "sk-test")

    class FakeResp:
        def __init__(self, payload):
            self.status_code = 200
            self._p = payload
            self.text = "ok"

        def json(self):
            return self._p

    turns = [
        FakeResp({
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "t1", "name": "qb_tax_data_info", "input": {}}],
        }),
        FakeResp({
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "Here's what I found."}],
        }),
    ]
    state = {"i": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            r = turns[min(state["i"], len(turns) - 1)]
            state["i"] += 1
            return r

    monkeypatch.setattr(serve.httpx, "AsyncClient", FakeClient)

    r = client.post("/chat", json={"messages": [{"role": "user", "content": "what tax data do you use?"}]})
    body = r.json()
    assert body["reply"] == "Here's what I found."
    assert any(t["tool"] == "qb_tax_data_info" for t in body["trace"])  # tool really ran


# --- Coffer/Hearth integration dialect (/mcp structured JSON) --------------------

_OWNER_DRAWS_MD = (
    "## Owner's Draws & Contributions\n"
    "Owner Draw: ($12,345.00)\n"
    "**Net owner activity: ($12,345.00)** (net draw)\n"
)
_ESTIMATE_MD = (
    "## Estimated Quarterly Tax — 2026\n"
    "**Total estimated annual tax: $10,000.00**\n"
    "**Each quarterly payment: $2,500.00**\n"
    "### Quarterly Due Dates:\n"
    "  Q3: Sep 15 — $2,500.00 (⏳ Current)\n"
)


_PAIR_HDR = {"X-AQB-Pairing": "testsecret"}


def _fake_call_tool(canned):
    async def _call(name, args):
        val = canned.get(name)
        return val(args) if callable(val) else val
    return _call


@pytest.fixture
def paired(monkeypatch):
    """Simulate an established, identity-verified pairing on the shim."""
    monkeypatch.setattr(serve, "_load_pairing", lambda: {"pairing_secret": "testsecret", "peer_product": "coffer"})


# --- pairing gate (cross-user contamination guard) ---

def test_integration_inert_until_paired(client, monkeypatch):
    monkeypatch.setattr(serve, "_load_pairing", lambda: {})
    r = client.post("/mcp", json={"tool": "qb_owner_draws", "args": {"year": 2026}})
    assert r.status_code == 403 and r.json().get("needs") == "pairing"


def test_integration_rejects_wrong_secret(client, paired):
    r = client.post("/mcp", json={"tool": "qb_owner_draws", "args": {"year": 2026}},
                    headers={"X-AQB-Pairing": "wrong"})
    assert r.status_code == 403


def test_whoami(client):
    d = client.get("/whoami").json()
    assert d["app"] == "accountingqb" and "paired" in d


def test_pair_and_unpair(client):
    assert client.post("/pair", json={"pairingSecret": "s1", "peerProduct": "coffer"}).json()["paired"] is True
    assert client.get("/whoami").json()["paired"] is True
    assert client.post("/unpair", json={}).json()["paired"] is False


# --- integration dialect (pairing-gated) ---

def test_owner_draws_structured(client, paired, monkeypatch):
    monkeypatch.setattr(serve, "call_tool", _fake_call_tool({"qb_owner_draws": _OWNER_DRAWS_MD}))
    d = client.post("/mcp", json={"tool": "qb_owner_draws", "args": {"year": 2026}}, headers=_PAIR_HDR).json()
    assert d["net"] == -12345.0
    assert d["ytd"] == 12345.0  # money drawn out = household income


def test_estimate_requires_filing_status(client, paired):
    d = client.post("/mcp", json={"tool": "qb_estimate_quarterly_tax", "args": {"tax_year": 2026}},
                    headers=_PAIR_HDR).json()
    assert d.get("needs") == ["filing_status"]  # never guesses a status


def test_estimate_structured(client, paired, monkeypatch):
    monkeypatch.setattr(serve, "call_tool", _fake_call_tool({"qb_estimate_quarterly_tax": _ESTIMATE_MD}))
    d = client.post("/mcp", json={"tool": "qb_estimate_quarterly_tax",
                                  "args": {"tax_year": 2026, "filing_status": "single"}},
                    headers=_PAIR_HDR).json()
    assert d["amount"] == 2500.0 and d["annual"] == 10000.0
    assert d["period"] == "Q3 2026" and d["due"] == "Sep 15"


def test_owner_paid_expense_confirm_gate_and_idempotency(client, paired, monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "BOOKED_FILE", tmp_path / "booked.json")
    monkeypatch.setattr(serve, "call_tool", _fake_call_tool(
        {"qb_create_journal_entry": "Journal entry created!\nId: 42\n"}))
    txn = {"key": "id:999", "date": "2026-08-14", "amount": -184.32, "merchant": "Staples",
           "note": "printer", "receipt": {"orderId": "9483-2211"}}

    # No confirmation → refused, nothing booked.
    r0 = client.post("/mcp", json={"tool": "qb_record_owner_paid_expense", "args": txn}, headers=_PAIR_HDR).json()
    assert r0["ok"] is False and "confirmation" in r0["error"]

    # Confirmed → booked as a journal entry to the review account.
    r1 = client.post("/mcp", json={"tool": "qb_record_owner_paid_expense", "args": {**txn, "confirmed": True}},
                     headers=_PAIR_HDR).json()
    assert r1["ok"] is True and r1["booked"] is True and r1["amount"] == 184.32
    assert "review" in r1["treatment"].lower()

    # Same key again → idempotent success, NOT a duplicate booking.
    r2 = client.post("/mcp", json={"tool": "qb_record_owner_paid_expense", "args": {**txn, "confirmed": True}},
                     headers=_PAIR_HDR).json()
    assert r2["ok"] is True and r2.get("alreadyBooked") is True


# --- OAuth-style linking (redirect + PKCE) ---

def test_link_connect_redirects_to_peer_authorize(client, monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "COFFER_API_URL", "https://coffermoney.com")
    monkeypatch.setattr(serve, "LINK_STATE_FILE", tmp_path / "link_state.json")
    r = client.get("/link/connect?peer=coffer", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://coffermoney.com/link/authorize?")
    assert "code_challenge=" in loc and "code_challenge_method=S256" in loc
    assert "redirect_uri=" in loc and "127.0.0.1" in loc
    # The verifier+state are persisted for the callback leg.
    st = serve._load_link_state()
    assert st.get("verifier") and st.get("state")


def test_link_callback_rejects_state_mismatch(client, monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "LINK_STATE_FILE", tmp_path / "link_state.json")
    serve._save_link_state({"verifier": "v", "state": "realstate", "peer": "coffer"})
    r = client.get("/link/callback?code=abc&state=WRONG", follow_redirects=False)
    assert r.status_code == 400
    assert "State mismatch" in r.text


def test_link_callback_stores_secret_on_success(client, monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "LINK_STATE_FILE", tmp_path / "link_state.json")
    monkeypatch.setattr(serve, "PAIRING_FILE", tmp_path / "pairing.json")
    monkeypatch.setattr(serve, "COFFER_API_URL", "https://coffermoney.com")
    serve._save_link_state({"verifier": "the-verifier", "state": "S", "peer": "coffer"})

    class FakeResp:
        status_code = 200
        def json(self):
            return {"ok": True, "pairingSecret": "SECRET123", "peerProduct": "coffer"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            assert url.endswith("/api/link/redeem")
            assert json["code"] == "code-xyz" and json["codeVerifier"] == "the-verifier"
            return FakeResp()

    monkeypatch.setattr(serve.httpx, "AsyncClient", FakeClient)
    r = client.get("/link/callback?code=code-xyz&state=S", follow_redirects=False)
    assert r.status_code == 200 and "connected" in r.text.lower()
    assert serve._load_pairing().get("pairing_secret") == "SECRET123"
    assert serve._load_link_state() == {}  # consumed


def test_bootstrap_pairing_restores_from_web(monkeypatch, tmp_path):
    # A restart that emptied the local cache must re-pair from the web on boot (source of truth).
    monkeypatch.setattr(serve, "PAIRING_FILE", tmp_path / "pairing.json")
    monkeypatch.delenv("QB_LICENSE_KEY", raising=False)
    monkeypatch.setattr(serve, "load_config", lambda: {"license_key": "LK-TEST"})

    class FakeResp:
        status_code = 200
        def json(self):
            return {"paired": True, "pairingSecret": "SEKRET", "peerProduct": "coffer"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None):
            assert url.endswith("/api/link/status") and params.get("key") == "LK-TEST"
            return FakeResp()

    monkeypatch.setattr(serve.httpx, "Client", FakeClient)
    serve._bootstrap_pairing()
    assert serve._load_pairing().get("pairing_secret") == "SEKRET"


def test_bootstrap_pairing_no_license_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "PAIRING_FILE", tmp_path / "pairing.json")
    monkeypatch.delenv("QB_LICENSE_KEY", raising=False)
    monkeypatch.setattr(serve, "load_config", lambda: {})
    serve._bootstrap_pairing()  # no license → no network, no crash
    assert serve._load_pairing() == {}


def test_link_refresh_requires_license(client, monkeypatch):
    monkeypatch.setattr(serve, "load_config", lambda: {})
    monkeypatch.setattr(serve.qb, "LICENSE_KEY", "", raising=False)
    r = client.post("/link/refresh")
    assert r.status_code == 400 and r.json()["paired"] is False


def test_owner_paid_expense_expected_realm_guard(client, paired, monkeypatch, tmp_path):
    import types
    monkeypatch.setattr(serve, "BOOKED_FILE", tmp_path / "booked.json")
    monkeypatch.setattr(serve, "get_ctx", lambda: types.SimpleNamespace(realm_id="R1"))
    r = client.post("/mcp", json={"tool": "qb_record_owner_paid_expense",
                                  "args": {"key": "k1", "amount": -10, "date": "2026-01-01",
                                           "confirmed": True, "expected_realm_id": "R2"}},
                    headers=_PAIR_HDR).json()
    assert r["ok"] is False and "expected_realm_id" in r["error"]
