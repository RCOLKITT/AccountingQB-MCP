#!/usr/bin/env python3
"""Append hash-chained ledger rows for any TABLES entry not yet in
tax_ledger.jsonl. Idempotent: re-running adds nothing if coverage is complete.
The ledger is append-only and hash-chained (see tax_tables.verify_ledger_chain);
this computes each new row's prev_hash off the running chain so the L3 integrity
gate stays green.

Usage: python3 scripts/append-tax-ledger.py [--dry-run]
"""
import hashlib
import json
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcpb" / "src"))
import accountingqb.tax_tables as tt  # noqa: E402

VERIFIED_BY = "ryan@vasperacapital.com (2026-08 taxonomy)"


def _canon(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def main(dry_run: bool = False) -> int:
    rows = tt.load_ledger()
    existing = {(r["table"], r["key"]) for r in rows}

    # running chain hash (matches verify_ledger_chain) + max global sequence
    prev = hashlib.sha256(tt._LEDGER_GENESIS_SEED.encode()).hexdigest()
    max_seq = 0
    for r in rows:
        prev = hashlib.sha256(_canon(r).encode()).hexdigest()
        seq = int(r["id"].rsplit("#", 1)[-1])
        max_seq = max(max_seq, seq)

    new_lines = []
    for name in tt.TABLES:
        entry = tt.TABLES[name]
        for key, value in tt.iter_table_rows(name, entry):
            if (name, key) in existing:
                continue
            max_seq += 1
            row = {
                "id": f"{name}:{key}#{max_seq}",
                "table": name,
                "key": key,
                "value": tt.canonical_value(value),
                "verified_date": entry["verified"],
                "verified_by": VERIFIED_BY,
                "source": entry["source"],
                "source_url": entry["source_url"],
                "jurisdiction": entry["jurisdiction"],
                "tax_data_version": tt.TAX_DATA_VERSION,
                "prev_hash": f"sha256:{prev}",
                "supersedes": None,
            }
            line = _canon(row)
            prev = hashlib.sha256(line.encode()).hexdigest()
            new_lines.append(line)
            print(f"+ {row['id']}")

    if not new_lines:
        print("ledger already complete — nothing to append")
        return 0
    if dry_run:
        print(f"[dry-run] would append {len(new_lines)} row(s)")
        return 0

    with tt.ledger_path().open("a") as f:
        for line in new_lines:
            f.write(line + "\n")
    assert tt.verify_ledger_chain(), "hash chain broke after append!"
    print(f"appended {len(new_lines)} row(s); chain verifies ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
