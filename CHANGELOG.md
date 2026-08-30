# What's New in AccountingQB

User-facing release notes for the desktop app. The newest stable version's entry is
shown in-app once, right after the app updates itself. Keep entries short and written
for the person using the app — not for engineers. One `## <version> — <date>` heading
per release; the app parses these headings.

## 0.2.0 — 2026-08-30

- **The app now updates itself.** When we ship a new version, AccountingQB downloads
  and installs it in the background and switches over next time you open it — no more
  re-downloading from the website.
- **Client Package reports.** Build a branded PDF (and a real multi-sheet Excel) of a
  client's financials — Profit & Loss, Balance Sheet, and A/R & A/P aging — with a
  prior-year comparison column, an AI-drafted management note you can edit, and the
  ability to hide, rename, or collapse individual lines. Save the whole setup as a
  per-client template so next month is one click. Every figure is pulled live from
  QuickBooks; nothing is invented.
- **Import client data.** Got a trial balance or general ledger as a spreadsheet? Load
  the CSV, map the columns, and AccountingQB turns it into a tidy workpaper (PDF or
  Excel) with subtotals and a balance check — the figures stay the client's.
- **Connect Coffer in a couple of clicks.** Linking AccountingQB and Coffer now takes
  you through a quick sign-in and connects both ways, and the connection survives
  restarts.
- **Fixes for brand-new QuickBooks companies** (owner-paid expenses now set up their
  own accounts) and a smoother reconnect when a session expires.

## 0.1.0 — 2026-08

- First desktop release: your QuickBooks, on your machine. Dashboard, Profit & Loss,
  Cash Flow, A/R, A/P, Transactions, Tax, Workbook, and Health — plus an "Ask
  AccountingQB" chat panel. Your books never leave your computer.
