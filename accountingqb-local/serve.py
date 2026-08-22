#!/usr/bin/env python3
"""AccountingQB — local "Door 2" shim.

A localhost-only HTTP server that wraps the AccountingQB MCP connector so the app
can run as a downloadable desktop app (Tauri sidecar) or plain `python serve.py`,
rendered in the browser — without depending on the Cowork bridge. It:

  * binds 127.0.0.1 ONLY, with Host + Origin allowlist checks (DNS-rebind / CSRF safe),
  * invokes the connector's 131 tools IN-PROCESS (no stdio round-trip) via FastMCP's
    tool registry,
  * relays chat to Claude with the user's OWN Anthropic key (BYO key; nothing AI
    touches our servers),
  * connects QuickBooks via loopback OAuth (local Intuit app) or the hosted broker,
  * auto-creates ~/.accountingqb and picks a free port.

Ported from the sibling repo Hearth's `hearth-local/serve.js`; Python here because the
connector is Python/FastMCP. This is Phase 2a — the shim + wiring. The tabbed
Chat+Dashboard UI (2b) and the signed Tauri build (2c) build on top of it.

Run:  python accountingqb-local/serve.py         (opens http://127.0.0.1:8788)
Env:  ACCOUNTINGQB_PORT, ACCOUNTINGQB_DATA_DIR, ACCOUNTINGQB_NO_OPEN,
      ANTHROPIC_API_KEY, ANTHROPIC_MODEL, plus the connector's QB_* vars.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

# --- make the canonical connector importable (repo layout: mcpb/src/accountingqb) ---
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "mcpb" / "src"))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import (  # noqa: E402
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from starlette.routing import Route  # noqa: E402

from accountingqb import server as qb  # noqa: E402  (the connector: mcp, tools, tokens)
from accountingqb.context import get_ctx  # noqa: E402

# ---------------------------------------------------------------------------
# Config / local state (mirrors Hearth's ~/.hearth pattern)
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("ACCOUNTINGQB_DATA_DIR", Path.home() / ".accountingqb"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "tauri.localhost"}

# BYO-key AI. Chat uses a mid-tier model by default; the user pays via their own key.
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Intuit OAuth (local / BYO-Intuit-app path) — same endpoints as setup.py.
OAUTH_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
OAUTH_SCOPES = "com.intuit.quickbooks.accounting"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(patch: dict) -> dict:
    cfg = {**load_config(), **patch}
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(CONFIG_FILE)
    return cfg


def _anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY") or load_config().get("anthropic_api_key", "")


def _server_version() -> str:
    try:
        return json.loads((_REPO_ROOT / "mcpb" / "manifest.json").read_text()).get("version", "dev")
    except Exception:
        return "dev"


# ---------------------------------------------------------------------------
# In-process tool invocation (FastMCP 1.29: tool.fn / tool.is_async)
# ---------------------------------------------------------------------------
def _tool_registry() -> dict:
    return qb.mcp._tool_manager._tools  # noqa: SLF001 — stable in mcp 1.29


async def call_tool(name: str, args: dict) -> object:
    tools = _tool_registry()
    tool = tools.get(name)
    if tool is None:
        raise KeyError(f"unknown tool: {name}")
    if getattr(tool, "context_kwarg", None):
        # A tool that wants FastMCP's request Context can't be called bare here;
        # none of the connector's tools need it today, but fail loud if that changes.
        raise RuntimeError(f"tool {name} requires a FastMCP Context (unsupported in the local shim)")
    fn = tool.fn
    result = await fn(**(args or {})) if tool.is_async else fn(**(args or {}))
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
async def healthz(_req: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def api_status(_req: Request) -> JSONResponse:
    ctx = get_ctx()
    connected = bool(getattr(ctx, "refresh_token", "") or ctx.hosted_mode)
    return JSONResponse(
        {
            "version": _server_version(),
            "toolCount": len(_tool_registry()),
            "hostedMode": bool(ctx.hosted_mode),
            "connected": connected,
            "hasAnthropicKey": bool(_anthropic_key()),
            "realmId": getattr(ctx, "realm_id", "") or "",
        }
    )


async def api_tools(_req: Request) -> JSONResponse:
    tools = _tool_registry()
    return JSONResponse(
        {"tools": [{"name": n, "description": (t.description or "").split("\n")[0]} for n, t in sorted(tools.items())]}
    )


async def mcp_call(req: Request) -> JSONResponse:
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"isError": True, "error": "invalid JSON body"}, status_code=400)
    name = (body or {}).get("tool")
    args = (body or {}).get("args") or {}
    if not name:
        return JSONResponse({"isError": True, "error": "missing 'tool'"}, status_code=400)
    try:
        result = await call_tool(name, args)
        return JSONResponse({"ok": True, "result": result})
    except KeyError as e:
        return JSONResponse({"isError": True, "error": str(e)}, status_code=404)
    except Exception as e:  # tool-level errors surface as friendly messages, not 500s
        return JSONResponse({"isError": True, "error": f"{type(e).__name__}: {e}"})


async def sample(req: Request) -> JSONResponse:
    """BYO-key Claude relay. NO proxy — the key never leaves the machine."""
    key = _anthropic_key()
    if not key:
        return JSONResponse({"needsKey": True, "error": "No Anthropic API key set. Add one to enable chat."})
    try:
        body = await req.json()
    except Exception:
        body = {}
    system = str(body.get("system") or "")
    messages = body.get("messages")
    if not messages:
        # accept a simple {system, ctx} shape too
        messages = [{"role": "user", "content": json.dumps(body.get("ctx") or body.get("prompt") or {})}]
    model = body.get("model") or DEFAULT_MODEL
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "content-type": "application/json",
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
                json={"model": model, "max_tokens": 2048, "system": system, "messages": messages},
            )
        if r.status_code != 200:
            return JSONResponse({"error": f"Anthropic {r.status_code}: {r.text[:400]}"}, status_code=502)
        data = r.json()
        text = "".join(part.get("text", "") for part in data.get("content", []))
        return JSONResponse({"text": text})
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)


async def api_config(req: Request) -> JSONResponse:
    """Persist local settings from the UI (Anthropic key, optional Intuit app creds)."""
    try:
        body = await req.json()
    except Exception:
        body = {}
    patch = {}
    for k_in, k_cfg in (
        ("anthropicApiKey", "anthropic_api_key"),
        ("qbClientId", "qb_client_id"),
        ("qbClientSecret", "qb_client_secret"),
        ("licenseKey", "license_key"),
    ):
        if body.get(k_in):
            patch[k_cfg] = str(body[k_in])
    if patch:
        save_config(patch)
    return JSONResponse({"ok": True, "hasAnthropicKey": bool(_anthropic_key())})


def _redirect_uri(req: Request) -> str:
    # Loopback redirect back to THIS shim. Local (BYO Intuit app) users must register
    # this exact URI in their Intuit app; the hosted broker path avoids this entirely.
    return f"http://localhost:{req.url.port or PORT}/callback"


async def oauth_start(req: Request) -> RedirectResponse:
    cfg = load_config()
    client_id = os.environ.get("QB_CLIENT_ID") or cfg.get("qb_client_id")
    if not client_id:
        # Hosted broker path (no Intuit app needed): hand off to the web connect flow.
        lic = getattr(qb, "LICENSE_KEY", "") or cfg.get("license_key", "")
        api = os.environ.get("QB_API_URL", "https://accountingqb.com").rstrip("/")
        dest = f"{api}/setup-wizard" + (f"?key={urllib.parse.quote(lic)}" if lic else "")
        return RedirectResponse(dest, status_code=302)
    state = secrets.token_urlsafe(16)
    save_config({"oauth_state": state})
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": OAUTH_SCOPES,
            "redirect_uri": _redirect_uri(req),
            "state": state,
        }
    )
    return RedirectResponse(f"{OAUTH_AUTH_URL}?{params}", status_code=302)


async def oauth_callback(req: Request) -> HTMLResponse:
    p = req.query_params
    if p.get("error"):
        return HTMLResponse(f"<h1>Authorization failed</h1><p>{p.get('error_description', p.get('error'))}</p>", 400)
    code = p.get("code")
    realm = p.get("realmId")
    if not code:
        return HTMLResponse("<h1>Missing authorization code</h1>", 400)
    if p.get("state") and p.get("state") != load_config().get("oauth_state"):
        return HTMLResponse("<h1>State mismatch</h1><p>Please retry the connection.</p>", 400)
    cfg = load_config()
    client_id = os.environ.get("QB_CLIENT_ID") or cfg.get("qb_client_id")
    client_secret = os.environ.get("QB_CLIENT_SECRET") or cfg.get("qb_client_secret")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                OAUTH_TOKEN_URL,
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect_uri(req)},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json"},
            )
        if r.status_code != 200:
            return HTMLResponse(f"<h1>Token exchange failed</h1><pre>{r.text[:500]}</pre>", 400)
        tok = r.json()
    except Exception as e:
        return HTMLResponse(f"<h1>Token exchange error</h1><pre>{e}</pre>", 502)

    refresh = tok.get("refresh_token", "")
    if refresh:
        qb._save_token(refresh)  # encrypted to ~/.accountingqb via the connector
        ctx = get_ctx()
        ctx.refresh_token = refresh
        if realm:
            ctx.realm_id = realm
            save_config({"realm_id": realm})
    return HTMLResponse(
        "<html><body style='font-family:system-ui;text-align:center;padding:64px;background:#0a0e1a;color:#e5e7eb'>"
        "<h1 style='color:#22d3ee'>&#10003; QuickBooks connected</h1>"
        "<p>You can close this tab and return to AccountingQB.</p>"
        "<script>setTimeout(()=>window.close(),2500)</script></body></html>"
    )


async def index(_req: Request) -> HTMLResponse:
    # Placeholder shell for Phase 2a. Phase 2b replaces this with the tabbed
    # Chat + Dashboard artifact. Kept minimal but functional: shows status and the
    # two setup actions (connect QuickBooks, add Anthropic key) and a tool probe.
    return HTMLResponse(_INDEX_HTML)


# ---------------------------------------------------------------------------
# Security: localhost-only Host + Origin allowlist (port Hearth serve.js:487-500)
# ---------------------------------------------------------------------------
class LocalOnly(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = (request.headers.get("host") or "").split(":")[0]
        if host and host not in ALLOWED_HOSTS:
            return PlainTextResponse("forbidden host", status_code=403)
        origin = request.headers.get("origin")
        if origin:
            oh = urllib.parse.urlparse(origin).hostname
            if oh not in ALLOWED_ORIGIN_HOSTS:
                return PlainTextResponse("forbidden origin", status_code=403)
        return await call_next(request)


routes = [
    Route("/", index),
    Route("/healthz", healthz),
    Route("/api/status", api_status),
    Route("/api/tools", api_tools),
    Route("/api/config", api_config, methods=["POST"]),
    Route("/mcp", mcp_call, methods=["POST"]),
    Route("/sample", sample, methods=["POST"]),
    Route("/oauth/start", oauth_start),
    Route("/callback", oauth_callback),
]

app = Starlette(routes=routes, middleware=[])
app.add_middleware(LocalOnly)


# ---------------------------------------------------------------------------
# Boot: free port + auto-open browser (port Hearth main.rs / serve.js)
# ---------------------------------------------------------------------------
def pick_port() -> int:
    env = os.environ.get("ACCOUNTINGQB_PORT") or os.environ.get("PORT")
    if env:
        return int(env)
    for p in (8788, 8789, 8790):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = pick_port()

_INDEX_HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>AccountingQB</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;background:#0a0e1a;color:#e5e7eb;max-width:720px;margin:0 auto;padding:40px}
a.btn,button{background:#fff;color:#0a0e1a;border:0;border-radius:10px;padding:10px 16px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}
.muted{color:#94a3b8}.card{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:20px;margin:16px 0;background:#131a2e}
input{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.15);background:#0d1220;color:#fff;margin:6px 0}
pre{white-space:pre-wrap;background:#0d1220;padding:12px;border-radius:8px;max-height:320px;overflow:auto}</style></head>
<body>
<h1><span style="color:#22d3ee">Accounting</span><span style="color:#60a5fa">QB</span> <span class=muted style="font-size:14px">local</span></h1>
<p class=muted id=status>Loading status…</p>
<div class=card><h3>1 · Connect QuickBooks</h3>
<p class=muted>Opens the QuickBooks consent flow. No data leaves your machine.</p>
<a class=btn href="/oauth/start">Connect QuickBooks</a></div>
<div class=card><h3>2 · Add your Anthropic key <span class=muted>(for chat)</span></h3>
<p class=muted>Stored only in ~/.accountingqb. Chat calls go from your machine straight to Anthropic.</p>
<input id=key type=password placeholder="sk-ant-…"><button onclick=saveKey()>Save key</button></div>
<div class=card><h3>Probe a tool</h3>
<button onclick="run('qb_server_info')">qb_server_info</button>
<button onclick="run('qb_tax_data_info')">qb_tax_data_info</button>
<pre id=out class=muted>—</pre></div>
<p class=muted style="font-size:12px">Phase 2a shell. The tabbed Chat + Dashboard UI lands in Phase 2b.</p>
<script>
async function refresh(){const s=await (await fetch('/api/status')).json();
document.getElementById('status').textContent=`v${s.version} · ${s.toolCount} tools · QuickBooks ${s.connected?'connected':'not connected'} · Anthropic key ${s.hasAnthropicKey?'set':'missing'}`;}
async function saveKey(){const k=document.getElementById('key').value.trim();if(!k)return;
await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({anthropicApiKey:k})});
document.getElementById('key').value='';refresh();}
async function run(tool){const o=document.getElementById('out');o.textContent='Running '+tool+'…';
const r=await fetch('/mcp',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({tool,args:{}})});
const j=await r.json();o.textContent=typeof j.result==='string'?j.result:JSON.stringify(j,null,2);}
refresh();
</script></body></html>"""


def main() -> None:
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  AccountingQB local is live → {url}\n")
    if not os.environ.get("ACCOUNTINGQB_NO_OPEN"):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform.startswith("win"):
                os.startfile(url)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
