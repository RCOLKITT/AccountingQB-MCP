# AccountingQB-MCP

The most comprehensive QuickBooks Online MCP server for Claude. Built for sole proprietors and small businesses who want to manage their books, run reports, and prep taxes through natural conversation.

**119 tools** covering transactions, reports, tax prep (US **and** Canada), reconciliation, smart bookkeeping, 1099/T4A reporting, GST/HST returns, anomaly detection, credit memos, vendor credits, cash flow forecasting, and profit margin analysis — all from Claude Desktop. Includes a **CPA Workbook**: a 15-page year-end binder (comparative statements, reconciliation tie-outs, tax payments made, owner's draws, tax organizer) exported to Excel for your accountant.

**Canada support:** works with Canadian QuickBooks Online companies out of the box — the server auto-detects the company's tax edition, applies sales tax codes (GST/HST/PST) on created transactions, and ships a full Canadian tax suite: GST/HST (GST34) return workpapers with the 50% meals ITC restriction, T2125 line mapping, CCA schedules (half-year rule + Accelerated Investment Incentive), T4A/T5018 contractor reporting, and CRA instalment + CPP estimates. Multicurrency companies see per-transaction currency and exchange rates.

> Built by [Vaspera Capital](https://vasperacapital.com) — because QuickBooks deserved a real MCP server.

---

## Quick Start

### Prerequisites

- Python 3.10+
- A QuickBooks Online account (any plan)
- Claude Desktop
- An Intuit Developer account ([free signup](https://developer.intuit.com))

### 1. Clone and Install

```bash
git clone https://github.com/RCOLKITT/AccountingQB-MCP.git
cd AccountingQB-MCP
pip install -r requirements.txt
```

### 2. Create Your Intuit Developer App

1. Go to [developer.intuit.com](https://developer.intuit.com) and sign in
2. Click **Create an App** → select **QuickBooks Online and Payments**
3. Under **Redirect URIs**, add: `http://localhost:8080/callback`
4. Copy your **Client ID** and **Client Secret**

### 3. Run Setup

```bash
python setup.py
```

The setup wizard will:
- Ask for your Client ID and Client Secret
- Open your browser to authorize access to your QuickBooks company
- Catch the OAuth callback automatically
- Write your Claude Desktop configuration
- Verify the connection works

That's it. Restart Claude Desktop and you're connected.

### Manual Configuration (Advanced)

If you prefer to configure manually, add this to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "accountingqb": {
      "command": "python3",
      "args": ["/path/to/AccountingQB-MCP/server.py"],
      "env": {
        "QB_CLIENT_ID": "your_client_id",
        "QB_CLIENT_SECRET": "your_client_secret",
        "QB_REALM_ID": "your_company_id",
        "QB_REFRESH_TOKEN": "your_refresh_token",
        "QB_ENVIRONMENT": "production"
      }
    }
  }
}
```

To get your refresh token manually, use the [Intuit OAuth Playground](https://developer.intuit.com/app/developer/playground).

---

## Tools (113)

### Company & Entities

| Tool | Description |
|------|-------------|
| `qb_company_info` | Company name, EIN, address, fiscal year |
| `qb_list_accounts` | Full chart of accounts with balances |
| `qb_list_vendors` | Search vendors/suppliers |
| `qb_list_customers` | Search customers |
| `qb_list_items` | Products and services |
| `qb_create_vendor` | Create a new vendor |
| `qb_create_customer` | Create a new customer |
| `qb_update_vendor` | Update vendor details (email, phone, address) |
| `qb_update_customer` | Update customer details (email, phone, address) |
| `qb_create_account` | Add an account to chart of accounts |
| `qb_create_sub_account` | Create a sub-account under a parent |
| `qb_inactivate_account` | Hide unused accounts |

### Transactions

| Tool | Description |
|------|-------------|
| `qb_list_transactions` | Purchases/expenses with filters |
| `qb_list_deposits` | Income and owner investments |
| `qb_list_transfers` | Account-to-account transfers |
| `qb_list_journal_entries` | Adjustments and reclassifications |
| `qb_list_journal_entries_by_memo` | Search JEs by memo text |
| `qb_list_bills` | Accounts payable |
| `qb_list_bill_payments` | Bill payments |
| `qb_list_sales_receipts` | Direct sales |
| `qb_list_payments` | Customer payments received |
| `qb_list_invoices` | Invoices with status filter |
| `qb_list_credit_memos` | Customer credit memos/refunds |
| `qb_list_vendor_credits` | Vendor credits received |
| `qb_list_estimates` | Estimates/quotes with status filter |
| `qb_search_transactions` | Search across ALL transaction types |
| `qb_list_recurring_transactions` | Recurring templates and schedules |
| `qb_transaction_detail` | Full detail for any single transaction |
| `qb_account_transactions` | All transactions hitting a specific account |

### Create & Modify

| Tool | Description |
|------|-------------|
| `qb_create_expense` | Record a purchase/expense |
| `qb_create_invoice` | Create a customer invoice |
| `qb_create_bill` | Create a vendor bill |
| `qb_create_estimate` | Create a customer estimate/quote |
| `qb_create_journal_entry` | Record adjustments |
| `qb_create_deposit` | Record a bank deposit |
| `qb_create_transfer` | Transfer between accounts |
| `qb_create_credit_memo` | Issue a customer credit memo |
| `qb_create_vendor_credit` | Record a vendor credit |
| `qb_convert_estimate_to_invoice` | Convert an estimate into an invoice |
| `qb_record_bill_payment` | Record payment on a vendor bill |
| `qb_record_invoice_payment` | Record customer payment on invoice |
| `qb_update_transaction` | Update any transaction |
| `qb_void_transaction` | Void a transaction |
| `qb_delete_transaction` | Delete a transaction permanently |
| `qb_delete_journal_entry` | Permanently delete a JE |
| `qb_reclassify_transaction` | Move a transaction to a different account |
| `qb_bulk_update_vendor` | Bulk-assign vendor to multiple transactions |
| `qb_bulk_update_vendors_multi` | Bulk-assign multiple vendors in one call |
| `qb_batch_create_expenses` | Bulk expense import |
| `qb_batch_create_bills` | Bulk bill import |
| `qb_batch_create_journal_entries` | Bulk JE import |

### Reports & Analysis

| Tool | Description |
|------|-------------|
| `qb_profit_loss` | P&L by total, month, quarter, or year |
| `qb_profit_loss_detail` | P&L drill-down — every transaction behind each line, by account |
| `qb_profit_loss_by_class` | P&L by department/class |
| `qb_balance_sheet` | Balance sheet as of any date |
| `qb_sales_by_customer` | Total sales (income) by customer |
| `qb_sales_by_product` | Sales by product/service — quantity and amount |
| `qb_transaction_list` | Flexible transaction register for a date range |
| `qb_customer_balance_detail` | Open invoices per customer with line detail (AR drill-down) |
| `qb_vendor_balance_detail` | Open bills per vendor with line detail (AP drill-down) |
| `qb_cash_flow` | Statement of cash flows |
| `qb_cash_flow_forecast` | Multi-period cash flow projections |
| `qb_general_ledger` | All transactions by account |
| `qb_trial_balance` | Verify books are balanced |
| `qb_ar_aging` | What customers owe you |
| `qb_ap_aging` | What you owe vendors |
| `qb_expense_summary` | Expenses by category |
| `qb_income_summary` | Income by source |
| `qb_sales_tax_summary` | Sales tax collected by jurisdiction |
| `qb_sales_tax_nexus` | Economic-nexus screen — sales by ship-to state vs each state's sourced Wayfair threshold + liability by state |
| `qb_compare_periods` | Side-by-side period comparison |
| `qb_vendor_summary` | Top vendors by spend |
| `qb_profit_margin_analysis` | Profit margins by customer or item |
| `qb_budget_vs_actual` | Compare budget to actual spending |
| `qb_anomaly_detection` | Statistical anomaly and fraud detection |

### Tax Preparation

| Tool | Description |
|------|-------------|
| `qb_tax_summary` | Expenses mapped to Schedule C lines |
| `qb_schedule_c` | Full IRS Schedule C line-by-line |
| `qb_schedule_c_detailed` | Granular Schedule C with QB account detail |
| `qb_estimate_quarterly_tax` | Federal + state estimated taxes |
| `qb_deduction_finder` | Find commonly missed deductions |
| `qb_depreciation_schedule` | Section 179 and MACRS schedules |
| `qb_1099_contractor_report` | 1099-NEC contractor reporting with TIN/address validation |
| `qb_home_office_calculator` | Form 8829 home office deduction calculator |
| `qb_vehicle_depreciation_calculator` | Vehicle depreciation with business use % |
| `qb_payroll_checklist` | Payroll boundary checklist — wages/liability signals + W-2/1099, 941/940 items to hand your CPA |

### Canadian Tax (GST/HST, T2125)

| Tool | Description |
|------|-------------|
| `qb_gst_hst_return` | GST34 return workpaper — lines 101/103/105/106/108/109 with 50% meals ITC restriction, TaxSummary report, tax payments, and Quick Method note |
| `qb_t2125_summary` | CRA T2125 line-by-line mapping (8521 Advertising, 8523 Meals at 50%, 8910 Rent, ...) |
| `qb_cca_schedule` | Capital Cost Allowance by class — half-year rule, Accelerated Investment Incentive, Class 10.1/54 ceilings |
| `qb_t4a_contractor_report` | T4A box 048 contractor reporting with BN/address validation (T5018 note for construction) |
| `qb_estimate_instalments` | CRA instalments (Mar/Jun/Sep/Dec 15) + exact CPP/CPP2, with approximate federal/provincial tax |
| `qb_list_tax_codes` | Sales tax codes (name, combined rate, agency) — pass as `tax_code=` to create tools |
| `qb_list_tax_rates` | Individual sales tax rates and agencies |

### Smart Features

| Tool | Description |
|------|-------------|
| `qb_uncategorized_transactions` | Find uncategorized transactions |
| `qb_find_duplicates` | Detect potential duplicates |
| `qb_auto_categorize_suggestions` | AI-suggested categories based on vendor history |
| `qb_monthly_burn_rate` | Monthly expense trends |
| `qb_runway_calculator` | Months of cash runway |
| `qb_fiscal_year_close_checklist` | Year-end close readiness check |
| `qb_books_health_audit` | Comprehensive books health audit |
| `qb_month_end_close` | Month-end close checklist with status checks |
| `qb_unknown_vendor_report` | Find transactions with missing vendor names |

### Reconciliation & Attachments

| Tool | Description |
|------|-------------|
| `qb_reconcile_invoices` | Match invoices against QB transactions |
| `qb_match_invoices_to_transactions` | Fuzzy-match with tolerance |
| `qb_upload_receipt` | Attach receipts to transactions |
| `qb_list_attachments` | List attached documents |
| `qb_missing_receipts` | Expenses ≥ threshold (default $75) with no receipt attached — IRS substantiation gap |
| `qb_change_audit_trail` | What changed since a date — created / updated / **deleted** transactions (QuickBooks CDC) |
| `qb_bank_reconciliation` | Tie a bank/credit-card statement CSV to the books — matched / missing / uncleared |
| `qb_account_balance` | Check any account balance |

### Connection & Multi-Company

| Tool | Description |
|------|-------------|
| `qb_list_companies` | List all connected QuickBooks companies |
| `qb_switch_company` | Switch to a different company |
| `qb_refresh_connection` | Refresh connection to AccountingQB |

---

## Usage Examples

Once connected, just ask Claude naturally:

- *"What's my P&L for 2025?"*
- *"Show me all expenses over $500 from last month"*
- *"Create an expense for $49.99 to GitHub for software subscriptions"*
- *"Run my Schedule C for tax year 2025"*
- *"Find any uncategorized transactions"*
- *"What's my monthly burn rate?"*
- *"How much runway do I have?"*
- *"Compare Q1 vs Q2 profit and loss"*
- *"Find potential duplicate transactions"*
- *"What deductions am I missing?"*
- *"Generate my 1099 contractor report"*
- *"Run anomaly detection on last quarter's transactions"*
- *"Show my profit margins by customer"*
- *"Forecast my cash flow for the next 6 months"*
- *"Create a vendor credit for $200 to Amazon"*
- *"Convert estimate #1042 to an invoice"*
- *"Build my GST/HST return workpaper for Q2"* (Canada)
- *"Map my books to the T2125 and estimate my CRA instalments"* (Canada)

---

## Security

This server takes security seriously:

- **No credentials in code** — all secrets come from environment variables
- **OAuth 2.0** with automatic token rotation
- **Local-only OAuth flow** — the setup script runs a callback server on `127.0.0.1`
- **`.env` files are gitignored** and set to `chmod 600` (owner-only)
- **No data storage** — the server is stateless; it reads/writes to QuickBooks and nothing else
- **Refresh tokens rotate** — each token exchange returns a new refresh token
- **100-day expiry** — tokens expire after 100 days of inactivity (Intuit policy)

### Token Management

QuickBooks refresh tokens are valid for 100 days and rotate automatically on every use, so an active connection stays live indefinitely. If a connection does lapse (100+ days idle), reconnect based on how you run AccountingQB:

- **Hosted / managed (you have a license key):** In Claude, run `qb_refresh_connection` first — it silently re-establishes most expired connections with no browser step. If the connection is fully gone, reconnect at [accountingqb.com/dashboard](https://accountingqb.com/dashboard) → **Connect QuickBooks**, then run `qb_refresh_connection` again.
- **Self-hosted (your own Intuit app):** re-run `python setup.py` to re-authorize and rewrite your refresh token.

---

## Sandbox Mode

Test with Intuit's sandbox before connecting to production:

```bash
python setup.py --sandbox
```

This connects to `sandbox-quickbooks.api.intuit.com` with Intuit's test data. Switch to production when ready by running setup again without the flag.

---

## Troubleshooting

**"QuickBooks credentials not configured"**
Self-hosted: run `python setup.py` to configure credentials, or check your Claude Desktop config. Hosted/managed: set your `QB_LICENSE_KEY` and connect a company at [accountingqb.com/dashboard](https://accountingqb.com/dashboard).

**"401 Unauthorized"**
Your connection may have expired (100-day idle limit). Hosted/managed: run `qb_refresh_connection` first, then if needed reconnect at [accountingqb.com/dashboard](https://accountingqb.com/dashboard) → **Connect QuickBooks**. Self-hosted: re-run `python setup.py` to re-authorize.

**"Company not found"**
Check that your `QB_REALM_ID` matches the company you authorized. You can find it in the URL when logged into QuickBooks Online.

**Tools not appearing in Claude Desktop**
Restart Claude Desktop after running setup. Check that the `accountingqb` entry exists in your Claude Desktop config.

**Sandbox vs Production**
If you're seeing test data, check that `QB_ENVIRONMENT` is set to `"production"` in your config.

---

## Contributing

Issues and PRs welcome. If you're adding new tools, follow the existing pattern:
- Use flat parameters (not Pydantic models) for Claude Desktop compatibility
- Include descriptive docstrings
- Handle errors gracefully with actionable messages
- Add the tool to the README table

---

## License

**Proprietary — © Vaspera Capital LLC, all rights reserved.** The source is
publicly viewable for transparency and security review; it is **not** open
source. Use requires a paid license key. See [LICENSE](LICENSE).

Built by [Vaspera Capital](https://vasperacapital.com)
