# AccountingQB — Claude Cowork Plugin

101 QuickBooks Online tools + workflow skills for Claude Cowork, for US and
Canadian bookkeepers.

## What's inside

- **Connector** (`.mcp.json`): the AccountingQB remote MCP service at
  `https://mcp.accountingqb.com/mcp`. Installing the plugin prompts an OAuth
  sign-in with your accountingqb.com account — no local install, works in
  Cowork on desktop, web, and mobile.
- **Skills** (`skills/`):
  - `accountingqb-accounting` — everyday reports and transaction workflows
  - `accountingqb-bookkeeping` — cleanup, categorization, month-end close
  - `accountingqb-tax-prep` — region-aware tax prep (US Schedule C/1099;
    Canada GST/HST, T2125, CCA, T4A, instalments)
  - `accountingqb-dashboard` — living dashboard artifact in the sidebar

## Install (Cowork)

1. Claude Cowork → **Customize → Plugins → Browse**
2. Find **AccountingQB** (or install from this repo while unlisted)
3. Approve the connector OAuth prompt and pick your license
4. Ask: *"What's my P&L this quarter?"*

Prefer everything local? Use the desktop extension (.mcpb) from
accountingqb.com instead — your books never touch our servers.
