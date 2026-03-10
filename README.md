# AccountingQB-MCP

The most comprehensive QuickBooks Online MCP server for Claude. Built for sole proprietors and small businesses who want to manage their books, run reports, and prep taxes through natural conversation.

**58 tools** covering transactions, reports, tax prep, reconciliation, and smart bookkeeping — all from Claude Desktop.

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
    "quickbooks": {
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

## Tools (58)

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
| `qb_create_account` | Add an account to chart of accounts |
| `qb_inactivate_account` | Hide unused accounts |

### Transactions

| Tool | Description |
|------|-------------|
| `qb_list_transactions` | Purchases/expenses with filters |
| `qb_list_deposits` | Income and owner investments |
| `qb_list_transfers` | Account-to-account transfers |
| `qb_list_journal_entries` | Adjustments and reclassifications |
| `qb_list_bills` | Accounts payable |
| `qb_list_bill_payments` | Bill payments |
| `qb_list_sales_receipts` | Direct sales |
| `qb_list_payments` | Customer payments received |
| `qb_list_invoices` | Invoices with status filter |
| `qb_search_transactions` | Search across ALL transaction types |
| `qb_list_recurring_transactions` | Recurring templates and schedules |

### Create & Modify

| Tool | Description |
|------|-------------|
| `qb_create_expense` | Record a purchase/expense |
| `qb_create_invoice` | Create a customer invoice |
| `qb_create_bill` | Create a vendor bill |
| `qb_create_journal_entry` | Record adjustments |
| `qb_create_deposit` | Record a bank deposit |
| `qb_create_transfer` | Transfer between accounts |
| `qb_update_transaction` | Update any transaction |
| `qb_void_transaction` | Void a transaction |
| `qb_batch_create_expenses` | Bulk expense import |
| `qb_batch_create_bills` | Bulk bill import |

### Reports

| Tool | Description |
|------|-------------|
| `qb_profit_loss` | P&L by total, month, quarter, or year |
| `qb_profit_loss_by_class` | P&L by department/class |
| `qb_balance_sheet` | Balance sheet as of any date |
| `qb_cash_flow` | Statement of cash flows |
| `qb_general_ledger` | All transactions by account |
| `qb_trial_balance` | Verify books are balanced |
| `qb_ar_aging` | What customers owe you |
| `qb_ap_aging` | What you owe vendors |
| `qb_expense_summary` | Expenses by category |
| `qb_income_summary` | Income by source |
| `qb_compare_periods` | Side-by-side period comparison |
| `qb_vendor_summary` | Top vendors by spend |

### Tax Preparation

| Tool | Description |
|------|-------------|
| `qb_tax_summary` | Expenses mapped to Schedule C lines |
| `qb_schedule_c` | Full IRS Schedule C line-by-line |
| `qb_estimate_quarterly_tax` | Federal + state estimated taxes |
| `qb_deduction_finder` | Find commonly missed deductions |
| `qb_depreciation_schedule` | Section 179 and MACRS schedules |

### Smart Features

| Tool | Description |
|------|-------------|
| `qb_uncategorized_transactions` | Find uncategorized transactions |
| `qb_find_duplicates` | Detect potential duplicates |
| `qb_auto_categorize_suggestions` | AI-suggested categories based on vendor history |
| `qb_monthly_burn_rate` | Monthly expense trends |
| `qb_runway_calculator` | Months of cash runway |
| `qb_fiscal_year_close_checklist` | Year-end close readiness check |

### Reconciliation & Attachments

| Tool | Description |
|------|-------------|
| `qb_reconcile_invoices` | Match invoices against QB transactions |
| `qb_match_invoices_to_transactions` | Fuzzy-match with tolerance |
| `qb_upload_receipt` | Attach receipts to transactions |
| `qb_list_attachments` | List attached documents |
| `qb_account_balance` | Check any account balance |

---

## Usage Examples

Once connected, just ask Claude naturally:

- *"What's my P&L for 2024?"*
- *"Show me all expenses over $500 from last month"*
- *"Create an expense for $49.99 to GitHub for software subscriptions"*
- *"Run my Schedule C for tax year 2024"*
- *"Find any uncategorized transactions"*
- *"What's my monthly burn rate?"*
- *"How much runway do I have?"*
- *"Compare Q1 vs Q2 profit and loss"*
- *"Find potential duplicate transactions"*
- *"What deductions am I missing?"*

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

QuickBooks refresh tokens are valid for 100 days. The server automatically handles token refresh, but if your token expires (e.g., you don't use the server for 100+ days), re-run `python setup.py` to re-authorize.

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
Run `python setup.py` to configure credentials, or check your Claude Desktop config.

**"401 Unauthorized"**
Your refresh token may have expired (100-day limit). Run `python setup.py` to re-authorize.

**"Company not found"**
Check that your `QB_REALM_ID` matches the company you authorized. You can find it in the URL when logged into QuickBooks Online.

**Tools not appearing in Claude Desktop**
Restart Claude Desktop after running setup. Check that the `quickbooks` entry exists in your Claude Desktop config.

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

MIT — see [LICENSE](LICENSE)

Built by [Vaspera Capital](https://vasperacapital.com)
