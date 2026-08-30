#!/usr/bin/env python3
"""CA sandbox smoke test — runs the Canadian tool suite against a real
QuickBooks CA sandbox company, exercising region/province detection, the
GST/HST workpaper, T2125/CCA/T4A, instalments, and the report tools in
both the current and modernized (Reports v2, pre-Aug-31-2026) modes.

Usage (Development keys; refresh token + realm from the OAuth playground):

    doppler run -p accountingqb-mcp -c dev -- env \
        QB_REALM_ID=<ca-sandbox-realm> QB_REFRESH_TOKEN=<refresh-token> \
        python3 scripts/ca-smoke-test.py

QB_CLIENT_ID / QB_CLIENT_SECRET come from the Doppler dev config.
"""

import asyncio
import os
import sys
from datetime import date

os.environ.setdefault("QB_ENVIRONMENT", "sandbox")

MISSING = [
    v
    for v in ("QB_CLIENT_ID", "QB_CLIENT_SECRET", "QB_REALM_ID", "QB_REFRESH_TOKEN")
    if not os.environ.get(v)
]
if MISSING:
    sys.exit(
        f"Missing env: {', '.join(MISSING)} — see the usage note at the "
        f"top of this script."
    )

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcpb", "src"))
import accountingqb.server as qb  # noqa: E402

YEAR = date.today().year
Q_START = f"{YEAR}-01-01"
TODAY = date.today().strftime("%Y-%m-%d")

PASS, FAIL = [], []


async def check(name, coro, expect=None):
    """Run one tool; PASS if it returns a string without raising (and
    contains every `expect` substring when provided)."""
    try:
        out = await coro
        missing = [e for e in (expect or []) if e not in out]
        if missing:
            FAIL.append((name, f"missing {missing!r}", out))
        else:
            PASS.append(name)
            print(f"  PASS  {name}")
            return out
    except Exception as e:  # noqa: BLE001 — smoke test wants every failure
        FAIL.append((name, repr(e), ""))
    print(f"  FAIL  {name} — {FAIL[-1][1]}")
    return None


async def main():
    print(
        f"== CA sandbox smoke test — realm {os.environ['QB_REALM_ID']}, "
        f"{qb.QB_ENVIRONMENT} API ==\n"
    )

    print("-- Region & tax codes --")
    info = await check("qb_company_info", qb.qb_company_info())
    if info:
        print("        " + "\n        ".join(info.splitlines()[:6]))
    region = await qb._get_region()
    print(
        f"        detected: region={region['region']} "
        f"province={region.get('subdivision') or '(none)'} "
        f"currency={region['home_currency']}"
    )
    if region["region"] != "CA":
        print("  WARN  company is not detected as CA — is this the right realm?")
    await check("qb_list_tax_codes", qb.qb_list_tax_codes())
    await check("qb_list_tax_rates", qb.qb_list_tax_rates())

    print("\n-- Canadian tax suite --")
    await check(
        "qb_gst_hst_return",
        qb.qb_gst_hst_return(Q_START, TODAY),
        expect=["Line 109", "workpaper, not a filing"],
    )
    await check("qb_t2125_summary", qb.qb_t2125_summary(YEAR))
    await check(
        "qb_cca_schedule",
        qb.qb_cca_schedule('[{"name": "Laptop", "cost": 3000, "class": "50"}]', YEAR),
    )
    await check("qb_t4a_contractor_report", qb.qb_t4a_contractor_report(YEAR))
    await check("qb_estimate_instalments", qb.qb_estimate_instalments(YEAR))

    print("\n-- Reports: current vs modernized (v2) service --")
    for label, v2 in (("v1", False), ("v2 (_testing_migration)", True)):
        qb.QB_REPORTS_V2_TEST = v2
        print(f"  [{label}]")
        for name, coro in [
            ("qb_profit_loss", qb.qb_profit_loss(Q_START, TODAY)),
            ("qb_balance_sheet", qb.qb_balance_sheet(TODAY)),
            ("qb_trial_balance", qb.qb_trial_balance(Q_START, TODAY)),
            ("qb_general_ledger", qb.qb_general_ledger(Q_START, TODAY)),
        ]:
            await check(f"{name} [{label}]", coro)
    qb.QB_REPORTS_V2_TEST = False

    print(f"\n== {len(PASS)} passed, {len(FAIL)} failed ==")
    for name, why, out in FAIL:
        print(f"\nFAIL {name}: {why}")
        if out:
            print("  output head: " + out[:300].replace("\n", " | "))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
