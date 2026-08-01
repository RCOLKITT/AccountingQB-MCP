# Common Issues & FAQ

## Installation Issues

### Tools not appearing in Claude Desktop
1. Make sure you saved the config file
2. Completely quit Claude Desktop (not just close the window)
3. Reopen Claude Desktop
4. Check that JSON is valid at jsonlint.com
5. Verify license key is correct (starts with LK-)

### "uvx not found" error
The uv package manager needs to be installed:
- **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows:** `winget install astral-sh.uv`

Then restart your terminal AND Claude Desktop.

Alternatively: install the one-file desktop extension (.mcpb) from your dashboard — no uv needed — or skip installs entirely with the remote connector.

### Config file location
- **macOS:** ~/Library/Application Support/Claude/claude_desktop_config.json
- **Windows:** %APPDATA%\Claude\claude_desktop_config.json
- **Linux:** ~/.config/Claude/claude_desktop_config.json

### JSON syntax errors
Common mistakes:
- Missing commas between entries
- Extra comma after last entry
- Single quotes instead of double quotes
- Missing closing braces

Use jsonlint.com to validate.

---

## QuickBooks Connection Issues

### "401 Unauthorized" error
Your OAuth token has expired.
**Fix:** First ask Claude to "refresh the QuickBooks connection" (`qb_refresh_connection`) — this resolves most expiries instantly without reconnecting. If that doesn't work, go to https://accountingqb.com/dashboard and click "Connect QuickBooks" to reauthorize.

### "Company not found" error
The company ID doesn't match.
**Fix:** Disconnect the company in your dashboard and reconnect.

### OAuth popup closes without completing
1. Disable popup blockers for accountingqb.com
2. Try in incognito/private window
3. Check you're using the correct QuickBooks account

### Sandbox vs Production data
If you see test/fake data:
- You may be connected to Intuit's sandbox
- Reconnect your QuickBooks company

---

## License & Account Issues

### License key not working
- Make sure the key starts with LK-
- Check for extra spaces when copying
- Verify your trial hasn't expired (14 days)
- Contact support@vasperacapital.com

### Forgot my license key
Go to https://accountingqb.com/dashboard and enter the email you used to purchase. Your key will be displayed.

### Trial expired
After 14 days, you keep access to 25 essential read-only tools for free. To unlock all 119 tools, choose a paid plan.

### How to cancel subscription
1. Go to https://accountingqb.com/dashboard
2. Click "Manage Subscription" or "Cancel Subscription"
3. Follow the prompts in the billing portal

No contracts, no cancellation fees.

---

## Usage Issues

### Getting rate limited
If you're making many requests quickly, you may hit rate limits. Wait a moment and try again.

### Tool returns an error
1. Check your QuickBooks connection is active
2. Verify you have permission in QuickBooks for that action
3. For write operations, check your tier allows it

### Wrong company data
If you have multiple companies connected, ask Claude: "Switch to [company name]"

---

## Frequently Asked Questions

### Is my financial data safe?
Yes. With the local extension or self-hosted setup, AccountingQB runs entirely on your machine — data flows directly between your computer and QuickBooks and never touches our servers. With the hosted remote connector, data passes through our service per-request but is never stored, logged, or used for analytics (zero retention). Either way, we never store your books.

### Do I need to know how to code?
No. Install the extension, connect your QuickBooks, and ask questions in plain English.

### What happens after the 14-day trial?
You keep 25 essential read-only tools free. For all 119 tools including writes and tax prep, choose a paid plan.

### Does this work with QuickBooks Desktop?
AccountingQB currently supports QuickBooks Online only. Desktop support is on our roadmap.

### What Claude apps does this work with?
Claude on the web, desktop, and mobile via the remote connector (add it as a custom connector), Claude Desktop via the MCP extension, Cowork via our plugin, and any app that supports MCP servers.

### Can I use multiple QuickBooks companies?
Yes, depending on your plan:
- Solopreneur: 1 company
- Business: 3 companies
- Firm: Unlimited

---

## Need More Help?

Email support@vasperacapital.com with:
- Your license key
- Description of the issue
- Any error messages you're seeing

We typically respond within 24 hours.

## How do I export the CPA workbook?

Open the dashboard (say "open accountingqb"), go to the Workbook tab, pick the period (prior year or year-to-date), fill in the Tax Organizer page, and click "Export workbook". Claude runs every section fresh and produces an Excel workbook (or CSV bundle) named AccountingQB-Workbook-<Company>-<Period>. Every sheet carries a provenance row showing the source tool, pull time, and period.
