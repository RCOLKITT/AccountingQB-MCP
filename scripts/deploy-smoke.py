#!/usr/bin/env python3
"""Deploy smoke test — verify the LIVE connector after a deploy.

Two checks against the public hostname Cowork uses (https://mcp.accountingqb.com):

  1. GET /version (unauthenticated) — the deployed build's version and tool count
     match the released tag, and it self-identifies as the hosted connector.
     Catches stale/failed deploys (the 3.14.0/3.14.2 divergence) in one call.

  2. tools/call qb_server_info through the AUTHENTICATED /mcp endpoint — exercises
     the exact JWT + MCP transport path Cowork uses, and asserts the same version
     + "hosted connector" comes back through it. Needs MCP_JWT_SECRET (inject via
     `doppler run -p accountingqb-mcp -c prd -- python scripts/deploy-smoke.py`).
     Skipped with a warning if the secret isn't present.

Exit 0 = all checks pass. Non-zero = a mismatch (fail the deploy).

Usage:
  python scripts/deploy-smoke.py [--expect-version X.Y.Z] [--host URL]
  # version defaults to mcpb/pyproject.toml; host defaults to mcp.accountingqb.com
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_HOST = "https://mcp.accountingqb.com"
DEMO_LICENSE = "LK-DEMO-REVIEW2026"      # qb_server_info needs no real QB connection
AUDIENCE = "https://mcp.accountingqb.com"


def _pyproject_version() -> str:
    p = Path(__file__).resolve().parent.parent / "mcpb" / "pyproject.toml"
    m = re.search(r'^version\s*=\s*"([^"]+)"', p.read_text(), re.M)
    return m.group(1) if m else ""


def _get_json(url: str, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
        return r.status, dict(r.headers), raw


def check_version(host: str, expect: str) -> bool:
    print(f"→ GET {host}/version")
    try:
        status, _, raw = _get_json(f"{host}/version")
    except Exception as e:
        print(f"  ✗ request failed: {e}")
        return False
    if status != 200:
        print(f"  ✗ HTTP {status}")
        return False
    info = json.loads(raw)
    ok = True
    if info.get("version") != expect:
        print(f"  ✗ version {info.get('version')!r} != expected {expect!r} "
              "(stale or failed deploy)")
        ok = False
    else:
        print(f"  ✓ version {info['version']}")
    if "hosted connector" not in (info.get("deployment") or ""):
        print(f"  ✗ deployment {info.get('deployment')!r} is not the hosted connector")
        ok = False
    else:
        print(f"  ✓ deployment: {info['deployment']}")
    print(f"  · tools: {info.get('tools')}")
    return ok


def _mint_jwt(secret: str) -> str:
    import jwt as pyjwt  # PyJWT
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return pyjwt.encode(
        {"license_key": DEMO_LICENSE, "sub": "deploy-smoke",
         "aud": AUDIENCE, "iat": now, "exp": now + timedelta(minutes=5)},
        secret, algorithm="HS256")


def _parse_mcp_body(raw: str) -> dict:
    """A streamable-HTTP response is JSON (json_response=True) or SSE — handle both."""
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {}


def check_authenticated(host: str, expect: str, secret: str) -> bool:
    print(f"→ tools/call qb_server_info via {host}/mcp (authenticated)")
    try:
        token = _mint_jwt(secret)
    except Exception as e:
        print(f"  ⚠ could not mint JWT ({e}) — is PyJWT installed? Skipping.")
        return True
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2026-07-28", "capabilities": {},
                       "clientInfo": {"name": "deploy-smoke", "version": "1.0"}}}
    try:
        status, respheaders, _ = _get_json(f"{host}/mcp", hdrs, json.dumps(init).encode())
        if status == 401:
            print("  ✗ 401 — JWT rejected (secret/audience mismatch)")
            return False
        sid = respheaders.get("mcp-session-id") or respheaders.get("Mcp-Session-Id")
        call_hdrs = dict(hdrs)
        if sid:
            call_hdrs["Mcp-Session-Id"] = sid
            # stateless servers still want the initialized notification
            note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            _get_json(f"{host}/mcp", call_hdrs, json.dumps(note).encode())
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "qb_server_info", "arguments": {}}}
        status, _, raw = _get_json(f"{host}/mcp", call_hdrs, json.dumps(call).encode())
    except Exception as e:
        print(f"  ✗ MCP call failed: {e}")
        return False
    body = _parse_mcp_body(raw)
    text = json.dumps(body)
    content = body.get("result", {}).get("content", [])
    if content and isinstance(content, list):
        text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    ok = True
    if expect not in text:
        print(f"  ✗ qb_server_info did not report version {expect}")
        ok = False
    else:
        print(f"  ✓ qb_server_info reports {expect}")
    if "hosted connector" not in text:
        print("  ✗ qb_server_info deployment is not 'hosted connector'")
        ok = False
    else:
        print("  ✓ qb_server_info deployment: hosted connector")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-version", default="")
    ap.add_argument("--host", default=DEFAULT_HOST)
    args = ap.parse_args()
    expect = args.expect_version or _pyproject_version()
    host = args.host.rstrip("/")
    print(f"Deploy smoke test — {host} — expecting v{expect}\n")

    ok = check_version(host, expect)

    secret = os.environ.get("MCP_JWT_SECRET", "")
    if secret:
        ok = check_authenticated(host, expect, secret) and ok
    else:
        print("→ authenticated check: MCP_JWT_SECRET not set — skipping "
              "(run under `doppler run` to exercise the /mcp path).")

    print()
    print("✅ SMOKE PASS" if ok else "❌ SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
