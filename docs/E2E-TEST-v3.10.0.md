# AccountingQB v3.10.0 — End-to-End Test Report

**Date:** 2026-08-01 · **Build:** 3.10.0 (126 tools) · **Company:** NutriFitAI LLC, realm `9341453706844727`
**Data:** 230 card transactions YTD, live QuickBooks + live Stripe.

**Verdict: the v3.9.x/v3.10.0 fixes are real and they hold. All 7 previously-reported bugs
are fixed and verified against known-good figures. But testing surfaced 10 new issues, two
of which are release blockers — including one that produces an incorrect tax return.**

---

## Part 1 — Regression: all 7 prior bugs FIXED ✅

| # | Bug | Test | Result |
|---|---|---|---|
| 1 | `qb_account_transactions` silent truncation | Card, default `max_results` | ✅ `230 \| $22,936.47 — showing the first 100`. Correct count **and** explicit disclosure. |
| 2 | `_resolve_account` silent wrong account | `qb_account_balance("Services")` | ✅ Returns all 4 candidates instead of silently picking `Legal & accounting services`. |
| 3 | JE unknown line keys ignored | `posting_type` + `account_id` | ✅ `"Journal line 1 has unrecognized field(s): posting_type. Allowed per line: account_name (or account_id), amount, type…"` — and `account_id` is now supported, which was the requested fix. |
| 4 | `qb_list_accounts` ignores `account_type` | `account_type="Bank"` | ✅ `Chart of Accounts (2 accounts, type=Bank)`. |
| 5 | `qb_search_transactions` misses feed memos | `"MOBILE PAYMENT"` | ✅ 14 transactions, $8,500.00 — matches ground truth exactly. Was 0. |
| 6 | `qb_create_account` no length validation | 158-char description | ✅ `"Description is 158 characters; QuickBooks allows at most 100."` |
| 7 | Health audit blind to structural problems | New `qb_books_hygiene` | ✅ **40/100.** Independently found the deleted-account postings, wrong-sign balances, dormant account, and all 12 misfiled card payments. |

`qb_books_hygiene` deserves specific credit: it found in one call what took manual digging
across several sessions, and its 12-payments/$7,000 figure correctly excludes the 2 payments
posted to the deleted SkyMiles account (counted under the deleted-account finding instead).
Internally consistent. This is the best tool in the product.

Guardrails also verified working: `dry_run` defaults to true, delete requires `confirm=True`
and suggests voiding instead, and `qb_stripe_reconcile` refused to post on a failed tie-out.

---

## Part 2 — New bugs

### 🔴 P0 — `qb_schedule_c` omits all business revenue

```
Line 1 — Gross receipts: $0.76
Line 31 — Net profit (loss): $-20,089.26
```

$0.76 is the bank interest. **The $195.00 in `Sales` and the $39.00 in `Refunds to
customers` are absent from the return entirely.**

Cross-checked against P&L for the identical period:

| | P&L | Schedule C |
|---|---|---|
| Business revenue | $195.00 Sales − $39.00 refunds = **$156.00** | **absent** |
| Interest income | $0.76 (Other Income) | **$0.76 on Line 1** |
| Total expenses | $20,090.02 | $20,090.02 ✅ |
| **Bottom line** | **−$19,933.26** | **−$20,089.26** |

Two distinct defects:

1. **Income accounts are not mapped to Line 1.** `Sales` (`SalesOfProductIncome`) and
   `Refunds to customers` (`DiscountsRefundsGiven`) are both skipped. Refunds should map to
   Line 2 (returns and allowances), not be dropped.
2. **Other Income is being swept onto Line 1.** Interest income belongs on Line 6, not
   gross receipts.

The expense side is correct and ties to the P&L exactly, so this is isolated to income mapping.

**Why P0:** this is a tax product and this is an incorrect return. Understated gross
receipts is the single most audit-sensitive line on Schedule C. Verify `qb_t2125_summary`
for the same defect on the Canadian side.

### 🔴 P0 — `qb_trial_balance` is structurally broken

```
General Operations (7405) - 1: $36,123.23
Inventory:
Stripe Clearing:
Sales: $195.00
Owner investments: $75,369.51
**TOTAL: $126,766.65**
```

- **No debit/credit columns.** A trial balance is definitionally two columns.
- **Most accounts render blank** — every expense account, Stripe Clearing, Inventory, the
  fixed assets.
- **It doesn't balance**, and cannot, with one column. `TOTAL` is the sum of a mixed bag and
  means nothing.
- **Signs are inverted.** `General Operations` shows `$36,123.23` positive; the balance is
  −$36,123.23. Same for the card.
- **Header says `2026-01-01 to 2026-08-02`** for a tool taking a single `as_of_date`.

Non-negotiable for the CPA workbook — a trial balance that doesn't balance is the first
thing an accountant will reject.

### 🟠 P1 — `qb_stripe_reconcile` understates platform fees

Reported **$10.62**; correct is **$11.30** (verified against posted JE 2198 and Stripe).

Root cause: it sums the `amount` field on fee records and ignores `fee`. On a `stripe_fee`
balance transaction, `amount` is the fee net of tax and `fee` holds the **sales tax**. True
cash impact is `net`.

```
amount:  -27 + -27 + -8 + -1000  = -1062  → $10.62   ← what the tool reports
net:     -29 + -29 + -9 + -1063  = -1130  → $11.30   ← correct
```

Fix: use `net` for every balance-transaction type. This also affects the charge side, where
`net` already equals `amount − fee`. Understating fees overstates income — wrong direction
for a tax product.

### 🟠 P1 — `qb_stripe_reconcile` contradicts itself inside one report

```
Net retained in Stripe: $24.34          ← Activity section
… prior $112.04 + net change $23.66     ← Tie-out section
```

Same quantity, two values, one output. The Activity figure carries the fee bug above; the
Tie-out figure is correct. They're computed by separate paths that need consolidating.

### 🟠 P1 — Tie-out uses the live balance as "prior" for historical periods

Reconciling **2026-04** — the first period with activity, prior balance $0.00 — it used the
*current* Stripe Clearing balance of $112.04 (which reflects April through July) as the
opening figure:

```
Projected: $135.70 (prior $112.04 + net change $23.66)
Reported:  $23.66 — 🔴 OFF
Unreconciled difference: $112.04
```

The "difference" is just the prior balance it shouldn't have added. Any back-reconciliation
of a historical month will fail this way. Prior balance must be the clearing balance **as of
the period start**, not as of today.

Credit where due: it refused to post on the failed tie-out. The guardrail worked.

### 🟡 P2 — Idempotency doesn't detect manually-posted entries

JE 2198 already reconciles 2026-04. The tool proposed a complete duplicate with no warning.
It only recognizes its own `[stripe:PERIOD]` tag.

Anyone who reconciled by hand before adopting the tool — which is everyone, on their first
run — gets silent duplicates. It should also scan for existing entries touching the clearing
account within the period and warn.

### 🟡 P2 — `dry_run` doesn't validate account resolution

A malformed account name (`Office expenses:Software &amp; apps`) was echoed straight into the
proposed entry without being resolved. A dry run that skips validation gives false
confidence — the whole point is to find problems before posting. Resolve every account
during dry run and report failures.

### 🟡 P2 — `qb_missing_receipts` flags credit-card payments

14 of the 55 flagged items are the card payments — $8,500 of the $18,539.53 total. A payment
is not an expense and has no receipt to attach. Amex interest charges are flagged too.

Exclude transactions categorized to bank/equity accounts — `qb_books_hygiene` already has
exactly this detection logic. Also worth excluding interest.

### 🟡 P2 — `qb_find_duplicates` noise, and two tools disagree

26 pairs returned; nearly all are legitimate. Vercel bills per-usage several times a week,
Tailor Brands runs multiple same-day subscriptions. Flagging `2026-02-05 / 2026-02-06 /
2026-02-07` Vercel charges at $33.12 as three duplicate pairs is noise that trains users to
ignore the tool.

Separately: `qb_books_health_audit` reports **9 potential duplicates**, `qb_find_duplicates`
reports **26 pairs**, same period. Two tools counting the same thing disagree.

Suggest: require same-day + same-amount + same-vendor by default, and suppress vendors with
a high recurring-charge frequency.

### 🔵 P3 — `qb_books_hygiene` truncates its ID list silently

States 12 transactions, lists 10 IDs, no indication of truncation. Minor, but this is the
exact pattern v3.9.2 fixed elsewhere — apply the same disclosure.

---

## Part 3 — Material finding for the books

**The YTD loss is ~$19,933, not the ~$13,347 previously reported.**

The pre-fix P&L understated expenses by roughly $6,600 — `Software & apps` read $3,197.42
against an actual $7,346.42, `Memberships & subscriptions` $176.99 against $2,087.99. The
truncation bug was suppressing real deductions in the financial statements, not just in the
register views.

This is in your favour, and it means every figure quoted from this company file before
v3.9.2 should be re-derived.

Still open on the books:

- 14 card payments ($8,500) misfiled as purchases — awaiting the real Amex statement balance
- 15 transactions with no vendor ($4,317.65) — `qb_unknown_vendor_report` maps them cleanly,
  ready to fix with `qb_bulk_update_vendor`
- 6 transactions on deleted accounts ($1,529.99)
- General Operations −$36,123.23 with $0.76 of real activity — opening-balance error
- Tailor Brands $2,122 across 19 charges, including $498 twice in two days

---

## Recommended order

1. `qb_schedule_c` income mapping — **blocks release**, produces a wrong return
2. `qb_trial_balance` rewrite — **blocks release**, blocks the CPA workbook
3. `qb_stripe_reconcile`: use `net` everywhere; consolidate the two net-change paths;
   period-start prior balance; validate accounts during dry run; detect manual entries
4. `qb_missing_receipts` / `qb_find_duplicates` filtering; reconcile the duplicate counts
5. `qb_books_hygiene` truncation disclosure

Items 1 and 2 are the same class of failure as the bugs fixed in v3.9.x: a confident,
plausible-looking number that is wrong. The pagination and resolution fixes closed that gap
in the data layer. It's still open in the reporting layer.
