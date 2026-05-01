---
name: accountingqb-dashboard
description: Renders the AccountingQB living dashboard artifact in the user's Cowork sidebar — a rich, persistent UI for QuickBooks data with tabs for P&L, cash flow, receivables, payables, transactions, taxes, and books health, plus an "Ask AccountingQB" chat panel powered by sample() and sendPrompt(). Use this skill when the user says "open accountingqb", "show me my dashboard", "open my books", "accountingqb dashboard", "what's my financial picture", "how are my books doing", or any general invocation that wants a visual overview rather than a single report. Also use when the user says "refresh dashboard" or "reload my books".
---

# AccountingQB Dashboard

You render the AccountingQB living dashboard artifact — a single Cowork artifact that consolidates P&L, cash flow, receivables, payables, transactions, tax estimation, and books-health into one persistent view. The artifact is interactive: tabs are clickable, period selectors trigger re-fetches via `window.cowork.callMcpTool()`, and the Ask AccountingQB chat panel handles natural-language Q&A and action commands.

## When to render the artifact

Trigger on any of:
- "open accountingqb" / "show me my dashboard" / "open my books"
- "what's my financial picture" / "how are my books doing"
- "accountingqb dashboard" / "refresh dashboard"
- Any invocation where the user wants a visual overview rather than a single specific report

## How to render

1. Read the artifact template from `references/artifact-template.html`.
2. Pull a starter snapshot of QB data using these tools in parallel:
   - `qb_company_info`
   - `qb_profit_loss` for current month-to-date and year-to-date
   - `qb_runway_calculator`
   - `qb_monthly_burn_rate` with `months_back: 6`
   - `qb_account_balance` for primary checking
   - `qb_uncategorized_transactions` (last 30 days)
3. Pass that snapshot as `window.HEARTH_DATA` (yes, the artifact uses the same global name as Hearth — the artifact ID keeps them separate) injected into the template.
4. Call `mcp__cowork__create_artifact` (or `update_artifact` if `accountingqb-dashboard` already exists) with the populated HTML.
5. Tell the user: *"Your AccountingQB dashboard is open in the sidebar."* — one short sentence. Do not narrate the dashboard contents.

## How the artifact behaves

- **Live data fetching**: each tab calls `window.cowork.callMcpTool('mcp__accountingqb__qb_*', {...})` directly to fetch fresh data on click. The skill's only job at render time is the initial snapshot.
- **Markdown rendering**: QuickBooks MCP tools return markdown strings. The artifact has an inline markdown parser that renders these natively. No client-side parsing of numbers is needed — let the markdown be the source of truth.
- **Period selector**: P&L and Cash Flow tabs have day/week/month/quarter/half/year selectors that call `qb_profit_loss` or `qb_cash_flow` with the appropriate date range.
- **Ask AccountingQB chat panel**: same intent-router pattern as Hearth's chat panel. Quick lookups go to `window.cowork.sample()`. Action commands (create invoice, reclassify transaction, etc.) route to `sendPrompt()` which fires the existing AccountingQB skills.
- **Reload button**: the artifact's view header has a built-in Reload button. Each reload re-runs all `callMcpTool` calls to refresh.

## When the user asks for a specific report inside the chat panel

The `accountingqb-accounting`, `accountingqb-bookkeeping`, and `accountingqb-tax-prep` skills already handle these. The dashboard skill is the rendering layer; the existing skills are the action layer. When chat panel routes to `sendPrompt()`, the appropriate sibling skill picks it up.

## Sister product

This artifact is a sibling to the Hearth artifact (personal budget app). They share design DNA but use distinct palettes — Hearth uses navy + amber + cream (warm, household), AccountingQB uses deep teal + emerald + cream (professional, fiscal). Both are Vaspera Capital products.
