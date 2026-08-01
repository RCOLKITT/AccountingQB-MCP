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
      "119 tools total across US & Canada",
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
      "119 tools total across US & Canada",
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
