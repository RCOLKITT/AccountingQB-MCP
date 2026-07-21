---
name: accountingqb-cpa-workbook
description: Assembles a complete, CPA-ready year-end workbook (Excel or CSV bundle) from live QuickBooks data via AccountingQB. Use when the user says "prepare my CPA workbook", "year-end binder", "export for my accountant", "CPA package", "export the workbook", or clicks Export in the dashboard artifact's Workbook tab.
---

# CPA Workbook Export

Produce the exact package a CPA expects at year-end: reconciled statements,
supporting schedules, and open items — every figure pulled fresh from
AccountingQB tools, never from memory or invention.

## Period

Use the period the user gives (the artifact's export button includes it).
If none: prior calendar year when today is January–April, else year-to-date.

## Region

Call `qb_company_info` first. If the output shows **Business Number (BN)**
the company is Canadian — use the CA sheet set below; otherwise US.

## Sheets (one per section, in this order)

| # | Sheet name | Tool (US / CA) |
|---|---|---|
| 00 | Cover | `qb_company_info` + `qb_books_health_audit` |
| 01 | Trial Balance | `qb_trial_balance(start, end)` |
| 02 | Profit & Loss | `qb_profit_loss(start, end, "Total")` |
| 03 | Balance Sheet | `qb_balance_sheet(end)` |
| 04 | Cash Flow | `qb_cash_flow(start, end)` |
| 05 | General Ledger | `qb_general_ledger(start, end)` |
| 06 | Tax Mapping | `qb_schedule_c_detailed(year)` / `qb_t2125_summary(year)` |
| 07 | Contractors | `qb_1099_contractor_report(year)` / `qb_t4a_contractor_report(year)` |
| 08 | Sales Tax | `qb_sales_tax_summary(start, end)` / `qb_gst_hst_return(start, end)` |
| 09 | Fixed Assets | `qb_depreciation_schedule(year)` / `qb_cca_schedule(year=year)` |
| 10 | Open Items | `qb_uncategorized_transactions` + `qb_find_duplicates` + `qb_unknown_vendor_report` (all with start/end) |

## Assembly rules

1. **Run every tool fresh** for the chosen period. Convert each tool's
   markdown tables to sheet rows; keep account names in column A and
   amounts in numeric columns (no currency symbols in cells — format the
   column instead). Never invent, estimate, or fill gaps: a cell exists
   only if the tool output contains it. If a tool errors, include the
   sheet with a single line "Section unavailable: <error>".
2. **Cover sheet (00)** contains: company name, period, prepared date,
   books-health score, open-items count, the user's notes if provided,
   and this line verbatim: "Prepared with AccountingQB — workpapers, not
   filings. Verify before filing."
3. **Provenance row** at the bottom of every sheet:
   `Source: <tool> | pulled <ISO timestamp> | period <start>–<end>`.
   For sheets 06–09 also append the TAX_DATA version line from
   `qb_tax_data_info` (first two header lines are enough).
4. **File naming**: a single Excel workbook
   `AccountingQB-Workbook-<Company>-<YYYY or YYYY-MM-DD range>.xlsx` with
   the sheets above. If Excel generation isn't available in this session,
   produce a folder of CSVs named `00-Cover.csv` … `10-Open-Items.csv`
   plus the cover as `00-Cover.csv`, and tell the user it's a CSV bundle.
5. When finished, tell the user the file location, the sheet list, the
   books-health score, and any open items their CPA will ask about.
