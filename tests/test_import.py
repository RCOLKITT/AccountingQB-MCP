"""Import smoke tests: the canonical server registers exactly 94 tools."""

EXPECTED_TOOL_COUNT = 94

SPOT_CHECK_TOOLS = [
    "qb_create_invoice",
    "qb_company_info",
    "qb_list_companies",
    "qb_switch_company",
    "qb_refresh_connection",
    "qb_profit_loss",
    "qb_upload_receipt",
]


def _registered_tools(server) -> dict:
    return server.mcp._tool_manager._tools


def test_tool_count_is_94(server):
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
