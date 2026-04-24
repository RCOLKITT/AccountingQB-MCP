/**
 * Time saved estimates for each MCP tool.
 * Values are in minutes, representing how long the task would take manually.
 *
 * Categories:
 * - Tax tools: High value (45-240 min)
 * - Reconciliation: High value (90-120 min)
 * - Reports & Analysis: Medium value (10-60 min)
 * - Smart Bookkeeping: Medium value (20-60 min)
 * - CRUD operations: Low value (2-5 min)
 */
export const TIME_SAVED_MINUTES: Record<string, number> = {
  // ============================================
  // Tax & Compliance (High Value)
  // ============================================
  qb_schedule_c: 180, // 3 hours - full Schedule C mapping
  qb_schedule_c_detailed: 240, // 4 hours - detailed line-by-line
  qb_deduction_finder: 60, // 1 hour - scan for missed deductions
  qb_quarterly_estimates: 45, // 45 min - calculate estimated taxes
  qb_1099_report: 90, // 1.5 hours - 1099 contractor reporting
  qb_depreciation_schedule: 60, // 1 hour - MACRS/Section 179 analysis
  qb_home_office_calculator: 30, // 30 min - home office deduction
  qb_vehicle_deduction: 30, // 30 min - vehicle/mileage deduction
  qb_year_end_checklist: 90, // 1.5 hours - year-end close checklist

  // ============================================
  // Reconciliation (High Value)
  // ============================================
  qb_reconcile_invoices: 120, // 2 hours - invoice reconciliation
  qb_match_bank_transactions: 90, // 1.5 hours - bank matching
  qb_reconcile_accounts: 60, // 1 hour - account reconciliation

  // ============================================
  // Reports & Analysis (Medium Value)
  // ============================================
  qb_profit_loss: 15, // 15 min - P&L report
  qb_profit_loss_by_class: 20, // 20 min - P&L by class/department
  qb_profit_loss_by_customer: 20, // 20 min - P&L by customer
  qb_balance_sheet: 15, // 15 min - balance sheet
  qb_cash_flow: 20, // 20 min - cash flow statement
  qb_general_ledger: 25, // 25 min - general ledger
  qb_trial_balance: 15, // 15 min - trial balance
  qb_ar_aging: 10, // 10 min - AR aging
  qb_ap_aging: 10, // 10 min - AP aging
  qb_budget_vs_actual: 30, // 30 min - budget analysis
  qb_customer_balance: 10, // 10 min - customer balances
  qb_vendor_balance: 10, // 10 min - vendor balances
  qb_monthly_burn_rate: 15, // 15 min - burn rate calculation
  qb_runway_calculator: 20, // 20 min - runway analysis
  qb_cash_flow_forecast: 45, // 45 min - 6-month forecast
  qb_profit_margin_by_customer: 30, // 30 min - margin analysis
  qb_profit_margin_by_product: 30, // 30 min - product margin

  // ============================================
  // Smart Bookkeeping (Medium Value)
  // ============================================
  qb_categorize_suggest: 30, // 30 min - auto-categorization
  qb_duplicate_detector: 45, // 45 min - find duplicates
  qb_unknown_vendors: 20, // 20 min - unknown vendor cleanup
  qb_anomaly_scan: 30, // 30 min - anomaly detection
  qb_books_health_audit: 60, // 1 hour - full health audit
  qb_uncategorized_transactions: 20, // 20 min - find uncategorized
  qb_month_end_close: 90, // 1.5 hours - month-end workflow

  // ============================================
  // Search & Query (Low-Medium Value)
  // ============================================
  qb_search_transactions: 10, // 10 min
  qb_search_invoices: 10, // 10 min
  qb_search_bills: 10, // 10 min
  qb_search_expenses: 10, // 10 min
  qb_search_customers: 5, // 5 min
  qb_search_vendors: 5, // 5 min
  qb_get_transaction: 5, // 5 min
  qb_get_invoice: 5, // 5 min
  qb_get_customer: 5, // 5 min
  qb_get_vendor: 5, // 5 min
  qb_get_account: 5, // 5 min
  qb_list_accounts: 5, // 5 min
  qb_list_customers: 5, // 5 min
  qb_list_vendors: 5, // 5 min
  qb_list_items: 5, // 5 min
  qb_list_classes: 5, // 5 min

  // ============================================
  // Create Operations (Low Value)
  // ============================================
  qb_create_expense: 2, // 2 min
  qb_create_invoice: 5, // 5 min
  qb_create_bill: 3, // 3 min
  qb_create_bill_payment: 3, // 3 min
  qb_create_estimate: 5, // 5 min
  qb_create_credit_memo: 3, // 3 min
  qb_create_vendor_credit: 3, // 3 min
  qb_create_journal_entry: 5, // 5 min
  qb_create_deposit: 3, // 3 min
  qb_create_transfer: 2, // 2 min
  qb_create_customer: 2, // 2 min
  qb_create_vendor: 2, // 2 min
  qb_create_item: 3, // 3 min
  qb_create_account: 3, // 3 min

  // ============================================
  // Update Operations (Low Value)
  // ============================================
  qb_update_expense: 2, // 2 min
  qb_update_invoice: 3, // 3 min
  qb_update_bill: 3, // 3 min
  qb_update_customer: 2, // 2 min
  qb_update_vendor: 2, // 2 min
  qb_update_item: 2, // 2 min
  qb_update_account: 2, // 2 min
  qb_void_invoice: 2, // 2 min

  // ============================================
  // Bulk Operations (Medium Value)
  // ============================================
  qb_bulk_categorize: 45, // 45 min
  qb_bulk_update_vendors: 30, // 30 min
  qb_bulk_delete: 15, // 15 min

  // ============================================
  // Company Info (Low Value)
  // ============================================
  qb_company_info: 2, // 2 min
  qb_preferences: 2, // 2 min
};

/**
 * Default time saved for tools not in the map.
 */
const DEFAULT_TIME_SAVED = 5;

/**
 * Gets the estimated time saved for a tool invocation.
 * @param toolName The name of the tool (e.g., "qb_schedule_c")
 * @returns Time saved in minutes
 */
export function getTimeSaved(toolName: string): number {
  return TIME_SAVED_MINUTES[toolName] ?? DEFAULT_TIME_SAVED;
}

/**
 * Gets all tools with their time saved values.
 * Useful for documentation and analytics.
 */
export function getAllTimeSavedValues(): Array<{
  tool: string;
  minutes: number;
}> {
  return Object.entries(TIME_SAVED_MINUTES)
    .map(([tool, minutes]) => ({ tool, minutes }))
    .sort((a, b) => b.minutes - a.minutes);
}
