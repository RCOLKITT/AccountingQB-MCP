# AccountingQB Tools (101 Total)

## Company & Entities (12 tools)
| Tool | Description |
|------|-------------|
| qb_company_info | Company name, EIN, address, fiscal year |
| qb_list_accounts | Full chart of accounts with balances |
| qb_list_vendors | Search vendors/suppliers |
| qb_list_customers | Search customers |
| qb_list_items | Products and services |
| qb_create_vendor | Create a new vendor |
| qb_create_customer | Create a new customer |
| qb_update_vendor | Update vendor details (email, phone, address) |
| qb_update_customer | Update customer details (email, phone, address) |
| qb_create_account | Add an account to chart of accounts |
| qb_create_sub_account | Create a sub-account under a parent |
| qb_inactivate_account | Hide unused accounts |

## Transactions (17 tools)
| Tool | Description |
|------|-------------|
| qb_list_transactions | Purchases/expenses with filters |
| qb_list_deposits | Income and owner investments |
| qb_list_transfers | Account-to-account transfers |
| qb_list_journal_entries | Adjustments and reclassifications |
| qb_list_journal_entries_by_memo | Search JEs by memo text |
| qb_list_bills | Accounts payable |
| qb_list_bill_payments | Bill payments |
| qb_list_sales_receipts | Direct sales |
| qb_list_payments | Customer payments received |
| qb_list_invoices | Invoices with status filter |
| qb_list_credit_memos | Customer credit memos/refunds |
| qb_list_vendor_credits | Vendor credits received |
| qb_list_estimates | Estimates/quotes with status filter |
| qb_search_transactions | Search across ALL transaction types |
| qb_list_recurring_transactions | Recurring templates and schedules |
| qb_transaction_detail | Full detail for any single transaction |
| qb_account_transactions | All transactions hitting a specific account |

## Create & Modify (22 tools)
| Tool | Description |
|------|-------------|
| qb_create_expense | Record a purchase/expense |
| qb_create_invoice | Create a customer invoice |
| qb_create_bill | Create a vendor bill |
| qb_create_estimate | Create a customer estimate/quote |
| qb_create_journal_entry | Record adjustments |
| qb_create_deposit | Record a bank deposit |
| qb_create_transfer | Transfer between accounts |
| qb_create_credit_memo | Issue a customer credit memo |
| qb_create_vendor_credit | Record a vendor credit |
| qb_convert_estimate_to_invoice | Convert estimate into invoice |
| qb_record_bill_payment | Record payment on a vendor bill |
| qb_record_invoice_payment | Record customer payment on invoice |
| qb_update_transaction | Update any transaction |
| qb_void_transaction | Void a transaction |
| qb_delete_transaction | Delete a transaction permanently |
| qb_delete_journal_entry | Permanently delete a JE |
| qb_reclassify_transaction | Move transaction to different account |
| qb_bulk_update_vendor | Bulk-assign vendor to multiple transactions |
| qb_bulk_update_vendors_multi | Bulk-assign multiple vendors in one call |
| qb_batch_create_expenses | Bulk expense import |
| qb_batch_create_bills | Bulk bill import |
| qb_batch_create_journal_entries | Bulk JE import |

## Reports & Analysis (17 tools)
| Tool | Description |
|------|-------------|
| qb_profit_loss | P&L by total, month, quarter, or year |
| qb_profit_loss_by_class | P&L by department/class |
| qb_balance_sheet | Balance sheet as of any date |
| qb_cash_flow | Statement of cash flows |
| qb_cash_flow_forecast | Multi-period cash flow projections |
| qb_general_ledger | All transactions by account |
| qb_trial_balance | Verify books are balanced |
| qb_ar_aging | What customers owe you |
| qb_ap_aging | What you owe vendors |
| qb_expense_summary | Expenses by category |
| qb_income_summary | Income by source |
| qb_sales_tax_summary | Sales tax collected by jurisdiction |
| qb_compare_periods | Side-by-side period comparison |
| qb_vendor_summary | Top vendors by spend |
| qb_profit_margin_analysis | Profit margins by customer or item |
| qb_budget_vs_actual | Compare budget to actual spending |
| qb_anomaly_detection | Statistical anomaly and fraud detection |

## Tax Preparation (16 tools)
| Tool | Description |
|------|-------------|
| qb_tax_summary | Expenses mapped to Schedule C lines |
| qb_schedule_c | Full IRS Schedule C line-by-line |
| qb_schedule_c_detailed | Granular Schedule C with QB account detail |
| qb_estimate_quarterly_tax | Federal + state estimated taxes |
| qb_deduction_finder | Find commonly missed deductions |
| qb_depreciation_schedule | Section 179 and MACRS schedules |
| qb_1099_contractor_report | 1099-NEC contractor reporting |
| qb_home_office_calculator | Form 8829 home office deduction |
| qb_vehicle_depreciation_calculator | Vehicle depreciation with business use % |

### Canadian Tax
| Tool | Description |
|------|-------------|
| qb_gst_hst_return | GST/HST return workpaper (Canada) |
| qb_t2125_summary | CRA T2125 statement of business activities mapping (Canada) |
| qb_cca_schedule | CCA (capital cost allowance) depreciation schedule (Canada) |
| qb_t4a_contractor_report | T4A/T5018 contractor report (Canada) |
| qb_estimate_instalments | CRA instalments + CPP estimator (Canada) |
| qb_list_tax_codes | List sales tax codes (GST/HST/PST) |
| qb_list_tax_rates | List sales tax rates |

## Smart Features (9 tools)
| Tool | Description |
|------|-------------|
| qb_uncategorized_transactions | Find uncategorized transactions |
| qb_find_duplicates | Detect potential duplicates |
| qb_auto_categorize_suggestions | AI-suggested categories |
| qb_monthly_burn_rate | Monthly expense trends |
| qb_runway_calculator | Months of cash runway |
| qb_fiscal_year_close_checklist | Year-end close readiness check |
| qb_books_health_audit | Comprehensive books health audit |
| qb_month_end_close | Month-end close checklist with status checks |
| qb_unknown_vendor_report | Find transactions with missing vendor names |

## Reconciliation & Attachments (7 tools)
| Tool | Description |
|------|-------------|
| qb_reconcile_invoices | Match invoices against transactions |
| qb_match_invoices_to_transactions | Fuzzy-match with tolerance |
| qb_upload_receipt | Attach receipts to transactions |
| qb_list_attachments | List attached documents |
| qb_missing_receipts | Expenses >= threshold (default $75) with no receipt attached |
| qb_change_audit_trail | What changed since a date — created/updated/deleted (QuickBooks CDC) |
| qb_account_balance | Check any account balance |

## Connection & Multi-Company (3 tools)
| Tool | Description |
|------|-------------|
| qb_list_companies | List connected QuickBooks companies |
| qb_switch_company | Switch to a different company |
| qb_refresh_connection | Refresh connection to AccountingQB |

---

## Usage Examples

Ask Claude naturally:
- "What's my P&L for 2025?"
- "Show me all expenses over $500 from last month"
- "Create an expense for $49.99 to GitHub for software subscriptions"
- "Run my Schedule C for tax year 2024"
- "Find any uncategorized transactions"
- "What's my monthly burn rate?"
- "How much runway do I have?"
- "Compare Q1 vs Q2 profit and loss"
- "Find potential duplicate transactions"
- "What deductions am I missing?"
- "Generate my 1099 contractor report"
- "Prepare my GST/HST return workpaper for Q2"
- "Run my T2125 summary for this fiscal year"
- "Run anomaly detection on last quarter's transactions"
- "Show my profit margins by customer"
- "Forecast my cash flow for the next 6 months"
- "Create a vendor credit for $200 to Amazon"
- "Run a books health audit"
- "Do my month-end close for April"
