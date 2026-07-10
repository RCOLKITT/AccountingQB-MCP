# QuickBooks OAuth & Connection

## Connecting Your QuickBooks Company

1. Go to https://accountingqb.com/dashboard
2. Enter your license key (or sign in with email)
3. Click "Connect QuickBooks"
4. Sign in to your QuickBooks account when prompted
5. Select the company you want to connect
6. Click "Authorize"

You'll be redirected back to your dashboard showing the connected company.

## Multiple Companies

You can connect multiple QuickBooks companies to a single license (up to the limit for your plan):
- Solopreneur: 1 company
- Business: 3 companies
- Firm: Unlimited companies

To switch between companies, ask Claude: "Switch to [company name]"

## Token Refresh

AccountingQB handles token refresh automatically. You don't need to do anything.

However, if you don't use AccountingQB for 100+ days, your connection may expire (this is an Intuit policy).

**If expired:** Click "Connect QuickBooks" again in your dashboard to reauthorize.

---

## Common OAuth Issues

### OAuth window closes without completing
1. Check if a popup blocker is active - disable it for accountingqb.com
2. Try in an incognito/private window
3. Make sure you're using the correct QuickBooks account

### "401 Unauthorized" error in Claude
Your token may have expired.
**Fix:** Go to https://accountingqb.com/dashboard and click "Connect QuickBooks" to reauthorize.

### "Company not found" error
The company ID in your connection doesn't match.
**Fix:** Disconnect the company in your dashboard and reconnect.

### "Access denied" from QuickBooks
Your QuickBooks account may not have permission to authorize third-party apps.
**Fix:** Contact your QuickBooks admin to grant access, or use an admin account.

### Sandbox vs Production
If you're seeing test data in Claude:
- Your connection may be pointing to Intuit's sandbox environment
- Reconnect your QuickBooks company to use production data

## Security

- OAuth tokens are stored securely and encrypted
- With the local extension, data flows directly between your machine and QuickBooks — it never passes through AccountingQB servers (zero-knowledge design)
- With the hosted connector, data passes through our service per-request but is never stored (zero retention)
- Tokens automatically rotate for security
