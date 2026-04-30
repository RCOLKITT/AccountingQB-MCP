# AccountingQB — QuickBooks for Claude

91 AI tools connecting Claude to your QuickBooks Online. Reports, reconciliation, tax prep, anomaly detection — all through natural conversation.

## Quick Setup

```sh
uvx accountingqb-setup --license-key YOUR_LICENSE_KEY
```

Get your license key at [accountingqb.com](https://accountingqb.com)

Then restart Claude Desktop (Cmd+Q on macOS, not just close the window).

### Troubleshooting

```sh
uvx accountingqb-setup --doctor
```

Runs 7 diagnostic checks: uv installed, config exists, valid JSON, AccountingQB configured, license valid, QuickBooks connected, server starts.

## Features

- **15 Reports & Analysis** — P&L, Balance Sheet, Cash Flow, Trial Balance, AR/AP Aging, and more
- **9 Tax Prep Tools** — Schedule C, deduction finder, quarterly estimates, 1099 reporting, depreciation
- **15 Create & Write Tools** — Invoices, expenses, bills, journal entries, deposits, transfers
- **8 Smart Bookkeeping** — Auto-categorization, duplicate detection, anomaly flagging, unknown vendor cleanup
- **4 Cash Flow Tools** — Runway calculator, burn rate, cash flow forecasting

## Example Prompts

- "What's my P&L for this quarter?"
- "Show me my burn rate and runway"
- "Generate my Schedule C for tax prep"
- "Find any duplicate transactions from last month"
- "Create an invoice for Acme Corp for $5,000"
- "Run my month-end close checklist"

## Privacy

Your QuickBooks data never touches our servers. All financial queries go directly from Claude to QuickBooks.

We only store:
- Your license key (for validation)
- OAuth tokens (encrypted, for QuickBooks connectivity)
- Anonymous usage metrics

Full privacy policy: [accountingqb.com/privacy](https://accountingqb.com/privacy)

## Pricing

- **Solopreneur** — $39/mo (2 companies)
- **Business** — $99/mo (10 companies)
- **Firm** — $299/mo (unlimited companies)

All plans include a 14-day free trial.

## Support

- Email: support@accountingqb.com
- Website: [accountingqb.com](https://accountingqb.com)

---

Built by [Vaspera Capital](https://vasperacapital.com)
