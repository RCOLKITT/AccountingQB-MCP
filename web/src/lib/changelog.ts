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
      "126 tools total across US & Canada",
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
      "126 tools total across US & Canada",
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
      "126 tools total across US & Canada",
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
      "126 tools total across US & Canada",
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
