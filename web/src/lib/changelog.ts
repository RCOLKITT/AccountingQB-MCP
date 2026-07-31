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
    version: "3.6",
    date: "2026-07-31",
    title: "2026 vs 2025 tax changes — sourced",
    tag: "Tax",
    summary:
      "Every 2026 tax change a bookkeeper or CPA needs, each with its effective date, statute, and a link to the official source — in the app (qb_tax_law_changes) and on a public reference page.",
    highlights: [
      "New qb_tax_law_changes tool: ask \"what changed for 2026?\" and get a cited, dated answer — filter by jurisdiction or topic",
      "Public /tax-changes reference: US federal, US state, and Canadian rate/threshold changes with one-click sources",
      "OBBBA highlights done right: 100% bonus depreciation restored, SALT cap to $40,400, 1099-NEC threshold $600 → $2,000",
      "Powered by the same sourced, hash-chained tax-data control plane as our calculators — the reference and the tools can't disagree",
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
      "109 tools total across US & Canada",
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
