# Constitution — AccountingQB

Hard invariants for the AccountingQB platform (MCP servers, web/licensing app,
remote connector, plugin, and skills). These are not preferences — they are
rules that must never be violated. Several encode **legal and fiduciary
posture**: this product reads and *writes other people's books of record*.
Breaking these creates client-facing financial damage and regulatory exposure,
not just bugs. If you find yourself about to break one, stop and rethink.

**Supremacy:** This document governs all code, tools, prompts, skills, emails,
and data pipelines in this repository. It is referenced from CLAUDE.md and
loads in every session. Amendments bump `CONSTITUTION_VERSION`.

---

## Product Laws (highest severity)

### Workpapers, Never Filings. Math, Never Advice.

Every tax output (Schedule C, GST/HST return, T2125, CCA, 1099/T4A,
quarterly/instalment estimates) is a **workpaper**: it shows the numbers, the
mapping, and the method, and tells the user to verify before filing.

```python
# NEVER — filing-ready or advisory framing
return "Your GST/HST return is ready to file. You owe $4,310."
return "You should elect the Quick Method."

# ALWAYS — workpaper + verification pointer
return (... +
  "\n\n⚠️ This is a workpaper, not a filing. Verify against QuickBooks' "
  "Sales Tax Centre and confirm with your accountant before filing with CRA.")
```

- Banned framings in tool output about a user's situation: *you should, you
  must, we recommend, best for you, ready to file, guaranteed*. Allowed:
  *maps to, computes to, typically, eligible if, verify*.
- Estimates are labeled estimates. Approximate tables (tax brackets,
  provincial factors) say "approximate" in the output itself, not just in
  code comments.
- Deadlines and thresholds state the jurisdiction and year they apply to.

### Never Wrong-Jurisdiction Numbers

A US answer given to a Canadian company is not a degraded answer — it is a
**wrong** answer that looks right.

- Region detection (`_get_region`) gates every jurisdiction-specific tool.
  US-only tools refuse (with the CA alternative) for CA companies and vice
  versa. New tax tools ship region-gated or not at all.
- Never send `GlobalTaxCalculation`/injected `TaxCodeRef` to a US (AST)
  company; never post a CA sales/purchase transaction without line tax codes
  — fail fast with guidance *before* the API call.
- Tax code IDs, agency IDs, and account IDs are **per-company data**. Never
  hardcode them. Resolve by name at call time.
- Indeterminate region defaults to US **and says so** when it materially
  affects a tax output.

### Every Encoded Rate Has a Source and a Review Date

```python
# NEVER
CPP_RATE = 0.119  # "current rate"

# ALWAYS
# CPP self-employed base rate, 2026. Source: CRA "CPP contribution rates,
# maximums and exemptions" (announced 2025-11). Review: annually, December.
_CPP_PARAMS = {2026: {"rate": 0.119, "ymPE": 74_600, ...}}
```

- Statutory constants (CPP/YMPE, CCA ceilings, mileage rates, IRS/CRA dates,
  thresholds) live in named, year-keyed tables with a source comment and a
  review cadence (tracked in private-docs/OPS.md). No bare magic numbers in tax math.
- When a constant's year table lacks the requested year, the tool says which
  year's figures it used — it never silently reuses stale rates.

### Writes Are Sacred

These tools mutate a business's books of record.

- Every write tool carries an accurate `destructiveHint`/`readOnlyHint`
  annotation. A tool that can delete or void is destructive, full stop.
- No silent bulk mutation: batch tools report per-item success/failure;
  a failed item never aborts into a half-applied state without saying
  exactly what was and wasn't applied.
- Deletes/voids echo back what was deleted (type, id, amount, date) in the
  response so the conversation itself is a record.
- Skills instruct Claude to confirm details with the user before creating or
  modifying transactions. New skills inherit this rule.
- No write path may fabricate data to satisfy the API (no defaulting a tax
  code, account, or amount the user didn't specify — resolve or ask).

### Books Data Locality Is a Promise, Tiered and Honest

- **Local tier (.mcpb / self-hosted):** QuickBooks data flows device ↔ Intuit
  only. The vendor backend sees OAuth/licensing metadata, never books data.
  Nothing in the local server may POST books content to accountingqb.com —
  usage tracking sends tool *names* only.
- **Remote tier (mcp.accountingqb.com):** zero-retention pass-through. No
  books payloads in logs, no books data at rest, no analytics on books
  content. Marketing copy for each tier states that tier's truth; the local
  slogan is never applied to the remote tier.
- Support tooling and emails never include books data. License keys are
  masked in logs (`LK-…last4`); tokens are never logged at all.

---

## Auditability Invariants

### Every Consequential Action Leaves a Row

- The `event_logs` table is the platform audit trail: license issuance,
  linking, rotation, OAuth connect/refresh, campaign sends, webhook
  processing — success **and** failure, with typed `event_type`/`action`
  and a context payload. New endpoints that change state must log or they
  don't merge.
- Corrections are new rows; audit rows are never edited or deleted.
- QuickBooks writes are additionally auditable at the source: QBO's own
  audit log records the API user. Never impersonate, batch through a
  different company, or otherwise obscure which license performed a write.
- The remote connector attributes every request to a license (JWT claim) —
  anonymous writes are structurally impossible.

### Reconciliation Beats Assertion

- Tax workpapers cross-check against QuickBooks' own reports where the API
  provides one (e.g. TaxSummary vs. transaction-derived GST34 lines) and
  show both when they disagree — never pick one silently.
- Funnel/ops claims ("emails send", "connections work") are verified against
  live data (`email_schedules.sent_at`, `oauth_tokens`, Vercel logs), not
  assumed from code reading. That standard applies to future debugging too.

---

## Money & Data Invariants

- Money amounts pass through untouched as QBO provides them (decimal
  strings/numbers); never accumulate in binary floats for reported totals —
  round only at display, and label currency when multicurrency is enabled
  (`[USD @1.37]`).
- Suppression over fabrication: a report with missing data says what's
  missing ("3 transactions had no account ref — excluded") rather than
  absorbing it silently.
- Timestamps: timezone-aware UTC everywhere in Python (`datetime.now(timezone.utc)`);
  ISO 8601 at boundaries. Naive datetimes caused real bugs here — they are banned.
- Prohibited in our stores: full bank/account numbers, SSNs/SINs, uploaded
  documents. We hold OAuth tokens (encrypted at rest locally; rotated,
  hashed-or-locked server-side) and license/billing metadata — nothing else.

## Credential Invariants

- Intuit refresh tokens rotate on every use: the new token is persisted
  **before** the old one is considered consumed; concurrent refresh goes
  through the single-flight lock (`claim_token_refresh`). Never bypass it.
- Local token cache is encrypted (Fernet) and chmod-restricted; `.env` files
  are gitignored; secrets live in Doppler → Vercel/Fly, never in git, never
  in logs, never in error messages returned to the model.
- OAuth codes/refresh tokens in the AS are stored as hashes only; reuse of a
  rotated refresh token revokes the chain.

## MCP Invariants

- Zod/typed schemas on web endpoints; typed params + docstrings on every
  tool (docstrings are the model-facing contract — keep them accurate, keep
  jurisdiction claims accurate).
- `mcpb/manifest.json` tool count and schemas are generated
  (`scripts/generate-schemas.py`), never hand-edited into drift.
- Rate limits on public endpoints are hard stops. The remote service fails
  closed when `MCP_JWT_SECRET` is unset.
- Tool responses are honest about failure: QBO Fault errors surface with
  code + message + actionable guidance; nothing is retried into silence.

## Testing Invariants

- Golden tests for tax math (CPP/CPP2, CCA half-year & AII, GST34 line
  arithmetic, meals ITC restriction) with hand-checked expected values.
- The US-unchanged regression suite (no injected tax fields for US bodies)
  must pass for any change touching create tools or region logic.
- All tests pass offline (respx-mocked); no test hits Intuit or the backend.
- Multi-tenant isolation (ContextVar) has a dedicated test; any change to
  context handling must keep it green.

## Git & Ops Invariants

- **`main` is production. Never push to it directly.** This product reads and
  writes real books; a merge to `main` deploys the web app (Vercel) and is the
  source for desktop releases. Every change lands through a short-lived branch →
  PR → green gates (pytest + secret-scan) → squash-merge. Branch protection
  enforces this. Admin-merge is only for when CI runners are genuinely
  unavailable ("not acquired"), and the PR says so — never to skip a real failure.
- No force-push to main. No secrets, tokens, or books data in git — ever.
- Schema source of truth: `web/supabase-schema.sql` mirrors live prod;
  changes ship as dated files in `web/migrations/` and are applied before
  the code that needs them deploys.
- Statutory rate tables reviewed annually (December CRA / IRS announcements);
  Reports API cutover and other dated obligations tracked in private-docs/OPS.md.
- External failure → hold and log, never publish partial financial data
  silently.

---

## When In Doubt

1. **Correct books over convenient answers.** A refusal with a pointer beats
   a plausible wrong number.
2. **The user's accountant is the authority.** We prepare; humans file.
3. **Fail loudly, attribute everything.** Typed errors inward, audit rows
   outward.
4. **Each tier keeps its own privacy promise.** Never borrow the stricter
   tier's marketing.

---

This Constitution governs the money/books path and **wins over any general
engineering standard** where they conflict (see VASPERA-SPINE.md §7); the conflict
gets reported. The org engineering standard (gates, artifacts, infra) is
VASPERA-SPINE.md at the repo root — this Constitution is the higher law here.

_CONSTITUTION_VERSION: 2 — added branch/PR production discipline + VASPERA-SPINE
reference (2026-08-28). Referenced from CLAUDE.md; loads in every session._
