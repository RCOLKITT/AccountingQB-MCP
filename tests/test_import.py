"""Import smoke tests: the canonical server registers exactly 131 tools."""

EXPECTED_TOOL_COUNT = 131

SPOT_CHECK_TOOLS = [
    "qb_create_invoice",
    "qb_company_info",
    "qb_list_companies",
    "qb_switch_company",
    "qb_refresh_connection",
    "qb_profit_loss",
    "qb_upload_receipt",
    "qb_list_tax_codes",
    "qb_list_tax_rates",
    # Phase 5 — Canada tax suite
    "qb_gst_hst_return",
    "qb_t2125_summary",
    "qb_cca_schedule",
    "qb_t4a_contractor_report",
    "qb_estimate_instalments",
]


def _registered_tools(server) -> dict:
    return server.mcp._tool_manager._tools


def test_tool_count_is_108(server):
    assert len(_registered_tools(server)) == EXPECTED_TOOL_COUNT


def test_key_tools_present(server):
    tools = _registered_tools(server)
    for name in SPOT_CHECK_TOOLS:
        assert name in tools, f"expected tool {name} to be registered"


def test_import_does_not_enable_hosted_mode_without_license(server):
    # With no QB_LICENSE_KEY in the environment, the default context must be
    # self-hosted (and no hosted fetch should have happened at import).
    from accountingqb.context import _default_ctx

    assert _default_ctx.hosted_mode is False
    assert _default_ctx.hosted_loaded is False
