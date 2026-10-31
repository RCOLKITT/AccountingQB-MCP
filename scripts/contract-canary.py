#!/usr/bin/env python3
"""QBO contract canary — asserts, against the LIVE connector and real books,
the QuickBooks API behaviors our code (and our mocked tests) RELY on.

Why this exists: unit tests mock QBO responses, so they encode OUR assumptions
about Intuit's API — not its actual behavior. That class of gap shipped a real
bug (2026-10: tests asserted a class column on the TransactionList report that
the real API silently drops). This canary runs read-only probes on a real
realm weekly and fails loudly when Intuit's behavior drifts from what we built
against — in either direction.

Env (both required; the workflow skips cleanly when absent):
  MCP_JWT_SECRET      — mints the connector JWT (same secret the smoke test uses)
  CANARY_LICENSE_KEY  — a license the OWNER controls (never a customer's), with
                        a connected QuickBooks company. Read-only tools only.

Usage:  python3 scripts/contract-canary.py
Exit 0 = all contracts hold; exit 1 = drift (the workflow opens an issue).
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

HOST = os.environ.get("CANARY_HOST", "https://mcp.accountingqb.com")
SECRET = os.environ.get("MCP_JWT_SECRET", "")
LICENSE = os.environ.get("CANARY_LICENSE_KEY", "")

if not SECRET or not LICENSE:
    print("contract-canary: MCP_JWT_SECRET / CANARY_LICENSE_KEY not set — skipping")
    sys.exit(0)


def _post(body: dict, headers: dict) -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"{HOST}/mcp", data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, dict(r.headers), r.read().decode()


def _parse(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {}


def _session() -> dict:
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "license_key": LICENSE,
            "sub": "contract-canary",
            "aud": HOST,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        SECRET,
        algorithm="HS256",
    )
    proto = "2025-11-25"
    hdrs = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": proto,
    }
    st, rh, raw = _post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": proto,
                "capabilities": {},
                "clientInfo": {"name": "contract-canary", "version": "1"},
            },
        },
        hdrs,
    )
    if st != 200:
        raise RuntimeError(f"initialize failed: HTTP {st}")
    negotiated = _parse(raw).get("result", {}).get("protocolVersion") or proto
    sid = rh.get("mcp-session-id") or rh.get("Mcp-Session-Id")
    hdrs = dict(hdrs)
    hdrs["MCP-Protocol-Version"] = negotiated
    if sid:
        hdrs["Mcp-Session-Id"] = sid
        _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, hdrs)
    return hdrs


def call_tool(hdrs: dict, name: str, args: dict) -> str:
    st, _, raw = _post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        hdrs,
    )
    body = _parse(raw)
    content = body.get("result", {}).get("content", [])
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content if isinstance(c, dict)
        )
    return json.dumps(body)


def main() -> int:
    hdrs = _session()
    year = datetime.now(timezone.utc).year
    start, end = f"{year}-01-01", f"{year}-01-31"
    failures: list[str] = []

    def check(label: str, ok: bool, evidence: str) -> None:
        print(f"{'✅' if ok else '❌'} {label}")
        if not ok:
            failures.append(f"{label}\n    evidence: {evidence[:300]}")

    # 0. Baseline connectivity — if this fails, nothing below is meaningful.
    info = call_tool(hdrs, "qb_company_info", {})
    check(
        "baseline: qb_company_info returns company data",
        "Company" in info or "company" in info,
        info,
    )

    # 1. QBO GeneralLedger HONORS the klass_name column request — the behavior
    #    the class-tracking GL fix is built on. Realm-aware (first canary run
    #    taught us this): QBO includes the Class column ONLY when the realm has
    #    class tracking enabled; on an untracked realm its absence is correct.
    #    So: tracked realm → column REQUIRED; untracked → absence expected.
    classes = call_tool(hdrs, "qb_list_classes", {})
    realm_has_classes = "No classes found" not in classes
    gl = call_tool(
        hdrs, "qb_general_ledger", {"start_date": start, "end_date": end}
    )
    if realm_has_classes:
        check(
            "QBO contract: GeneralLedger honors klass_name on a class-tracked realm",
            "Class" in gl,
            gl[:400],
        )
    else:
        check(
            "QBO contract: GeneralLedger renders (canary realm untracked — "
            "Class column not expected; connect a class-tracked company to "
            "assert the full contract)",
            "General Ledger" in gl,
            gl[:400],
        )

    # 2. Our query-based register renders its Class column (built because the
    #    TransactionList REPORT drops class — if this header disappears, the
    #    register regressed).
    tl = call_tool(
        hdrs,
        "qb_transaction_list",
        {"start_date": start, "end_date": end, "max_results": 5},
    )
    check(
        "register: qb_transaction_list renders the Class column",
        "| Class |" in tl or "No transactions found" in tl,
        tl[:400],
    )

    # 3. Fail-honest live: Balance Sheet by Class on a realm without class
    #    tracking must say so — never render a misleading single-column sheet.
    #    (On a class-tracked canary realm the by-class sheet renders instead.)
    bs = call_tool(hdrs, "qb_balance_sheet_by_class", {})
    check(
        "honesty: qb_balance_sheet_by_class renders by-class or says why not",
        "Balance Sheet by Class" in bs or "No class breakdown available" in bs,
        bs[:400],
    )

    # 4. Tax-data provenance endpoint: ledger chain must verify.
    with urllib.request.urlopen(f"{HOST}/tax-data", timeout=30) as r:
        tax = json.loads(r.read().decode())
    check(
        "provenance: /tax-data ledger chain verifies",
        bool(tax.get("ledger", {}).get("chain_ok")) and tax["ledger"]["rows"] > 0,
        json.dumps(tax.get("ledger", {})),
    )

    print()
    if failures:
        print(f"CONTRACT DRIFT — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All QBO contracts hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
