"""End-to-end assertions against the golden book (see golden_book.py). This is
the fixture the v3.16.2 audit recommended: a single realistic chart that carries
the structures which broke every release this week. If one of these fails, a real
book would have surfaced it before shipping."""

import asyncio

from unittest.mock import patch

from golden_book import patch_book, GOLDEN_ACCOUNTS, GOLDEN_PL

import accountingqb.server as s

HOME_10 = {"home_office": {"percentage": 0.10, "basis_note": "250/2500 sqft"}}


def _unwrap(tool):
    return getattr(tool, "__wrapped__", tool)


def _sched_c(profile=HOME_10):
    with patch_book(profile=profile):
        return asyncio.run(_unwrap(s.qb_schedule_c)("2025"))


def test_parent_posted_travel_residual_captured():
    """(1) The $200 posted directly to the Travel parent is not dropped — Line 24a
    is 2,200 (800 + 1,200 + 200), not 2,000."""
    out = _sched_c()
    assert "Line 24a" in out
    # Travel children + the parent residual all land on 24a (2,200); Cell phone
    # (mistyped Travel) adds 1,200 → 3,400 total on the line.
    assert "$3,400.00" in out


def test_duplicate_leaf_repairs_split_correctly():
    """(2) Standalone 'Repairs & maintenance' ($500) stays on Line 21; the
    Home office one ($400) is in the 8829 base — they do NOT merge."""
    out = _sched_c()
    assert "Line 21" in out and "$500.00" in out
    # home base = 400 + 1000 + 600 + 2000 = 4000 → Line 30 at 10% = 400
    assert "$4,000.00 × 10.00% business use" in out
    assert "Line 30 — Home office (Form 8829): $400.00" in out


def test_inactive_home_account_routes():
    """(3) The INACTIVE 'Mortgage interest (deleted)' ($2,000) is inside the home
    base, not deducted at 100% on an interest line."""
    out = _sched_c()
    assert "Line 16" not in out                    # not on the interest line
    # 2,000 is folded into the 4,000 home base (asserted above), not a standalone line
    assert "home expenses $4,000.00" in out


def test_home_personal_share_reconciles():
    """(5) Conservation holds: deductible + statutory + personal home share tie to
    the P&L. Personal home share = 4,000 × 90% = 3,600."""
    out = _sched_c()
    assert "3,600.00 personal home share" in out
    assert "Does not reconcile" not in out


def test_meals_50_percent():
    out = _sched_c()
    assert "× 50% (IRC §274(n)) = $500.00" in out   # 1,000 meals at 50%


def test_allocation_candidate_flagged_when_no_profile():
    """(7) With no allocation set, the mixed Internet & TV / Cell phone accounts
    are flagged as needing a business-use %, not silently deducted at 100%."""
    out = _sched_c(profile={})
    assert "Likely need a business-use %" in out


def test_owner_draws_excludes_system_equity_on_golden_book():
    """(6) Owner draws counts only real owner activity: +40,000 from Owner
    investments; Opening Balance Equity's −130,000 adjustment is excluded."""
    with patch_book():
        out = asyncio.run(_unwrap(s.qb_owner_draws)(2025))
    assert "Net owner activity: $40,000.00" in out
    assert "net contribution" in out
    assert "($130,000.00)" not in out
    assert "Excluded QuickBooks system equity" in out


def test_t2125_on_golden_book_routes_home_to_9945():
    """The same book through the Canadian path: home → line 9945, meals 50%,
    standalone repairs off the home base."""
    with patch_book(profile=HOME_10, region="CA"):
        out = asyncio.run(_unwrap(s.qb_t2125_summary)(2025))
    assert "Line 9945 — Business-use-of-home: $400.00" in out
    assert "$4,000.00 × 10.00%" in out
    assert "Line 30" not in out and "Form 8829" not in out


def test_golden_book_has_the_seven_structural_properties():
    """Guardrail: the fixture must keep the properties that make it valuable — if
    someone simplifies it away, this fails and explains why."""
    subs = [a["AccountSubType"] for a in GOLDEN_ACCOUNTS]
    fqns = [a["FullyQualifiedName"] for a in GOLDEN_ACCOUNTS]
    names = [a["Name"] for a in GOLDEN_ACCOUNTS]
    assert any(":" in f for f in fqns)                              # sub-accounts
    assert names.count("Repairs & maintenance") == 2               # duplicate leaf
    assert any(not a["Active"] for a in GOLDEN_ACCOUNTS)           # inactive
    assert any(st.endswith("HomeOffice") for st in subs)          # home subtype family
    assert "OpeningBalanceEquity" in subs and "RetainedEarnings" in subs   # system equity
    # name↔subtype disagreement: Cell phone typed Travel
    assert any(a["Name"] == "Cell phone" and a["AccountSubType"] == "Travel"
               for a in GOLDEN_ACCOUNTS)


def test_tax_summary_agrees_with_schedule_c_on_meals():
    """P0-1: qb_tax_summary used a name-only mapping and routed 'Travel meals' to
    Line 24a (no limit) while qb_schedule_c used the subtype → 24b at 50%. Now both
    run the same engine and must agree line-for-line, meals limited in both."""
    with patch_book(profile=HOME_10):
        sc = asyncio.run(_unwrap(s.qb_schedule_c)("2025"))
    with patch_book(profile=HOME_10):
        ts = asyncio.run(_unwrap(s.qb_tax_summary)(2025))
    # meals 50% in BOTH (golden book: Business meals 1,000 → 24b × 50% = 500);
    # previously tax_summary put them on 24a at 100% ($1,000), skipping §274(n).
    assert "Line 24b — Deductible meals: $500.00" in sc
    assert "Line 24b — Deductible meals: $500.00" in ts
    # both compute the same home-office Line 30 and the same Line 28 total
    assert "Line 30 — Home office (Form 8829): $400.00" in sc
    assert "Line 30 — Home office (Form 8829): $400.00" in ts
    sc28 = sc.split("Line 28 — Total expenses:")[1][:20]
    ts28 = ts.split("Line 28 — Total expenses:")[1][:20]
    assert sc28 == ts28
    # and tax_summary now HAS income + net (previously missing)
    assert "Line 7 — Gross income:" in ts and "Net profit" in ts


def test_tax_summary_respects_tax_year_param():
    """P1: passing tax_year must be honored, not silently discarded for YTD."""
    captured = {}

    async def fake_req(m, p, params=None, **k):
        captured["params"] = params
        return GOLDEN_PL

    async def fake_all(q, **k):
        return {"QueryResponse": {"Account": GOLDEN_ACCOUNTS}}

    async def fake_query(q):
        return {"QueryResponse": {"CompanyInfo": [{"CompanyName": "Golden Co", "Country": "US"}]}}

    async def fake_profile(y):
        return {}

    with patch.object(s, "qb_request", fake_req), \
            patch.object(s, "qb_query_all", fake_all), \
            patch.object(s, "qb_query", fake_query), \
            patch.object(s, "_get_allocation_profile", fake_profile):
        out = asyncio.run(_unwrap(s.qb_tax_summary)(2023))
    assert captured["params"]["start_date"] == "2023-01-01"
    assert captured["params"]["end_date"] == "2023-12-31"
    assert "2023-01-01 to 2023-12-31" in out


def _net_from(text, label):
    import re
    m = re.search(re.escape(label) + r"[^$]*(\$[\-()0-9,.]+)", text)
    return m.group(1) if m else None


def test_deduction_finder_net_matches_schedule_c():
    """The non-deductible items (charitable) must be EXCLUDED from Line 28 and the
    loss. qb_deduction_finder now shares _schedule_c_totals, so its Line 31 net
    must equal qb_schedule_c's — even on a book that HAS a non-deductible item
    (which is exactly the case that shipped wrong)."""
    with patch_book(profile=HOME_10):
        sc = asyncio.run(_unwrap(s.qb_schedule_c)("2025"))
    with patch_book(profile=HOME_10):
        df = asyncio.run(_unwrap(s.qb_deduction_finder)("2025"))
    sc_net = _net_from(sc, "Line 31 — Net profit (loss):")
    df_net = _net_from(df, "Net (Schedule C Line 31):")
    assert sc_net and df_net, (sc_net, df_net)
    assert sc_net == df_net, f"deduction_finder {df_net} != schedule_c {sc_net}"
    # charitable ($300) is NOT in the deductible-expenses figure
    assert "Charitable" not in df.split("Net (Schedule C Line 31)")[0].split(
        "Deductible expenses")[-1]


def test_golden_book_has_a_nondeductible_item():
    """Guardrail: the golden book MUST contain a non-deductible account, or the
    'nondeductible leaks into totals' class of bug is invisible to CI (which is
    why qb_deduction_finder's over-count shipped)."""
    from accountingqb.tax_tables import classify_account
    nondeduct = [a for a in GOLDEN_ACCOUNTS
                 if classify_account(a["Name"], a["AccountSubType"], "US")[0].startswith("NONDED")]
    assert nondeduct, "golden book needs a charitable/entertainment/etc. account"
