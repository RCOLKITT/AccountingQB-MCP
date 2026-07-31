"""Year-over-year tax-change derivation + the qb_tax_law_changes tool."""

import asyncio

import accountingqb.tax_tables as tt
import accountingqb.server as qb_server


def test_derive_returns_sourced_changes():
    changes = tt.derive_tax_changes(2025, 2026)
    assert len(changes) >= 20
    for c in changes:
        # every change carries a source + link + verified date (CandidCost bar)
        for field in ("category", "item", "from", "to", "effective",
                      "source", "source_url", "verified"):
            assert c.get(field), f"change missing {field}: {c}"
        assert c["source_url"].startswith("http")
        assert c["from"] != c["to"]


def test_bonus_depreciation_shows_obbba_100_not_phasedown():
    changes = tt.derive_tax_changes(2025, 2026)
    bonus = [c for c in changes if "bonus depreciation" in c["item"].lower()]
    assert bonus, "bonus depreciation change should be surfaced"
    assert "100%" in bonus[0]["to"]
    # the misleading raw 40%->20% phase-down diff must NOT appear
    assert not any(c["to"].strip() == "20%" for c in changes)


def test_marquee_federal_and_canada_present():
    changes = tt.derive_tax_changes(2025, 2026)
    items = " ".join(c["item"] for c in changes)
    assert "Social Security wage base" in items
    assert "1099-NEC" in items
    assert "SALT" in items
    assert "CPP" in items  # Canadian coverage


def test_jurisdiction_filter():
    ca = tt.derive_tax_changes(2025, 2026, "Canada")
    assert ca and all(c["category"] == "Canada" for c in ca)
    us_state = tt.derive_tax_changes(2025, 2026, "US State")
    assert us_state and all(c["category"] == "US State" for c in us_state)


def test_state_deltas_backfilled():
    changes = tt.derive_tax_changes(2025, 2026, "US State")
    ga = [c for c in changes if c["item"].startswith("GA")]
    assert ga and ga[0]["from"] == "5.19%" and ga[0]["to"] == "4.99%"


def test_tool_output_has_disclaimer_and_links():
    out = asyncio.run(qb_server.qb_tax_law_changes())
    assert "Tax Law Changes — 2025 → 2026" in out
    assert "not tax, legal, or accounting" in out  # tax_data_footer disclaimer
    assert "](http" in out  # source links present
    assert "100%" in out    # bonus depreciation surfaced correctly


def test_tool_topic_and_jurisdiction_filters():
    ca = asyncio.run(qb_server.qb_tax_law_changes(jurisdiction="CA"))
    assert "Canada" in ca and "US Federal" not in ca
    dep = asyncio.run(qb_server.qb_tax_law_changes(topic="depreciation"))
    assert "depreciation" in dep.lower()
    none = asyncio.run(qb_server.qb_tax_law_changes(topic="zzz-no-such-topic"))
    assert "No tracked tax-law changes" in none


def test_tool_is_free_and_registered():
    assert "qb_tax_law_changes" in qb_server.FREE_TOOLS
    assert "qb_tax_law_changes" in qb_server.mcp._tool_manager._tools
