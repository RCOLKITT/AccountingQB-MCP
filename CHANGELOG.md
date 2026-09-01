# What's New in AccountingQB

User-facing release notes for the desktop app. The newest stable version's entry is
shown in-app once, right after the app updates itself. Keep entries short and written
for the person using the app — not for engineers. One `## <version> — <date>` heading
per release; the app parses these headings.

## 0.3.0 — 2026-09-01

- **S corporation and partnership tax workpapers.** Declare your entity type and
  AccountingQB arranges your books onto Form 1120-S or Form 1065 — including the
  Schedule M-1 book-to-tax reconciliation, per-owner K-1 summaries, and (for
  S-corps) a reasonable-compensation check. Workpapers to hand your CPA, with
  every line verified against the IRS instructions.
- **Categorization rules that remember.** Save rules like "uber → Travel" once and
  clear the whole uncategorized backlog in one pass — always previewed before
  anything changes, and consistent every month.
- **1099-MISC report.** Rents, royalties (at the correct $10 threshold), and other
  reportable payments — completing the 1099 story alongside the improved 1099-NEC.

## 0.2.0 — 2026-08-31

- **The app now updates itself.** When we ship a new version, AccountingQB downloads
  and installs it in the background and switches over next time you open it — no more
  re-downloading from the website.
- **More accurate 1099s — and 1099-MISC is new.** The 1099-NEC contractor report now
  counts what you actually **paid** (not unpaid bills), leaves out card payments (your
  card processor reports those), shows each contractor's payments broken out by
  account, and lets you designate exactly which accounts are compensation. Plus a new
  1099-MISC report for rents, royalties, and other reportable payments.
- **Fixed: the Tax tab's quarterly estimate** showed a pairing error once Coffer was
  linked. It now works whether or not you use Coffer.
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
