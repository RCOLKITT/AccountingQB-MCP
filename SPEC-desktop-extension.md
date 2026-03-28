# AccountingQB Desktop Extension Spec

**Status:** In Progress (Phase 4 Complete)
**Owner:** Ryan Colkitt
**Created:** 2026-03-28
**Last Updated:** 2026-03-28

---

## Executive Summary

Transform AccountingQB from a manual MCP server installation into a **one-click Desktop Extension** for Claude Desktop. This eliminates the 30+ minute technical setup process and opens the product to non-technical small business owners.

---

## Current State

### User Journey (Today)
```
Landing → Checkout → Success (get license key) → Setup Page
                                                      ↓
                                            Manual 4-step process:
                                            1. Save license key
                                            2. Create Intuit Developer app
                                            3. Run OAuth flow manually
                                            4. Edit JSON config file
```

### Pain Points
| Issue | Impact |
|-------|--------|
| Requires Intuit Developer account | 90% drop-off |
| Manual JSON config editing | Technical barrier |
| OAuth token management | Confusing for non-devs |
| No dependency bundling | Installation failures |
| No automatic updates | User must reinstall |

---

## Target State

### User Journey (After)
```
Landing → Checkout → Success Page
                         ↓
              "Install in Claude Desktop" button
                         ↓
              One-click .mcpb install
                         ↓
              Enter license key (in Claude)
                         ↓
              "Connect QuickBooks" → OAuth popup
                         ↓
              Done. Start chatting.
```

### Key Improvements
- [x] ~~Stripe checkout~~ (already done)
- [x] ~~License key generation~~ (already done)
- [x] ~~License email~~ (already done)
- [ ] Desktop Extension (.mcpb) package
- [ ] Built-in OAuth flow (no Intuit Developer account needed)
- [ ] Hosted OAuth callback endpoint
- [ ] Simplified success page with install button
- [ ] Account dashboard for subscription management

---

## Technical Architecture

### Desktop Extension Package Structure
```
accountingqb.mcpb/
├── manifest.json           # Extension metadata
├── server/
│   ├── index.js           # Bundled MCP server
│   └── node_modules/      # All dependencies included
├── icon.png               # Extension icon (128x128)
└── README.md              # Description for marketplace
```

### manifest.json
```json
{
  "name": "accountingqb",
  "display_name": "AccountingQB",
  "version": "1.0.0",
  "description": "91 AI tools connecting Claude to your QuickBooks Online",
  "author": "Vaspera Capital",
  "homepage": "https://accountingqb.com",
  "icon": "icon.png",
  "server": {
    "type": "node",
    "entry": "server/index.js"
  },
  "configuration": {
    "properties": {
      "licenseKey": {
        "type": "string",
        "description": "Your AccountingQB license key (starts with LK-)",
        "required": true
      }
    }
  },
  "oauth": {
    "provider": "intuit",
    "callback_url": "https://accountingqb.com/api/oauth/callback",
    "scopes": ["com.intuit.quickbooks.accounting"]
  }
}
```

### OAuth Flow (Hosted)
```
User clicks "Connect QuickBooks" in Claude
         ↓
Redirect to accountingqb.com/api/oauth/start?license_key=LK-xxx
         ↓
Redirect to Intuit OAuth
         ↓
User authorizes
         ↓
Callback to accountingqb.com/api/oauth/callback
         ↓
Store tokens in Supabase (encrypted, tied to license key)
         ↓
Redirect back to Claude with success
         ↓
MCP server fetches tokens from API on startup
```

### Token Storage
```sql
-- New table: oauth_tokens
CREATE TABLE oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_key TEXT REFERENCES licenses(key),
  realm_id TEXT NOT NULL,
  access_token TEXT NOT NULL,  -- encrypted
  refresh_token TEXT NOT NULL, -- encrypted
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(license_key, realm_id)
);
```

---

## Implementation Phases

### Phase 1: OAuth Infrastructure (Week 1) ✅
- [x] Create `oauth_tokens` table in Supabase
- [x] Build `/api/oauth/start` endpoint (initiates flow)
- [x] Build `/api/oauth/callback` endpoint (stores tokens)
- [x] Build `/api/oauth/token` endpoint (MCP server fetches tokens)
- [x] Add token refresh logic
- [x] Encrypt tokens at rest

**Deliverable:** Users can connect QuickBooks via web flow, tokens stored securely.

### Phase 2: MCP Server Refactor (Week 1-2) ✅
- [x] Modify MCP server to fetch tokens from API instead of local env
- [x] Add license key validation on startup
- [x] Handle token refresh automatically
- [x] Remove requirement for local Intuit credentials
- [x] Bundle all dependencies

**Deliverable:** MCP server works with hosted OAuth tokens.

### Phase 3: Desktop Extension Package (Week 2) ✅
- [x] Update manifest.json for hosted mode (license key only required)
- [x] Update pyproject.toml
- [x] Copy updated server to mcpb/src
- [x] Mark QuickBooks credentials as optional/advanced

**Deliverable:** Updated .mcpb package ready for hosted mode.

### Phase 4: Web Updates (Week 2-3) ✅
- [x] Update success page with "Install in Claude Desktop" button
- [x] Add "Connect QuickBooks" button (starts OAuth)
- [x] Create account dashboard page
  - [x] Show license key
  - [x] Show connected QuickBooks companies
  - [x] Show subscription status
  - [x] "Manage Billing" → Stripe portal
  - [x] "Disconnect QuickBooks" option
- [x] Fix setup page branding (Quarterback → AccountingQB)
- [x] Update license email with new instructions

**Deliverable:** Complete web experience for new flow.

### Phase 5: Marketplace Submission (Week 3)
- [ ] Create Anthropic developer account
- [ ] Submit extension to marketplace
- [x] Write marketplace description (README.md created)
- [x] Add extension icon (icon.png)
- [ ] Create demo video
- [ ] Respond to review feedback

**Deliverable:** Extension live in Claude Desktop marketplace.

### Phase 6: Migration & Launch (Week 3-4)
- [ ] Email existing users about new install method
- [ ] Deprecate old setup page (redirect to new flow)
- [ ] Monitor error rates
- [ ] Gather user feedback

**Deliverable:** All users on new flow.

---

## Database Schema Changes

```sql
-- oauth_tokens table (new)
CREATE TABLE oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_key TEXT NOT NULL REFERENCES licenses(key) ON DELETE CASCADE,
  realm_id TEXT NOT NULL,
  company_name TEXT,
  access_token_encrypted TEXT NOT NULL,
  refresh_token_encrypted TEXT NOT NULL,
  token_expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(license_key, realm_id)
);

-- Add index for token lookups
CREATE INDEX idx_oauth_tokens_license_key ON oauth_tokens(license_key);

-- Add connected_companies count to licenses (optional, for dashboard)
-- Could be computed from oauth_tokens table
```

---

## API Endpoints (New)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/oauth/start` | GET | Initiate QuickBooks OAuth flow |
| `/api/oauth/callback` | GET | Handle OAuth callback, store tokens |
| `/api/oauth/token` | POST | MCP server fetches tokens (authenticated) |
| `/api/oauth/refresh` | POST | Refresh expired tokens |
| `/api/oauth/revoke` | POST | Disconnect a QuickBooks company |
| `/api/account` | GET | Get account info for dashboard |

---

## Security Considerations

1. **Token Encryption**
   - Encrypt access/refresh tokens at rest using AES-256
   - Encryption key in environment variable, not in code

2. **API Authentication**
   - `/api/oauth/token` requires valid license key
   - Rate limit token requests
   - Log all token access for audit

3. **OAuth State**
   - Use cryptographic state parameter to prevent CSRF
   - State includes license key (encrypted)

4. **License Validation**
   - MCP server validates license on every startup
   - Invalid/expired licenses = read-only mode (25 free tools)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Setup completion rate | ~10% (estimated) | >80% |
| Time to first query | 30+ minutes | <5 minutes |
| Support tickets (setup) | High | Near zero |
| Trial → Paid conversion | Unknown | >20% |

---

## Open Questions

1. **Intuit App Approval**
   - Do we need production approval for hosted OAuth?
   - What's the review timeline?

2. **Multi-Company Support**
   - Allow connecting multiple QuickBooks companies?
   - How to handle in Claude (company switcher)?

3. **Token Security**
   - Should tokens be stored server-side or passed to local MCP?
   - Trade-off: convenience vs. zero-knowledge architecture

4. **Pricing Tiers**
   - Should "number of connected companies" be a tier differentiator?
   - Current: Solopreneur (1), Business (3), Firm (unlimited)

---

## Dependencies

- [ ] Anthropic MCPB CLI tool
- [ ] Intuit Developer production app approval
- [ ] Supabase encryption setup
- [ ] Desktop Extension marketplace access

---

## Timeline

| Week | Focus |
|------|-------|
| Week 1 | OAuth infrastructure + MCP server refactor |
| Week 2 | Desktop Extension package + Web updates |
| Week 3 | Testing + Marketplace submission |
| Week 4 | Migration + Launch |

**Target Launch:** 4 weeks from start

---

## Appendix

### Resources
- [Building Desktop Extensions with MCPB](https://support.claude.com/en/articles/12922929-building-desktop-extensions-with-mcpb)
- [MCPB GitHub Repository](https://github.com/modelcontextprotocol/mcpb)
- [Intuit OAuth Documentation](https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization)

### Related Files
- `web/src/app/api/oauth/` - OAuth endpoints
- `web/src/app/success/page.tsx` - Success page
- `web/src/app/setup/page.tsx` - Setup page (to be deprecated)
- `server/` - MCP server code (to be bundled)
