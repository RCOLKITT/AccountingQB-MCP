#!/usr/bin/env python3
"""Generate web/src/lib/tax-changes.json from the Python tax-data control plane.

The /tax-changes page and the qb_tax_law_changes MCP tool must show the SAME
figures — this makes the Python registry (tax_tables.derive_tax_changes) the
single source of truth and emits a committed JSON artifact the Next.js page
reads. Re-run whenever tax_tables.py changes:

    python scripts/generate-tax-changes.py

Deterministic: same registry in -> same JSON out (CI can assert no drift).
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcpb" / "src"))

import accountingqb.tax_tables as tt  # noqa: E402

OUT = ROOT / "web" / "src" / "lib" / "tax-changes.json"


def main() -> None:
    changes = tt.derive_tax_changes(2025, 2026)
    payload = {
        "yearFrom": 2025,
        "yearTo": 2026,
        "taxDataVersion": tt.TAX_DATA_VERSION,
        "verified": tt.TAX_DATA_VERIFIED,
        "count": len(changes),
        "changes": changes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(changes)} changes "
          f"(TAX_DATA v{tt.TAX_DATA_VERSION}, verified {tt.TAX_DATA_VERIFIED})")


if __name__ == "__main__":
    main()
