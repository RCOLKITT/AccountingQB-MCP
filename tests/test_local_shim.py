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
    assert "Dashboard" in html and "Chat" in html and "Ask your books" in html


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
