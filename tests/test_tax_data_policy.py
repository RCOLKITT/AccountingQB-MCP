"""L3 policy gate for the tax-data control plane.

Deterministic rules over the L2 registry (tax_tables.TABLES) and the L4
ledger (tax_ledger.jsonl). These run in the normal suite, so every commit
is gated: a rate can't ship without provenance, a ledger row, and sane
bounds — and every January 1 the freshness tripwire fails until the new
year's tables are loaded. That failure is intended.
"""

import ast
import datetime
import json
import pathlib

import pytest

import accountingqb.tax_tables as tt

SERVER_PATH = pathlib.Path(__file__).parent.parent / "mcpb/src/accountingqb/server.py"

YEAR_KEYED_ANNUAL = [
    name
    for name, e in tt.TABLES.items()
    if e.get("year_keyed") and e.get("review", "").startswith("annual-")
]


# ---------------------------------------------------------------------------
# freshness-current-year — fails every Jan 1 until new tables load (intended)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", YEAR_KEYED_ANNUAL)
def test_freshness_current_year(name):
    years = tt.table_year_keys(tt.TABLES[name])
    current = datetime.date.today().year
    assert current in years, (
        f"{name}: no figures loaded for {current} (covers {years[0]}-{years[-1]}). "
        f"Load the new year's values, ledger them, and bump TAX_DATA_VERSION."
    )


# ---------------------------------------------------------------------------
# provenance-complete
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(tt.TABLES))
def test_provenance_complete(name):
    e = tt.TABLES[name]
    for field in (
        "source",
        "source_url",
        "verified",
        "review",
        "jurisdiction",
        "kind",
        "description",
    ):
        assert e.get(field), f"{name}: missing provenance field '{field}'"
    assert e["kind"] in ("exact", "approximation", "stable_statute")
    assert e["review"] in ("annual-december", "annual-january", "legislative-watch")


# ---------------------------------------------------------------------------
# verified-recency — exact figures must be re-verified at least annually
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", [n for n, e in tt.TABLES.items() if e["kind"] == "exact"]
)
def test_verified_recency(name):
    verified = datetime.date.fromisoformat(tt.TABLES[name]["verified"])
    age = (datetime.date.today() - verified).days
    assert age < 400, (
        f"{name}: last verified {verified} ({age} days ago) — exact tables "
        f"must be re-verified within 400 days."
    )


# ---------------------------------------------------------------------------
# ledger-coverage — no ledger row, no rate ships
# ---------------------------------------------------------------------------


def _live_ledger_values():
    """Latest row per table:key (later rows supersede earlier)."""
    live = {}
    for row in tt.load_ledger():
        live[(row["table"], row["key"])] = row["value"]
    return live


@pytest.mark.parametrize("name", sorted(tt.TABLES))
def test_ledger_coverage(name):
    live = _live_ledger_values()
    for key, value in tt.iter_table_rows(name, tt.TABLES[name]):
        assert (
            name,
            key,
        ) in live, f"{name}:{key} has no ledger row — no ledger row, no rate ships."
        assert live[(name, key)] == tt.canonical_value(value), (
            f"{name}:{key} registry value differs from its latest ledger row — "
            f"append a superseding row before changing the registry."
        )


# ---------------------------------------------------------------------------
# ledger-integrity — append-only by math
# ---------------------------------------------------------------------------


def test_ledger_integrity():
    rows = tt.load_ledger()
    assert rows, "ledger is missing or empty"
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ledger ids"
    known = set(ids)
    for r in rows:
        if r.get("supersedes"):
            assert (
                r["supersedes"] in known
            ), f"{r['id']} supersedes unknown row {r['supersedes']}"
        datetime.date.fromisoformat(r["verified_date"])
        assert r["source"] and r["source_url"], f"{r['id']}: missing source"
    assert tt.verify_ledger_chain(rows), (
        "ledger hash chain does NOT verify — the file was edited in place. "
        "The ledger is append-only; restore it and append a superseding row."
    )


# ---------------------------------------------------------------------------
# sanity-bounds
# ---------------------------------------------------------------------------


def _leaf_numbers(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _leaf_numbers(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _leaf_numbers(v)
    elif isinstance(value, (int, float)):
        yield float(value)


@pytest.mark.parametrize("name", [n for n, e in tt.TABLES.items() if e.get("sanity")])
def test_sanity_bounds(name):
    e = tt.TABLES[name]
    s = e["sanity"]
    numbers = [x for x in _leaf_numbers(e["values"])]
    if "min" in s:
        assert all(x >= s["min"] for x in numbers), f"{name}: value below sanity min"
    if "max" in s:
        assert all(x <= s["max"] for x in numbers), f"{name}: value above sanity max"
    if "max_yoy_pct" in s:
        years = tt.table_year_keys(e)
        vals = (
            e["values"]
            if all(isinstance(k, int) for k in e["values"])
            else e["values"].get("params", {})
        )
        for a, b in zip(years, years[1:]):
            xa = max(_leaf_numbers(vals[a]))
            xb = max(_leaf_numbers(vals[b]))
            if xa:
                assert abs(xb - xa) / xa <= s["max_yoy_pct"], (
                    f"{name}: {a}->{b} moved more than "
                    f"{s['max_yoy_pct']:.0%} — verify against the source."
                )


def test_year_keys_plausible():
    for name, e in tt.TABLES.items():
        for y in tt.table_year_keys(e):
            assert 2000 <= y <= 2100, f"{name}: implausible year key {y}"


# ---------------------------------------------------------------------------
# version-consistency
# ---------------------------------------------------------------------------


def test_version_consistency():
    newest = max(e["verified"] for e in tt.TABLES.values())
    assert tt.TAX_DATA_VERIFIED == newest, (
        f"TAX_DATA_VERIFIED ({tt.TAX_DATA_VERIFIED}) != newest table "
        f"verification date ({newest})"
    )
    version_year = int(tt.TAX_DATA_VERSION.split(".")[0])
    assert any(
        version_year in tt.table_year_keys(e)
        for e in tt.TABLES.values()
        if e.get("year_keyed")
    ), "TAX_DATA_VERSION year not in any table"


# ---------------------------------------------------------------------------
# no-orphan-constants — year-keyed tax dicts must not regress into functions
# ---------------------------------------------------------------------------


def test_no_orphan_constants_in_server():
    tree = ast.parse(SERVER_PATH.read_text())
    offenders = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Dict):
                year_keys = sum(
                    1
                    for k in node.keys
                    if isinstance(k, ast.Constant)
                    and isinstance(k.value, int)
                    and 2000 <= k.value <= 2100
                )
                if year_keys >= 2:
                    offenders.append(f"{func.name}:{node.lineno}")
    assert not offenders, (
        f"year-keyed dict literals defined inside server.py functions "
        f"(move them to tax_tables.py): {offenders}"
    )


# ---------------------------------------------------------------------------
# Helper behavior (fail-closed semantics)
# ---------------------------------------------------------------------------


def test_tax_value_raises_for_future_year():
    with pytest.raises(tt.TaxDataError) as exc:
        tt.tax_value("SS_WAGE_BASE", 2091)
    assert "2091" in str(exc.value)
    assert "TAX_DATA v" in str(exc.value)


def test_tax_value_or_latest_notes_future_year():
    value, note = tt.tax_value_or_latest("SS_WAGE_BASE", 2091)
    latest = max(tt._SS_WAGE_BASE)
    assert value == tt._SS_WAGE_BASE[latest]
    assert f"using {latest} figures" in note and "2091" in note


def test_tax_value_or_latest_refuses_backward():
    with pytest.raises(tt.TaxDataError) as exc:
        tt.tax_value_or_latest("SS_WAGE_BASE", 2019)
    assert "never applied backward" in str(exc.value)


def test_terminal_value_honored():
    # TCJA phase-down is 0% for 2027+ by statute — not a fallback
    assert tt.tax_value("TCJA_PHASE_DOWN", 2030) == 0.0
    value, note = tt.tax_value_or_latest("TCJA_PHASE_DOWN", 2030)
    assert value == 0.0 and note == ""


# ---------------------------------------------------------------------------
# copy-count-consistency — marketing copy must match the shipped tool count
# (this drifted 91 -> 101 -> 104 across three releases before this gate)
# ---------------------------------------------------------------------------


def test_tool_count_copy_matches_manifest():
    import re

    root = pathlib.Path(__file__).parent.parent
    manifest = json.loads((root / "mcpb/manifest.json").read_text())
    count = len(manifest["tools"])

    pattern = re.compile(r"\b(\d{2,3}) (?:AI |QuickBooks )?[Tt]ools\b")
    offenders = []
    for path in (
        list((root / "web/src").rglob("*.ts*"))
        + list((root / "web/src").rglob("*.md"))
        + list((root / "cowork-plugin").rglob("*.json"))
        + list((root / "cowork-plugin").rglob("*.md"))
        + [
            root / "web/public/llms.txt",
            root / "README.md",
            root / "mcpb/manifest.json",
            root / "mcpb/src/accountingqb/__init__.py",
        ]
    ):
        if not path.is_file():
            continue
        for m in pattern.finditer(path.read_text(errors="ignore")):
            n = int(m.group(1))
            # GST34 "lines 101..." style references aren't tool counts
            if n != count and n >= 25 and "line" not in m.group(0).lower():
                offenders.append(f"{path.relative_to(root)}: '{m.group(0)}'")
    assert (
        not offenders
    ), f"copy says a tool count != manifest ({count} tools): {offenders}"
