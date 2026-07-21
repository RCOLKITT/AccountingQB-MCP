---
name: accountingqb-dashboard
description: Renders the AccountingQB living dashboard artifact in the user's Cowork sidebar — a rich, persistent UI for QuickBooks data with tabs for P&L, cash flow, receivables, payables, transactions, taxes, and books health, plus an "Ask AccountingQB" chat panel. Use this skill when the user says "open accountingqb", "show me my dashboard", "open my books", "accountingqb dashboard", "what's my financial picture", "how are my books doing", or any general invocation that wants a visual overview rather than a single report. Also use when the user says "refresh dashboard" or "reload my books".
---

# AccountingQB Dashboard

You render the AccountingQB living dashboard artifact — a single Cowork artifact that consolidates P&L, cash flow, receivables, payables, transactions, tax estimation, and books-health into one persistent view.

## When to render the artifact

Trigger on any of:
- "open accountingqb" / "show me my dashboard" / "open my books"
- "what's my financial picture" / "how are my books doing"
- "accountingqb dashboard" / "refresh dashboard"
- Any invocation where the user wants a visual overview rather than a single specific report

## How to render

1. Read the artifact template from `references/artifact-template.html`.
2. Call `mcp__cowork__create_artifact` (or `update_artifact` if `accountingqb-dashboard` already exists) with the HTML template directly. **Do not pre-fetch any QB data** — the artifact handles connection checking and data loading automatically.
3. Tell the user: *"Your AccountingQB dashboard is open in the sidebar."* — one short sentence. Do not narrate the dashboard contents.

The artifact will:
- **Auto-detect connection status** and show a welcome/setup screen if QuickBooks isn't connected
- **Guide new users** through setup with clear steps (install, license, connect QB, add to Claude)
- **Load data automatically** once connected, showing KPIs, P&L, and books health

## How the artifact behaves

- **Connection check**: On load, the artifact tests the MCP connection. If not connected, it shows a friendly setup guide with step-by-step instructions. Users can click "Retry" after completing setup.
- **Live data fetching**: Each tab calls `window.cowork.callMcpTool()` directly to fetch fresh data on click.
- **Dynamic company name**: The company name is fetched from QuickBooks and displayed in the header.
- **Markdown rendering**: QuickBooks MCP tools return markdown strings. The artifact parses and renders tables, headers, and lists natively.
- **Period selector**: P&L and Cash Flow tabs have MTD/QTD/YTD/Prior Year selectors.
- **Ask AccountingQB chat panel**: Quick lookups go to `window.cowork.sample()`. Action commands (create invoice, reclassify transaction, etc.) route to `window.cowork.sendPrompt()` which fires the existing AccountingQB skills.

## When the user asks for a specific report inside the chat panel

The artifact also includes a **CPA Workbook** tab: a 12-page click-through year-end binder (cover, trial balance, statements, GL, region-aware tax mapping, contractors, sales tax, fixed assets, open items, notes) with a tie-out footer on every page and an Export button that routes to the `accountingqb-cpa-workbook` skill.

The `accountingqb-accounting`, `accountingqb-bookkeeping`, and `accountingqb-tax-prep`, and `accountingqb-cpa-workbook` skills already handle these. The dashboard skill is the rendering layer; the existing skills are the action layer. When the chat panel routes to `sendPrompt()`, the appropriate sibling skill picks it up.

## Sister product

This artifact is a sibling to the Hearth artifact (personal budget app). They share design DNA but use distinct palettes — Hearth uses navy + amber + cream (warm, household), AccountingQB uses deep teal + emerald + cream (professional, fiscal). Both are Vaspera Capital products.
