// Public release notes — the source of truth for /changelog AND the
// release→campaign flow in /admin/compose. Newest first. On each release,
// prepend an entry; the admin composer can turn any entry into a segmented
// campaign in one click.

export interface Release {
  version: string;
  date: string; // ISO
  title: string;
  tag?: "Feature" | "Tax" | "Canada" | "Platform";
  summary: string;
  highlights: string[];
}

export const RELEASES: Release[] = [
  {
    version: "3.18.1",
    date: "2026-08-06",
    title: "Public tax-data provenance endpoint",
    tag: "Platform",
    summary:
      "The connector now serves a public /tax-data endpoint — version, hash-chained ledger status, per-table sources, and concrete cited highlights — built entirely from the live tax registry so it can never drift from what the tools actually use. It powers the marketing site's provenance card so that card is always accurate.",
    highlights: [
      "GET /tax-data (unauthenticated, cacheable): TAX_DATA version + verified date, ledger row count + chain-verification status, every table's source, and cited highlight values",
      "Derived from the registry (tax_tables) at startup — if a rate changes, the endpoint changes with it; no hand-typed copy to fall out of date",
      "Statutory facts only, no taxpayer data; safe to serve publicly",
    ],
  },
  {
    version: "3.18.0",
    date: "2026-08-04",
    title: "Home office: both methods, with the choice made explicit",
    tag: "Tax",
    summary:
      "Schedule C now supports both home-office methods — actual (Form 8829, business % of real costs, carries forward) and simplified ($5/sq ft up to 300, no carryover) — and shows the two side by side so the choice is informed, including the nuance that flips it in a loss year and the depreciation/recapture trade-off.",
    highlights: [
      "Set the method with qb_allocation_profile (home_office_method: 'actual' or 'simplified'); Schedule C computes Line 30 accordingly, capped at net profit in both",
      "Simplified is treated correctly: $5/sq ft (max 300), the recorded home costs stay off Schedule C (mortgage interest / property taxes → Schedule A), and any excess over net profit is lost (no carryover) — while the actual method's excess carries forward",
      "Every Schedule C now shows a simplified-vs-actual comparison: which wins this year, why actual can be worth more in a loss year (its tentative carries forward), and the §1250 depreciation-recapture trade-off to weigh with your CPA",
      "qb_home_office_calculator shows both methods and the recapture caveat alongside the regular-method breakdown",
    ],
  },
  {
    version: "3.17.6",
    date: "2026-08-04",
    title:
      "Deduction finder no longer counts non-deductible items in the total",
    tag: "Tax",
    summary:
      "The deduction finder was including non-deductible items (charitable contributions, entertainment) inside 'deductible expenses' and the net loss, so its numbers disagreed with Schedule C by exactly those amounts. It now shares the same totals helper as Schedule C, so the two can't diverge.",
    highlights: [
      "qb_deduction_finder's total expenses and net now exclude non-deductible items (§170 charitable, §274 entertainment) — they matched Schedule C on books that happened to have none, but overstated the loss on books that did",
      "Line 28 / Line 31 are now computed by a single shared helper used by qb_schedule_c, qb_schedule_c_detailed, qb_tax_summary, qb_t2125_summary AND qb_deduction_finder — one source of truth",
      "The golden-book test fixture now includes a non-deductible account, and a cross-tool test asserts the deduction finder's net equals Schedule C's — so this class of bug can't ship again",
    ],
  },
  {
    version: "3.17.5",
    date: "2026-08-04",
    title:
      "Deploy smoke test — the live build is now verified after every release",
    tag: "Platform",
    summary:
      "Infrastructure to close the gap that let the deployment-mode mislabel recur: a public /version endpoint and a smoke test that confirms the LIVE connector matches the released version and self-identifies as the hosted connector — including through the authenticated MCP path a client actually uses.",
    highlights: [
      "New public /version endpoint reports the running build's version, tool count, and deployment mode — a one-call check that the deploy actually landed",
      "scripts/deploy-smoke.py verifies the live host after each deploy: version matches the tag, deployment is the hosted connector, and qb_server_info returns the same through the authenticated /mcp endpoint",
      "Catches stale/failed deploys and version drift before a user does — the structural gap behind the recurring deployment-mode report",
    ],
  },
  {
    version: "3.17.4",
    date: "2026-08-04",
    title:
      "Two tax tools brought onto the shared engine; deductions now respect the loss",
    tag: "Tax",
    summary:
      "A full end-to-end sweep found two tools that bypassed the canonical taxonomy and produced tax numbers that disagreed with qb_schedule_c. Both are now on the shared engine, so they can't disagree. And the deduction finder no longer promises savings a loss disallows.",
    highlights: [
      "qb_tax_summary now uses the same taxonomy + allocation/limitation engine as qb_schedule_c — meals are correctly limited to 50% (they were landing on Line 24a at 100%), and it now shows income, home office, net, and non-deductibles too",
      "qb_tax_summary accepts tax_year (previously it silently ignored it and returned year-to-date)",
      "qb_deduction_finder gates every estimate on the income limit it cites — at a loss, self-employed health, SEP-IRA, and home office resolve to $0 this year (or carry forward) instead of fabricated gross values, and it reads your allocation profile before calling home office 'unclaimed'",
      "The R&D-credit suggestion no longer prints a dollar figure off SaaS spend (those generally aren't qualified research expenses) — it prompts a proper eligibility review instead",
      "Journal-entry amounts show correctly in the change audit trail (summed from the debit lines, not the always-zero TotalAmt); bulk same-day weekend data-entry batches no longer flood the anomaly report",
    ],
  },
  {
    version: "3.17.3",
    date: "2026-08-04",
    title:
      "Allocation-key regression fixed; deployment mode & card-payment detection corrected",
    tag: "Tax",
    summary:
      "A follow-up audit caught a regression the previous fix introduced: because account keys became fully-qualified, allocation percentages stored under leaf names stopped matching and were silently dropped (over-claiming). That's fixed, and now a configured percentage that matches no account is surfaced loudly instead of hidden. Plus the real root cause of the deployment-mode flip, and a corrected credit-card-payment check.",
    highlights: [
      "Allocation percentages match on either the leaf name or the full 'Parent:Child' name, so a profile that stores 'Cell phone' still applies to 'Communications:Cell phone' — no more silent 100% over-claim",
      "A configured allocation that matches no account is now reported loudly ('matches NO account'), instead of silently ignored under a false 'not configured' message",
      "Deployment mode (qb_server_info) is read from the import-time config, never the mutable session flag that flipped it after a token refresh — the actual root cause of the recurring mislabel",
      "Credit-card payment detection now keys on QuickBooks' Credit flag (money-in), not the category or memo — card payments are correctly excluded from the 'miscategorized charge' finding, and qb_transaction_detail now shows the Credit flag",
    ],
  },
  {
    version: "3.17.2",
    date: "2026-08-04",
    title: "No more silent truncation; account lookups resolve consistently",
    tag: "Platform",
    summary:
      "Two reliability fixes from the audit backlog. Vendor and customer lists now page through everything and tell you when there's more, instead of quietly stopping at 50. And two account-name lookups that used a bare pattern match now use the shared resolver, so an exact name like 'Utilities' resolves cleanly instead of colliding with 'Home utilities'.",
    highlights: [
      "qb_list_vendors / qb_list_customers report the true total and disclose truncation (pass max_results=0 for all) — no more stopping mid-alphabet with no notice",
      "qb_inactivate_account and qb_account_transactions use the shared account resolver (exact name → full 'Parent:Child' name → unambiguous leaf), so they resolve where a bare pattern match returned raw ambiguity or 'not found'",
      "The resolver still refuses to guess between genuinely ambiguous names rather than silently pick the wrong account",
    ],
  },
  {
    version: "3.17.1",
    date: "2026-08-04",
    title:
      "Two correctness fixes from a real-book audit — owner equity & home routing",
    tag: "Tax",
    summary:
      "An end-to-end test against a real chart of accounts surfaced two directional errors that the conservation check couldn't catch (a misrouted dollar still balances). Owner's Draws no longer counts QuickBooks' system equity accounts as owner activity, and home-office routing now distinguishes accounts that merely share a name — and includes inactive (deleted) accounts.",
    highlights: [
      "qb_owner_draws excludes QuickBooks system equity (Opening Balance Equity, Retained Earnings) — these carry QB's own adjustment entries and were inverting the net on real books; contributions-only books now read as a positive net, as they should",
      "Home-office routing keys on the account's home-office AccountSubType first, then its parent chain — so two accounts sharing a leaf name (e.g. a home 'Repairs & maintenance' and a business one) no longer merge into one treatment",
      "The chart lookup now includes inactive/deleted accounts, so a deleted home cost still routes correctly instead of sitting at 100% on the wrong line",
      "New classification invariants (beyond conservation): no account in two buckets; every home-subtype account routes to the home form; no home cost on an operating line — each locks a specific bug permanently",
    ],
  },
  {
    version: "3.17.0",
    date: "2026-08-04",
    title: "Canada T2125 gets the full allocation engine",
    tag: "Canada",
    summary:
      "The allocation & limitation layer that Schedule C got now runs for the CRA T2125 too — on the same code path, so the two jurisdictions never disagree. Home costs route to line 9945 (business-use-of-home) with the loss limit and carryforward, the motor-vehicle line takes your business-use %, and meals stay at 50% (ITA s.67.1). Previously every T2125 expense flowed at 100%.",
    highlights: [
      "T2125 now applies your allocation profile: motor-vehicle business-use % (line 9281) and per-account percentages, in the correct order (classify → allocate → limit)",
      "Home-office costs route to line 9945 (business-use-of-home) with the CRA loss limitation and carryforward — detected by account parent chain, same as Schedule C's Form 8829",
      "Full conservation: every P&L dollar is reported as deductible, personal (allocation), statutorily-limited, business-use-of-home, or non-deductible — nothing silently over-claimed",
      "Accounts that likely need a business-use % you haven't set are flagged, not deducted at 100% by default",
      "One shared engine for US Schedule C and CA T2125 — only the line numbers differ",
    ],
  },
  {
    version: "3.16.2",
    date: "2026-08-04",
    title: "Owner draws & contributions — fixed to sum the right column",
    tag: "Tax",
    summary:
      "qb_owner_draws was summing the GeneralLedger's running-balance column instead of the transaction amount, which overstated equity activity. It now reads the amount column from the report's own metadata and cross-checks every account's transactions against its balance change, so the net owner figure ties out.",
    highlights: [
      "Sums the transaction Amount column (identified from QuickBooks' column metadata), never the running Balance — a $56,018 net contribution no longer reads as ~$96k",
      "Each equity account now shows its own net, and the total is cross-checked against the account's balance change — if they don't tie, it says so instead of showing a wrong number",
      "Clear sign convention in the output: positive = contribution (money in), negative = draw (money out)",
    ],
  },
  {
    version: "3.16.1",
    date: "2026-08-04",
    title: "Home-office routing hardened — no more silent over-claiming",
    tag: "Tax",
    summary:
      "A precision fix to the allocation layer: home costs booked as sub-accounts under a 'Home office' parent (mortgage interest, property taxes, repairs) now correctly route to Form 8829 at your home-office %, instead of being deducted in full on their operating lines. Detection keys on the account's full parent path, which QuickBooks already provides — no setup required.",
    highlights: [
      "Home-office detection now reads the FullyQualifiedName (parent chain), not just the leaf name — 'Home office:Property taxes' is unambiguously a home cost even though 'Property taxes' alone classifies to Line 23",
      "You can also designate any account as home-indirect in qb_allocation_profile (home_office_accounts) — for a home utility that isn't nested under a 'Home office' parent",
      "The reconciliation footer now shows the Form 8829 carryforward as its own line, so every P&L dollar stays visibly accounted for",
      "qb_server_info reports deployment mode from a static process signal, so it's correct even with an expired token",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.16.0",
    date: "2026-08-03",
    title: "Allocation profiles — the personal/business split, done right",
    tag: "Tax",
    summary:
      "The layer bookkeepers charge for: how much of a mixed expense is actually deductible. Record a home-office %, a vehicle method, and per-account business-use percentages once, and Schedule C applies them — with the math and the Form 8829 home-office limit shown.",
    highlights: [
      "New qb_allocation_profile: set per-year home-office %, vehicle (standard-mileage or actual), and per-account business-use % (e.g. internet 60%) — each recorded with its documented basis and carried forward",
      "qb_schedule_c now applies them in the right order — classify → allocate (your %) → limit (statutory %) — and shows every step, e.g. '$1,000 × 60% (internet) = $600'",
      "Home-office accounts route to Form 8829 (Line 30) with the gross-income limit and carryforward; vehicle supports standard mileage (miles × IRS rate, replacing actual expenses) or a business-use % of actuals",
      "Nothing is dropped: every dollar is reported as deductible, statutorily-limited, personal (allocation), home-office, or non-deductible — and until a percentage is set, mixed accounts are flagged, never silently over-claimed",
      "Allocation percentages are per-taxpayer inputs, stored separately from the sourced statutory tax data — as they should be",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.15.0",
    date: "2026-08-03",
    title: "Statutory deduction limits — meals at 50%, with the math shown",
    tag: "Tax",
    summary:
      "The taxonomy answered which line an expense belongs on; this adds how much of it is actually deductible. Business meals are now correctly limited to 50% (IRC §274(n)) with the arithmetic shown, and accounts that likely need a business-use percentage are flagged rather than silently over-claimed.",
    highlights: [
      "Business meals are limited to 50% on Schedule C (IRC §274(n)) and T2125 (ITA s.67.1) — Line 24b now shows '$X × 50% = $Y' with the citation, instead of deducting the full amount",
      "Statutory limits (law-set, same for everyone) live in the sourced, ledger-gated control plane alongside the tax rates; taxpayer allocation percentages deliberately do not",
      "Reconciliation now balances three buckets — deductible + statutorily-disallowed + non-deductible — so nothing is dropped and the personal/limited share is reported, not hidden",
      "Safety net: accounts deducted at 100% that likely include a personal share (utilities, phone/internet, vehicle, home office) are flagged as needing a business-use percentage — silent over-claiming is never the default",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.14.2",
    date: "2026-08-03",
    title:
      "Taxonomy precision — parent accounts, charitable, and a trustworthy reconciliation",
    tag: "Tax",
    summary:
      "Testing against a real chart of accounts surfaced deductions that were being dropped when amounts are booked directly to a parent category. Fixed, plus a reconciliation check that no longer cries wolf.",
    highlights: [
      "Amounts posted directly to a PARENT account (you pick 'Travel', not 'Travel:Hotels') are now captured on Schedule C / T2125 — previously they silently vanished",
      "The reconciliation warning now compares against ALL expenses (including depreciation, home office, and vehicle), so it stops false-alarming on the majority of sole proprietors and reports the true difference",
      "Charitable contributions are treated as non-deductible on the business return (a sole proprietor claims them on Schedule A / a T1 credit, IRC §170); political contributions too (§162(e))",
      "New books-hygiene check: flags accounts whose name and QuickBooks type disagree (e.g. a phone bill typed as Travel), which would otherwise flow to the wrong tax line",
      "qb_server_info reports version, tools, build, and deployment even when the QuickBooks token is expired",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.14.1",
    date: "2026-08-03",
    title: "Security hardening — logging, secrets, and tenant-isolation tests",
    tag: "Platform",
    summary:
      "A defensive security pass tightening what reaches logs, how token encryption fails, and how we prove tenant isolation. No customer action needed.",
    highlights: [
      "Logging hygiene: the connector no longer emits request URLs at info level, and web endpoints log identifiers instead of emails, license keys, or upstream response bodies",
      "Token encryption fails closed in production — OAuth tokens are never written to the database unencrypted; they remain AES-256-GCM at rest",
      "Added explicit multi-tenant isolation tests (a license can only ever reach its own connected companies) and a CI secret/realm-id scan to catch accidental leaks",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.14.0",
    date: "2026-08-03",
    title: "Canonical tax taxonomy — mappings anchored to IRS & CRA codes",
    tag: "Tax",
    summary:
      "Schedule C and T2125 now classify accounts by their QuickBooks account TYPE — not by matching words in the account name — anchored to official IRS and CRA line codes and governed by the same sourced, gated control plane as our tax rates.",
    highlights: [
      "Accounts are mapped by their QuickBooks AccountSubType (authoritative and stable), with account-name matching only as a fallback — far more robust than the old keyword matching",
      "One classification engine for both the US and Canada, anchored to IRS Schedule C lines and CRA GIFI codes, with every mapping carrying a citation and gated by a new drift test",
      "Entertainment is now correctly treated as non-deductible in the US (IRC §274) — shown separately and excluded from Line 28; equipment leases map to Line 20a; subcontractor costs map to Line 11 (US) / 8340 (CA)",
      "Books without those specific account types see identical numbers; the change is precision, not disruption",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.13.1",
    date: "2026-08-03",
    title:
      "Precision pass: Other Income, duplicate counts, and a server-version tool",
    tag: "Tax",
    summary:
      "A second end-to-end review confirmed 16 of 17 fixes held and surfaced a few small precision issues. This patch closes them — most importantly a $0.76-scale Other Income double-count that reached the Schedule C bottom line.",
    highlights: [
      "Schedule C: fixed an Other Income double-count — a nested 'Net Other Income' roll-up was added twice, inflating Line 6/Line 7. Line 7 now provably equals Line 3 + Line 6",
      "qb_find_duplicates and qb_books_health_audit now share one detector, so their duplicate counts always agree (the tools no longer contradict each other)",
      "qb_missing_receipts now excludes card payments booked to a deleted/inactive credit-card account (previously those slipped through)",
      "New qb_server_info tool: reports the running version, tool count, build timestamp, and QuickBooks connection — so you can confirm which build is actually serving you after an update",
      "Profit & Loss by class/department now says the breakdown is unavailable when tracking is off, instead of returning an ungrouped P&L that looks like a single-segment result",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.13",
    date: "2026-08-02",
    title:
      "Correct tax returns, a real Trial Balance, and cleaner reconciliations",
    tag: "Tax",
    summary:
      "A full end-to-end review against a live company surfaced reporting-layer bugs that produced confident-but-wrong numbers. This release fixes all of them — most importantly, business revenue now lands on the right tax-return lines.",
    highlights: [
      "Schedule C & T2125: gross receipts, returns/refunds, and other income (interest) now map to the correct lines — previously 'Other Income' overwrote sales, so revenue was dropped from the return. The same fix flows through the detailed Schedule C and the US/CA quarterly-tax and instalment estimators",
      "Trial Balance rewritten: real Debit/Credit columns, correct signs, an as-of date (not a range), no blank accounts, and a debits-equal-credits check",
      "Stripe reconcile: platform fees now include their sales tax (reconciled on net), the Activity and Tie-out figures can no longer disagree, historical periods tie to the period-start balance, accounts are validated in dry-run, and a manually-posted entry for the period blocks a double-book",
      "qb_missing_receipts no longer flags credit-card payments, transfers, or interest; qb_find_duplicates now matches same-vendor + same-amount + same-day by default and suppresses recurring charges, with a count that reconciles to the health audit",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.12",
    date: "2026-08-02",
    title: "P&L by department, vendor spend & purchase orders",
    tag: "Feature",
    summary:
      "Three more native reports — and a fix so P&L-by-class actually returns class data.",
    highlights: [
      "Fixed qb_profit_loss_by_class: it asked QuickBooks for the wrong (singular) grouping value, so it always came back empty — now returns real class breakdowns",
      "qb_profit_loss_by_department: the same P&L broken out by department/location",
      "qb_vendor_expenses: total spend by vendor; qb_list_purchase_orders: open/closed POs with vendor, amount, and status",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.11",
    date: "2026-08-02",
    title: "Current with the 2026-07-28 MCP spec",
    tag: "Platform",
    summary:
      "The hosted connector now advertises and implements the newest MCP spec's client-facing improvements — stateless, load-balancer-ready, with cacheable tool listings and zero deprecated features.",
    highlights: [
      "Cacheable tools/list (ttlMs + cacheScope) so gateways and clients can cache the tool catalog instead of re-fetching it",
      "Capability discovery at /.well-known/mcp-capabilities and an MCP-Protocol-Version: 2026-07-28 header on responses",
      "Already stateless and load-balancer-ready (routable on Mcp-Method/Mcp-Name); uses none of the deprecated Roots/Sampling/Logging features",
    ],
  },
  {
    version: "3.10",
    date: "2026-08-02",
    title: "Books Hygiene audit",
    tag: "Feature",
    summary:
      "A structural audit that catches what a health score misses — the kind of problems that quietly make every downstream number wrong.",
    highlights: [
      "qb_books_hygiene flags transactions posted to deleted/inactive accounts, wrong-sign balances, credit-card payments misfiled as expenses, and dormant accounts carrying large balances (opening-balance errors)",
      "Optional statement attestation: hand it your real bank/card statement balances and it diffs them against QuickBooks — the single check that catches everything at once",
      "Complements the existing health audit; every finding names the fix",
    ],
  },
  {
    version: "3.9.2",
    date: "2026-08-02",
    title: "Complete counts, every time",
    tag: "Platform",
    summary:
      "Fixed silent truncation in the reconciliation and cleanup tools — they now read every matching transaction before reporting a count, so a busy account can't come back showing a fraction of its activity.",
    highlights: [
      "qb_account_transactions, qb_search_transactions, qb_uncategorized_transactions and qb_find_duplicates now page through the full result set and report the true total (with an honest 'showing the first N' when a display cap applies)",
      "qb_list_accounts fetches the whole chart (no more silent cut-off on large charts) and gained real account_type and active_only filters",
      "Transaction search now matches bank-feed descriptors on the line, not just the top-level memo — 'MOBILE PAYMENT' and the like are findable again",
    ],
  },
  {
    version: "3.9.1",
    date: "2026-08-02",
    title: "Stripe reconciliation, now automatic",
    tag: "Feature",
    summary:
      "qb_stripe_reconcile can now pull the month directly from Stripe — no export needed — when you run AccountingQB yourself with a read-only Stripe key.",
    highlights: [
      "Leave the report empty and it fetches the period's transactions (and current balance for the tie-out) live from the Stripe API",
      "Self-hosted only via a STRIPE_API_KEY environment variable (read-only restricted key); the hosted connector never holds your Stripe key",
      "Pasting a Stripe export still works exactly as before",
    ],
  },
  {
    version: "3.9",
    date: "2026-08-02",
    title: "Stripe reconciliation, done right",
    tag: "Feature",
    summary:
      "Reconcile a month of Stripe into your books the way most people can't: netting revenue against BOTH processing fees and the platform fees (Sigma, Billing, Radar) everyone forgets — the reason clearing accounts never tie.",
    highlights: [
      "qb_stripe_reconcile: posts a monthly journal entry through a Stripe Clearing account and ties the clearing balance to your Stripe balance",
      "Splits processing fees from platform fees (Sigma/Billing/Radar/Connect/Terminal) — in testing those platform fees were 3× the processing fees",
      "Dry-run by default (proposes the entry first), refuses to post if it doesn't tie or has unmapped transactions, and won't double-post a month",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.8.1",
    date: "2026-08-02",
    title: "Never post to the wrong account",
    tag: "Platform",
    summary:
      "Account name matching now refuses to guess — a partial name like 'Services' can no longer silently match 'Legal & accounting services' and post to the wrong account. Journal entries got safer too.",
    highlights: [
      "Every write tool (expenses, bills, deposits, transfers, journal entries, depreciation) resolves accounts by exact name first, and asks you to clarify instead of guessing when a name is ambiguous",
      "Journal entries now reject unknown line fields (a mistyped 'type' used to make every line a debit) and accept an explicit account_id",
      "Journal-entry confirmations show the real total instead of $0.00; qb_create_account validates name/description length before saving",
    ],
  },
  {
    version: "3.8",
    date: "2026-08-02",
    title: "Class, location & inventory reporting",
    tag: "Feature",
    summary:
      "Break sales out by class or location, value your inventory on hand, and see the class/location tags your books use — the dimensional reports multi-segment and product businesses need.",
    highlights: [
      "qb_sales_by_class and qb_sales_by_department: segment, program, and location performance",
      "qb_inventory_valuation: on-hand quantity, asset value, and average cost per item",
      "qb_list_classes and qb_list_departments: see the class/location dimensions your company tracks",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.7",
    date: "2026-08-01",
    title: "Six new bookkeeper reports",
    tag: "Feature",
    summary:
      "Sales by customer and by product, a flexible transaction list, P&L detail drill-down, and open-item detail by customer and vendor — the native QuickBooks reports bookkeepers ask for, now in Claude.",
    highlights: [
      "qb_sales_by_customer and qb_sales_by_product: who your biggest customers are and what's actually selling",
      "qb_transaction_list: the flexible register — every transaction in a date range with full columns",
      "qb_profit_loss_detail: drill from any P&L number down to the transactions behind it",
      "qb_customer_balance_detail and qb_vendor_balance_detail: the line-item drill-down behind AR/AP aging",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "3.6.2",
    date: "2026-08-01",
    title: "Sales-tax totals net out customer refunds",
    tag: "Tax",
    summary:
      "Sales-tax summary and the economic-nexus screen now subtract customer cash refunds, so refunded sales don't overstate what you owe — or push a state falsely over its nexus threshold.",
    highlights: [
      "Refund receipts net out of taxable sales and tax collected in qb_sales_tax_summary and qb_sales_tax_nexus",
      "Prevents a false 'you may have nexus' signal when returns pull a state back under its threshold",
      "Income summary was already correct (it reads the P&L report, which nets refunds)",
    ],
  },
  {
    version: "3.6.1",
    date: "2026-08-01",
    title: "Complete numbers on large books",
    tag: "Platform",
    summary:
      "Reports and reconciliations now page through every transaction, not just the first 1,000 — so totals stay correct on high-volume books.",
    highlights: [
      "QuickBooks returns at most 1,000 rows per request; tools that total or reconcile across all rows now follow the cursor to the end instead of stopping at the cap",
      "Fixes silent under-counting on busy books — sales-tax and nexus totals, 1099s, missing-receipts, bank reconciliation, expense summaries and more",
      "Small books are unaffected (one request as before); deliberate 'recent N' and single-record lookups keep their limits",
    ],
  },
  {
    version: "3.6",
    date: "2026-08-01",
    title: "Sales-tax economic-nexus screen",
    tag: "Tax",
    summary:
      "Know which states you may owe sales tax in before you get a notice — your sales rolled up by ship-to state against each state's sourced Wayfair threshold, plus liability by state.",
    highlights: [
      "qb_sales_tax_nexus: sales by destination state vs each state's economic-nexus threshold — exposure / approaching / below, with a source link and verified date per state",
      "All ~45 sales-tax states sourced and dated in the same tamper-evident tax-data control plane as our rates (Sales Tax Institute chart, cross-checked to state DORs)",
      "Liability by state (tax collected you owe) + honest caveats: marketplace-facilitated sales, exempt sales, and measurement windows differ",
      "A screening reference, not a determination — confirm with the state and a tax pro before registering",
    ],
  },
  {
    version: "3.5",
    date: "2026-07-22",
    title: "CPA-ready year-end binder",
    tag: "Feature",
    summary:
      "The workbook your accountant can file from — now a 15-page click-through binder with the tie-outs and organizer a CPA asks for.",
    highlights: [
      "Reconciliation tie-outs, prior-year comparative statements (P&L + balance sheet), tax payments made, and owner's draws — the questions a CPA asks first, pre-answered",
      "A structured Tax Organizer replaces free-text notes: mileage, home office, health premiums, assets bought/sold, estimated payments",
      "Export the whole binder to Excel in one message",
      "132 tools total across US & Canada",
    ],
  },
  {
    version: "Cowork plugin",
    date: "2026-07-21",
    title: "One-click dashboard in Claude",
    tag: "Feature",
    summary:
      "Install the AccountingQB plugin and get a live, click-through financial dashboard right inside Claude — no setup, no spreadsheets.",
    highlights: [
      "A living dashboard: P&L, balance sheet, cash flow, reconciliation, open items — drill into any row and ask Claude about it",
      "The CPA Workbook, built for your accountant, one click away",
      "Downloadable at accountingqb.com/downloads/accountingqb.plugin",
    ],
  },
  {
    version: "3.3",
    date: "2026-07-13",
    title: "Every tax number, sourced and dated",
    tag: "Tax",
    summary:
      "A tamper-evident tax-data control plane — every rate we use carries its official source and a verification date, checked monthly.",
    highlights: [
      "Each rate (IRS brackets, mileage, §179/bonus, GST/HST, CPP ceilings) shows its source and vintage",
      "Changes ship through an audit ledger reviewed by a human; a research agent checks sources monthly",
      "That's how we caught the 2025 OBBBA changes and the mid-2026 mileage-rate bump",
    ],
  },
  {
    version: "3.1",
    date: "2026-07-11",
    title: "Full Canada support",
    tag: "Canada",
    summary:
      "GST/HST returns, T2125, CCA schedules, T4A reporting, and CRA instalments — with province-aware rates and CAD pricing.",
    highlights: [
      "GST/HST return prep with PST/QST and provincial rate handling",
      "T2125 business statement, CCA depreciation schedules, T4A contractor reporting",
      "CRA instalment estimator; a dedicated experience at accountingqb.com/canada",
    ],
  },
];
