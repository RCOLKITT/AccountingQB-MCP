#!/usr/bin/env python3
"""FULL QBO class-tracking contract, run against an Intuit SANDBOX company.

The hosted contract canary (scripts/contract-canary.py) runs read-only probes
through the production connector, but its realm has no class tracking (that
needs QBO Plus/Advanced). Intuit SANDBOX companies get Plus features for free —
and a sandbox realm cannot connect to the hosted connector (QB_ENVIRONMENT sets
the API base process-wide). So this script runs the LOCAL server in-process
with QB_ENVIRONMENT=sandbox and exercises the full class loop against real
Intuit sandbox behavior:

    enable class tracking -> create a class -> post a class-tagged journal
    entry -> assert the GeneralLedger report returns the Class column AND the
    class VALUE (the exact contract our offline fixtures assume) -> assert the
    class-filtered register finds it -> delete the journal entry (cleanup).

ISOLATION: Development app keys + a sandbox realm with Intuit's sample data.
No production connector, no production database, no customer realm, no real
books. Writes touch only the disposable sandbox company and are cleaned up.

Env (workflow skips cleanly when absent):
  QB_ENVIRONMENT=sandbox     — REQUIRED; refuses to run otherwise
  QB_CLIENT_ID / QB_CLIENT_SECRET — the Intuit app's DEVELOPMENT keys
  SANDBOX_REALM_ID           — the sandbox company's realm id
  SANDBOX_REFRESH_TOKEN      — bootstrap refresh token (OAuth playground)
  SANDBOX_TOKEN_FILE         — optional path; read first (rotated token from a
                               prior run, via actions/cache) and written after
                               every run, because Intuit rotates refresh tokens.

Exit 0 = contract holds · 1 = drift/failure · 0 with a skip message = not configured.
"""

import asyncio
import json
import os
import pathlib
import re
import sys
from datetime import date

if os.environ.get("QB_ENVIRONMENT") != "sandbox":
    print("sandbox-canary: QB_ENVIRONMENT != sandbox — refusing to run")
    sys.exit(0)

REALM = os.environ.get("SANDBOX_REALM_ID", "")
TOKEN_FILE = os.environ.get("SANDBOX_TOKEN_FILE", "")
bootstrap_token = os.environ.get("SANDBOX_REFRESH_TOKEN", "")
if TOKEN_FILE and pathlib.Path(TOKEN_FILE).exists():
    rotated = pathlib.Path(TOKEN_FILE).read_text().strip()
    if rotated:
        bootstrap_token = rotated
        print("sandbox-canary: using rotated token from cache")

if not (
    REALM
    and bootstrap_token
    and os.environ.get("QB_CLIENT_ID")
    and os.environ.get("QB_CLIENT_SECRET")
):
    print("sandbox-canary: sandbox credentials not configured — skipping")
    sys.exit(0)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "mcpb/src"))

import accountingqb.server as s  # noqa: E402  (env must be set before import)
from accountingqb.context import QBContext, set_ctx  # noqa: E402

CLASS_NAME = "Canary Contract"


async def main() -> int:
    ctx = QBContext(refresh_token=bootstrap_token, realm_id=REALM, persist_tokens=False)
    set_ctx(ctx)
    failures: list[str] = []

    def check(label: str, ok: bool, evidence: str) -> None:
        print(f"{'✅' if ok else '❌'} {label}")
        if not ok:
            failures.append(f"{label}\n    evidence: {evidence[:300]}")

    # 0. Baseline — sandbox connectivity + token refresh path.
    info = await s.qb_company_info()
    check("baseline: sandbox company reachable", "Company" in info, info)

    # 1. Enable class tracking (idempotent; sandbox plans support it).
    en = await s.qb_enable_class_tracking()
    check(
        "setup: class tracking enabled (or already on)",
        "✅" in en or "already ON" in en,
        en,
    )

    # 2. Create the canary class (duplicate on re-run is fine — verified below).
    created = await s.qb_create_class(CLASS_NAME)
    if "✅" not in created and "already exists" not in created:
        check("setup: qb_create_class", False, created)
    classes = await s.qb_list_classes()
    check("setup: canary class exists", CLASS_NAME in classes, classes[:300])

    # 3. Post a class-tagged journal entry (per-line class — the per-line class
    #    feature) between the first two active accounts in the sample chart.
    accts = (
        (await s.qb_query_all("SELECT * FROM Account WHERE Active = true"))
        .get("QueryResponse", {})
        .get("Account", [])
    )
    names = [a["Name"] for a in accts if a.get("Name")][:2]
    if len(names) < 2:
        check("setup: two accounts available for the JE", False, str(names))
        return _report(failures)
    today = date.today().isoformat()
    je = await s.qb_create_journal_entry(
        today,
        json.dumps(
            [
                {
                    "account_name": names[0],
                    "amount": 1.0,
                    "type": "Debit",
                    "class_name": CLASS_NAME,
                    "description": "contract canary — auto-deleted",
                },
                {
                    "account_name": names[1],
                    "amount": 1.0,
                    "type": "Credit",
                    "class_name": CLASS_NAME,
                    "description": "contract canary — auto-deleted",
                },
            ]
        ),
    )
    check(
        "write path: class-tagged journal entry created",
        "Journal entry created" in je and CLASS_NAME in je,
        je,
    )
    je_id = (re.search(r"- ID: (\d+)", je) or [None, ""])[1]

    # 4. THE CONTRACT: QBO GeneralLedger honors klass_name — the Class column
    #    is present AND carries the class VALUE. This is exactly the behavior
    #    our offline fixtures assume; the hosted canary can't assert it because
    #    its realm has no class tracking.
    gl = await s.qb_general_ledger(today, today)
    check(
        "QBO CONTRACT: GeneralLedger returns the Class column with values",
        "Class" in gl and CLASS_NAME in gl,
        gl[:400],
    )

    # 5. The class-filtered register finds the tagged transaction.
    reg = await s.qb_transaction_list(today, today, class_name=CLASS_NAME)
    check(
        "register: class filter finds the tagged journal entry",
        "Journal Entry" in reg and CLASS_NAME in reg,
        reg[:400],
    )

    # 6. Cleanup — the sandbox stays tidy and re-runs stay deterministic.
    if je_id:
        gone = await s.qb_delete_journal_entry(je_id, confirm=True)
        check("cleanup: canary journal entry deleted", "elete" in gone, gone)

    # Persist the rotated refresh token for the next run (Intuit rotates them).
    if TOKEN_FILE and ctx.refresh_token and ctx.refresh_token != bootstrap_token:
        pathlib.Path(TOKEN_FILE).write_text(ctx.refresh_token)
        print("sandbox-canary: rotated refresh token saved for next run")
    elif TOKEN_FILE:
        pathlib.Path(TOKEN_FILE).write_text(ctx.refresh_token or bootstrap_token)

    return _report(failures)


def _report(failures: list[str]) -> int:
    print()
    if failures:
        print(f"SANDBOX CONTRACT DRIFT — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Full class-tracking contract holds against Intuit sandbox.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
