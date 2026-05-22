"use client";

import { useUser } from "@clerk/nextjs";
import { redirect } from "next/navigation";

const TOOL_CATEGORIES = [
  {
    name: "Company & Entities",
    icon: "🏢",
    description: "Manage your QuickBooks company data, accounts, vendors, and customers",
    tools: [
      { name: "qb_company_info", desc: "Company name, EIN, address, fiscal year" },
      { name: "qb_list_accounts", desc: "Full chart of accounts with balances" },
      { name: "qb_list_vendors", desc: "Search vendors/suppliers" },
      { name: "qb_list_customers", desc: "Search customers" },
      { name: "qb_list_items", desc: "Products and services" },
      { name: "qb_create_vendor", desc: "Create a new vendor" },
      { name: "qb_create_customer", desc: "Create a new customer" },
      { name: "qb_update_vendor", desc: "Update vendor details (email, phone, address)" },
      { name: "qb_update_customer", desc: "Update customer details (email, phone, address)" },
      { name: "qb_create_account", desc: "Add an account to chart of accounts" },
      { name: "qb_create_sub_account", desc: "Create a sub-account under a parent" },
      { name: "qb_inactivate_account", desc: "Hide unused accounts" },
    ],
  },
  {
    name: "Transactions",
    icon: "📊",
    description: "View and search all transaction types in your books",
    tools: [
      { name: "qb_list_transactions", desc: "Purchases/expenses with filters" },
      { name: "qb_list_deposits", desc: "Income and owner investments" },
      { name: "qb_list_transfers", desc: "Account-to-account transfers" },
      { name: "qb_list_journal_entries", desc: "Adjustments and reclassifications" },
      { name: "qb_list_journal_entries_by_memo", desc: "Search JEs by memo text" },
      { name: "qb_list_bills", desc: "Accounts payable" },
      { name: "qb_list_bill_payments", desc: "Bill payments" },
      { name: "qb_list_sales_receipts", desc: "Direct sales" },
      { name: "qb_list_payments", desc: "Customer payments received" },
      { name: "qb_list_invoices", desc: "Invoices with status filter" },
      { name: "qb_list_credit_memos", desc: "Customer credit memos/refunds" },
      { name: "qb_list_vendor_credits", desc: "Vendor credits received" },
      { name: "qb_list_estimates", desc: "Estimates/quotes with status filter" },
      { name: "qb_search_transactions", desc: "Search across ALL transaction types" },
      { name: "qb_list_recurring_transactions", desc: "Recurring templates and schedules" },
      { name: "qb_transaction_detail", desc: "Full detail for any single transaction" },
      { name: "qb_account_transactions", desc: "All transactions hitting a specific account" },
    ],
  },
  {
    name: "Create & Modify",
    icon: "✏️",
    description: "Create, update, and manage transactions in QuickBooks",
    tools: [
      { name: "qb_create_expense", desc: "Record a purchase/expense" },
      { name: "qb_create_invoice", desc: "Create a customer invoice" },
      { name: "qb_create_bill", desc: "Create a vendor bill" },
      { name: "qb_create_estimate", desc: "Create a customer estimate/quote" },
      { name: "qb_create_journal_entry", desc: "Record adjustments" },
      { name: "qb_create_deposit", desc: "Record a bank deposit" },
      { name: "qb_create_transfer", desc: "Transfer between accounts" },
      { name: "qb_create_credit_memo", desc: "Issue a customer credit memo" },
      { name: "qb_create_vendor_credit", desc: "Record a vendor credit" },
      { name: "qb_convert_estimate_to_invoice", desc: "Convert estimate into invoice" },
      { name: "qb_record_bill_payment", desc: "Record payment on a vendor bill" },
      { name: "qb_record_invoice_payment", desc: "Record customer payment on invoice" },
      { name: "qb_update_transaction", desc: "Update any transaction" },
      { name: "qb_void_transaction", desc: "Void a transaction" },
      { name: "qb_delete_transaction", desc: "Delete a transaction permanently" },
      { name: "qb_delete_journal_entry", desc: "Permanently delete a JE" },
      { name: "qb_reclassify_transaction", desc: "Move transaction to different account" },
      { name: "qb_bulk_update_vendor", desc: "Bulk-assign vendor to multiple transactions" },
      { name: "qb_bulk_update_vendors_multi", desc: "Bulk-assign multiple vendors in one call" },
      { name: "qb_batch_create_expenses", desc: "Bulk expense import" },
      { name: "qb_batch_create_bills", desc: "Bulk bill import" },
      { name: "qb_batch_create_journal_entries", desc: "Bulk JE import" },
    ],
  },
  {
    name: "Reports & Analysis",
    icon: "📈",
    description: "Generate financial reports and analyze your business performance",
    tools: [
      { name: "qb_profit_loss", desc: "P&L by total, month, quarter, or year" },
      { name: "qb_profit_loss_by_class", desc: "P&L by department/class" },
      { name: "qb_balance_sheet", desc: "Balance sheet as of any date" },
      { name: "qb_cash_flow", desc: "Statement of cash flows" },
      { name: "qb_cash_flow_forecast", desc: "Multi-period cash flow projections" },
      { name: "qb_general_ledger", desc: "All transactions by account" },
      { name: "qb_trial_balance", desc: "Verify books are balanced" },
      { name: "qb_ar_aging", desc: "What customers owe you" },
      { name: "qb_ap_aging", desc: "What you owe vendors" },
      { name: "qb_expense_summary", desc: "Expenses by category" },
      { name: "qb_income_summary", desc: "Income by source" },
      { name: "qb_sales_tax_summary", desc: "Sales tax collected by jurisdiction" },
      { name: "qb_compare_periods", desc: "Side-by-side period comparison" },
      { name: "qb_vendor_summary", desc: "Top vendors by spend" },
      { name: "qb_profit_margin_analysis", desc: "Profit margins by customer or item" },
      { name: "qb_budget_vs_actual", desc: "Compare budget to actual spending" },
      { name: "qb_anomaly_detection", desc: "Statistical anomaly and fraud detection" },
    ],
  },
  {
    name: "Tax Preparation",
    icon: "📋",
    description: "Prepare for tax season with Schedule C, deductions, and 1099 reporting",
    tools: [
      { name: "qb_tax_summary", desc: "Expenses mapped to Schedule C lines" },
      { name: "qb_schedule_c", desc: "Full IRS Schedule C line-by-line" },
      { name: "qb_schedule_c_detailed", desc: "Granular Schedule C with QB account detail" },
      { name: "qb_estimate_quarterly_tax", desc: "Federal + state estimated taxes" },
      { name: "qb_deduction_finder", desc: "Find commonly missed deductions" },
      { name: "qb_depreciation_schedule", desc: "Section 179 and MACRS schedules" },
      { name: "qb_1099_contractor_report", desc: "1099-NEC contractor reporting" },
      { name: "qb_home_office_calculator", desc: "Form 8829 home office deduction" },
      { name: "qb_vehicle_depreciation_calculator", desc: "Vehicle depreciation with business use %" },
    ],
  },
  {
    name: "Smart Features",
    icon: "🧠",
    description: "AI-powered insights, duplicate detection, and automated suggestions",
    tools: [
      { name: "qb_uncategorized_transactions", desc: "Find uncategorized transactions" },
      { name: "qb_find_duplicates", desc: "Detect potential duplicates" },
      { name: "qb_auto_categorize_suggestions", desc: "AI-suggested categories" },
      { name: "qb_monthly_burn_rate", desc: "Monthly expense trends" },
      { name: "qb_runway_calculator", desc: "Months of cash runway" },
      { name: "qb_fiscal_year_close_checklist", desc: "Year-end close readiness check" },
      { name: "qb_books_health_audit", desc: "Comprehensive books health audit" },
      { name: "qb_month_end_close", desc: "Month-end close checklist with status checks" },
      { name: "qb_unknown_vendor_report", desc: "Find transactions with missing vendor names" },
    ],
  },
  {
    name: "Reconciliation & Attachments",
    icon: "🔗",
    description: "Match invoices, attach receipts, and reconcile accounts",
    tools: [
      { name: "qb_reconcile_invoices", desc: "Match invoices against transactions" },
      { name: "qb_match_invoices_to_transactions", desc: "Fuzzy-match with tolerance" },
      { name: "qb_upload_receipt", desc: "Attach receipts to transactions" },
      { name: "qb_list_attachments", desc: "List attached documents" },
      { name: "qb_account_balance", desc: "Check any account balance" },
    ],
  },
  {
    name: "Connection & Multi-Company",
    icon: "🔄",
    description: "Manage multiple QuickBooks companies and connections",
    tools: [
      { name: "qb_list_companies", desc: "List connected QuickBooks companies" },
      { name: "qb_switch_company", desc: "Switch to a different company" },
      { name: "qb_refresh_connection", desc: "Refresh connection to AccountingQB" },
    ],
  },
];

export default function FeaturesPage() {
  const { isSignedIn, isLoaded } = useUser();

  if (isLoaded && !isSignedIn) {
    redirect("/sign-in");
  }

  const totalTools = TOOL_CATEGORIES.reduce((acc, cat) => acc + cat.tools.length, 0);

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0a0e1a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <a href="/dashboard" className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              AccountingQB
            </a>
            <nav className="flex items-center gap-4">
              <a href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">
                Dashboard
              </a>
              <span className="text-sm text-white font-medium">Features</span>
            </nav>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Page Title */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold mb-4">
            All {totalTools} Tools
          </h1>
          <p className="text-xl text-gray-400 max-w-3xl">
            Everything AccountingQB can do for your QuickBooks books. Just ask Claude naturally
            — &quot;What&apos;s my P&L for last month?&quot; or &quot;Find missing deductions.&quot;
          </p>
        </div>

        {/* Category Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
          {TOOL_CATEGORIES.map((cat) => (
            <a
              key={cat.name}
              href={`#${cat.name.toLowerCase().replace(/[^a-z]+/g, "-")}`}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-4 hover:bg-white/[0.05] transition group"
            >
              <div className="text-2xl mb-2">{cat.icon}</div>
              <h3 className="font-medium text-white group-hover:text-cyan-400 transition">
                {cat.name}
              </h3>
              <p className="text-sm text-gray-500">{cat.tools.length} tools</p>
            </a>
          ))}
        </div>

        {/* Tool Categories */}
        <div className="space-y-12">
          {TOOL_CATEGORIES.map((category) => (
            <section
              key={category.name}
              id={category.name.toLowerCase().replace(/[^a-z]+/g, "-")}
              className="scroll-mt-24"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{category.icon}</span>
                <div>
                  <h2 className="text-2xl font-bold">{category.name}</h2>
                  <p className="text-gray-400">{category.description}</p>
                </div>
              </div>

              <div className="grid gap-3">
                {category.tools.map((tool) => (
                  <div
                    key={tool.name}
                    className="rounded-xl border border-white/10 bg-white/[0.02] p-4 hover:bg-white/[0.04] transition"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <code className="text-cyan-400 font-mono text-sm">
                          {tool.name}
                        </code>
                        <p className="text-gray-400 text-sm mt-1">{tool.desc}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Usage Examples */}
        <section className="mt-16 rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-500/10 to-blue-500/10 p-8">
          <h2 className="text-2xl font-bold mb-6">How to Use These Tools</h2>
          <p className="text-gray-300 mb-6">
            You don&apos;t need to remember tool names. Just ask Claude naturally:
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              "What's my P&L for 2025?",
              "Show me all expenses over $500 from last month",
              "Create an expense for $49.99 to GitHub",
              "Run my Schedule C for tax year 2024",
              "Find any uncategorized transactions",
              "What's my monthly burn rate?",
              "How much runway do I have?",
              "Compare Q1 vs Q2 profit and loss",
              "Find potential duplicate transactions",
              "What deductions am I missing?",
              "Generate my 1099 contractor report",
              "Run anomaly detection on last quarter",
              "Show my profit margins by customer",
              "Forecast my cash flow for 6 months",
              "Run a books health audit",
              "Do my month-end close for April",
            ].map((example) => (
              <div
                key={example}
                className="rounded-lg bg-black/30 border border-white/5 px-4 py-3"
              >
                <span className="text-gray-400">&quot;</span>
                <span className="text-white">{example}</span>
                <span className="text-gray-400">&quot;</span>
              </div>
            ))}
          </div>
        </section>

        {/* Back to Dashboard */}
        <div className="mt-12 text-center">
          <a
            href="/dashboard"
            className="inline-flex items-center gap-2 text-gray-400 hover:text-white transition"
          >
            ← Back to Dashboard
          </a>
        </div>
      </div>
    </main>
  );
}
