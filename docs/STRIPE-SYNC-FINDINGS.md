# Stripe → QuickBooks Sync: Findings & Action Items

**Date:** 2026-08-01
**Stripe account:** `acct_1T9x6L8gtMApOcAQ` ("AccountingQB")
**QB company:** NutriFitAI LLC · cash basis · sole proprietor

---

## What was posted

Four journal entries (IDs **2198–2201**) recording actual Stripe activity April–July 2026,
plus a new **Stripe Clearing** account (ID 155, Other Current Asset).

| Date | Dr Stripe Clearing | Dr Merchant fees | Dr Software & apps | Dr Refunds | Cr Sales |
|---|---|---|---|---|---|
| 2026-04-30 | 23.66 | 4.04 | 11.30 | 39.00 | 78.00 |
| 2026-05-31 | 36.50 | 2.02 | 0.48 | — | 39.00 |
| 2026-06-30 | 15.34 | 2.02 | 21.64 | — | 39.00 |
| 2026-07-31 | 36.54 | 2.02 | 0.44 | — | 39.00 |
| **Total** | **112.04** | **10.10** | **33.86** | **39.00** | **195.00** |

**Verified:** Stripe Clearing = **$112.04**, matching the live Stripe available balance exactly.
P&L income = $195.00 Sales − $39.00 Refunds = **$156.00 net revenue**.

### Entries deleted and replaced

| Deleted | Reason |
|---|---|
| 2187, 2189, 2190 | Estimated subscription entries. Recorded 3 charges (actual: 5), $1.43 fee (actual: $2.02), and credited the **bank** — but no Stripe payout has ever occurred. Their own memos said "match to Stripe payout when bank feed reconnects, do not duplicate." |
| 2188 | Estimated refund entry, credited bank instead of Stripe balance. |
| 2194–2197 | First attempt at the new entries; revenue miscoded to an expense account by the `_resolve_account` bug below. |

**Side effect:** removing the three phantom bank deposits moved General Operations from
−$36,050.07 to **−$36,123.78**. More negative, but more accurate — that money never
reached the bank.

---

## Repo bugs found (priority order)

### 1. `_resolve_account` silently returns the wrong account — DATA INTEGRITY, blocks release

`mcpb/src/accountingqb/server.py:1061-1078`

```python
result = await qb_query(
    f"SELECT * FROM Account WHERE Name LIKE '%{safe}%' MAXRESULTS 1")
```

Passing `account_name: "Services"` matched **"Legal & accounting services"** and posted
$195 of revenue into an expense account. No warning, no error. The JE balanced, so nothing
downstream caught it.

`qb_account_transactions` handles the identical input correctly:
`"Multiple accounts match: Legal & accounting services (ID:44), Services (ID:2)... Please be more specific."`
So there are two resolution paths and only one is safe.

**Fix:**
1. Try exact `Name = '...'` first, then exact `FullyQualifiedName`, then `LIKE` as last resort.
2. Drop `MAXRESULTS 1` on the `LIKE` branch — if it returns >1, return the ambiguity error.
3. Consolidate both paths onto one resolver.

This affects every write tool that takes an account name: journal entries, expenses, bills,
deposits, transfers, reclassifications.

### 2. `qb_create_journal_entry` silently ignores unknown line keys

`server.py:3129-3131`

```python
acct_name = entry.get("account_name", "")
amount = float(entry.get("amount", 0))
posting_type = entry.get("type", "Debit")
```

Passing `posting_type` instead of `type` made **every line a debit**. The balance check
caught it here, but only by luck — a symmetric mistake would post silently.

**Fix:** reject unknown keys in each line dict with a clear message. Also accept
`account_id` as an explicit, unambiguous alternative to `account_name` (this would have
avoided bug #1 entirely).

### 3. JE creation response reports `Total: $0.00`

Cosmetic but misleading — it looks like an empty entry was created. Report total debits.

### 4. `qb_create_account` doesn't pre-validate field lengths

A 114-char description returned raw QuickBooks error 2050. Validate against the 100-char
limit locally and return a useful message.

### 5. Already in the queue

`qb_1099_contractor_report` filtering · `qb_runway_calculator` / `qb_cash_flow_forecast`
sign convention · `qb_anomaly_detection` weekend/duplicate noise · `qb_t2125_summary`
optional `year`.

---

## Product opportunity: `qb_stripe_reconcile`

Everything above was done by hand and it is entirely mechanical. This is the single most
common bookkeeping task for any SaaS or e-commerce client, and it is the thing bookkeepers
most often get wrong.

A tool that: pulls charges, refunds, payouts **and all balance-transaction types**; creates
the processor clearing account; posts monthly JEs; then asserts clearing balance == live
Stripe balance.

The differentiator is the **platform-fee handling**. Most people net revenue against
processing fees and stop. They miss Sigma, Billing, Radar, Connect, Tax, and Terminal fees —
which is why their clearing account never ties. Here those fees were $33.86 against $10.10
of processing fees: **more than 3× larger** than the fees everyone actually books.

Generalize to a "processor clearing" concept covering Stripe, PayPal, Square, Shopify Payments.

---

## Stripe: things to do

1. **Turn off Sigma.** $10.63/month including tax; $31.89 spent to date against $195 of
   gross revenue. That is 16% of everything the business has ever earned, going to an
   analytics tool. Settings → Product settings → Sigma.

2. **Nothing has ever been paid out.** All $112.04 is still sitting in Stripe.
   Check Settings → Bank accounts and scheduling — either no external account is attached
   or payouts are paused.

3. **79% of charges are failing.** 19 of 24 attempts declined (16 `card_declined`,
   3 `incorrect_number`):

   | Customer | Failed attempts | Ever paid? |
   |---|---|---|
   | `cus_UfblV50H3eFeLw` | 9 | no |
   | `cus_UJgrlQAgAXd0UK` | 9 | no |
   | `cus_UJgdQZ3mtSwkC4` | 1 | no |
   | `cus_UKqJYMSELicZLl` | — | **only paying customer** |

   Two people tried nine times each to pay and couldn't. Enable Smart Retries, Card Account
   Updater, and failed-payment emails under Settings → Billing → Revenue recovery.
   Recovering these roughly triples revenue.

4. **Pricing mismatch.** Every charge is $39/month. The pricing page lists $79 one-time,
   $200/yr Pro, $499 Sovereign. Decide which is real.

5. **Fee rate looks international.** $2.02 on $39.00 ≈ 4.4% + $0.30, consistent with
   international cards. Worth confirming.

---

## QuickBooks: things to do

1. **General Operations is −$36,123.78.** This is the largest remaining problem in the books
   and Stripe does not explain any of it. Most likely missing owner-funded transactions or a
   bad opening balance. Needs the bank feed reconnected.

2. **Rewards Checking is −$3,199.00.** Same class of problem.

3. **Chart of accounts hygiene** (from the earlier review): 5 duplicate accounts,
   3 misclassified account types, inverted equity signs. The 100/100 health audit does not
   catch any of these — worth adding a Books Hygiene tier that does.

4. **Entity naming.** Stripe's statement descriptor already reads "VASPERA CAPITAL" while
   the QB company is NutriFitAI LLC. Worth aligning at the rename.

5. **Going forward:** this sync needs to run monthly. Say the word and I'll set it up as a
   scheduled task that pulls the prior month from Stripe and posts the JE.

---

## The deduction question — corrected

Recording this revenue does **not** unlock the deductions previously discussed.

YTD net income moves to **−$13,347.31**. Still a loss, so:

| | Status |
|---|---|
| SEP-IRA contribution room | $0 — requires net SE income |
| SE health insurance deduction | $0 — capped at net SE income |
| §179 expensing | Still limited by the loss |
| §199A QBI deduction | Negative QBI, nothing to deduct |
| 1099-K matching risk | None — $195 gross is far below any threshold |

The business is pre-revenue in any practical sense. The books are now accurate, which
matters, but the tax position is essentially unchanged. Deductions open up when there is
net income to offset — which makes the 79% payment failure rate the highest-value item
on this entire list.
