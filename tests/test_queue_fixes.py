"""QA-queue fixes: comparative-statement row ordering + default date params."""

import inspect

import accountingqb.server as s


def test_prior_only_line_merged_not_appended():
    cur = [
        "Sales",
        "Total Income",
        "Advertising",
        "Rent",
        "Total Expenses",
        "Net Income",
    ]
    prior = [
        "Sales",
        "Total Income",
        "Advertising",
        "Consulting",
        "Rent",
        "Total Expenses",
        "Net Income",
    ]
    merged = s._merge_line_order(cur, prior)
    # prior-only "Consulting" lands with its section siblings, before Net Income
    assert merged.index("Consulting") < merged.index("Net Income")
    assert (
        merged.index("Advertising")
        < merged.index("Consulting")
        < merged.index("Total Expenses")
    )


def test_date_helpers_default():
    s_, e_ = s._ytd_range()
    assert s_.endswith("-01-01") and len(e_) == 10  # Jan 1 .. today
    assert s._ytd_range("2025-03-01", "")[0] == "2025-03-01"
    assert len(s._as_of_or_today()) == 10


def test_report_tools_have_optional_dates():
    # empty calls used to fail -32602; date params now carry defaults
    for name in (
        "qb_balance_sheet",
        "qb_cash_flow",
        "qb_trial_balance",
        "qb_ar_aging",
        "qb_ap_aging",
        "qb_expense_summary",
        "qb_income_summary",
        "qb_sales_tax_summary",
        "qb_tax_summary",
        "qb_list_deposits",
        "qb_vendor_summary",
    ):
        fn = getattr(s, name)
        fn = getattr(fn, "__wrapped__", fn)
        params = inspect.signature(fn).parameters
        for p in params.values():
            if "date" in p.name:
                assert p.default == "", f"{name}.{p.name} still required"
