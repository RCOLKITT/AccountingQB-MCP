/* Scripted content for the /demo experience — a canned but realistic "talk to your
   books" session over a fake sample company. NO real Claude, NO real QuickBooks: every
   answer here is fixed, illustrative data. Keep numbers internally consistent and mirror
   the shape of the real tools' output. Matching is keyword-based and runs client-side. */

export const DEMO_COMPANY = "TechStart Inc.";

type Tone =
  | "text-cyan-400"
  | "text-green-400"
  | "text-blue-400"
  | "text-emerald-400"
  | "text-amber-400"
  | "text-red-400"
  | "text-white";

export type DemoCard =
  | { kind: "metrics"; title?: string; note?: string; items: { label: string; value: string; tone: Tone }[] }
  | { kind: "lines"; title?: string; note?: string; rows: { label: string; value: string; sub?: string; strong?: boolean }[] }
  | { kind: "list"; title?: string; note?: string; items: { title: string; detail: string; badge?: string }[] }
  | { kind: "score"; title: string; score: number; note?: string; findings: string[] };

export interface DemoResponse {
  intro: string;
  cards?: DemoCard[];
  tools: string[];
  followups?: string[];
}

/** The suggested prompts shown as chips (also the "menu" of what the demo covers). */
export const DEMO_SUGGESTIONS = [
  "What's my burn rate and runway?",
  "Find deductions I might be missing",
  "Generate my Schedule C",
  "Any anomalies or duplicates?",
  "How healthy are my books?",
  "Show my P&L",
];

interface Intent {
  keywords: string[];
  response: DemoResponse;
}

const INTENTS: Intent[] = [
  {
    keywords: ["burn", "runway", "cash", "how long"],
    response: {
      intro: "Here's your financial overview:",
      cards: [
        {
          kind: "metrics",
          items: [
            { label: "Monthly Burn", value: "$4,218", tone: "text-cyan-400" },
            { label: "Cash on Hand", value: "$52,640", tone: "text-green-400" },
            { label: "Runway", value: "12.5 mo", tone: "text-blue-400" },
            { label: "Trend", value: "-3.2%", tone: "text-emerald-400" },
          ],
          note: "Burn decreased 3.2% vs last quarter. Top expenses: Hosting ($890), Software ($680), Marketing ($520).",
        },
      ],
      tools: ["qb_monthly_burn_rate", "qb_runway_calculator"],
      followups: ["Show my P&L", "Find deductions I might be missing"],
    },
  },
  {
    keywords: ["deduction", "write off", "write-off", "missing", "save on tax"],
    response: {
      intro: "I scanned 1,204 transactions and found 6 likely deductions that aren't fully categorized — about $8,410 in deductible expenses:",
      cards: [
        {
          kind: "list",
          items: [
            { title: "Home office — $3,120", detail: "12.5% of rent/utilities (Form 8829). Currently booked as personal.", badge: "Schedule C L30" },
            { title: "Software subscriptions — $2,280", detail: "Figma, Linear, Vercel miscategorized as 'Office supplies'.", badge: "Schedule C L27a" },
            { title: "Business mileage — $1,190", detail: "1,700 mi × 70¢ (2025 IRS rate) not yet recorded.", badge: "Schedule C L9" },
            { title: "Business meals — $1,020", detail: "50% deductible under IRC §274(n); flagged for the limit.", badge: "Schedule C L24b" },
          ],
          note: "Estimated tax impact: ~$1,850 at a 22% marginal rate. Every figure is sourced and dated — ask to see the citations.",
        },
      ],
      tools: ["qb_find_deductions", "qb_classify_account", "qb_home_office_calculator"],
      followups: ["Generate my Schedule C", "Show the citations"],
    },
  },
  {
    keywords: ["schedule c", "schedule-c", "tax prep", "taxes", "t2125", "prep for tax"],
    response: {
      intro: `Here's a draft Schedule C for ${DEMO_COMPANY} (tax year 2025). Every rate is sourced and audit-logged:`,
      cards: [
        {
          kind: "lines",
          title: "Schedule C — Profit or Loss From Business",
          rows: [
            { label: "Line 1 — Gross receipts", value: "$487,320" },
            { label: "Line 28 — Total expenses", value: "$304,170" },
            { label: "Line 24b — Meals (50% of $2,040)", value: "$1,020", sub: "IRC §274(n) · verified 2026-08-03" },
            { label: "Line 30 — Home office (Form 8829)", value: "$3,120", sub: "12.5% business use" },
            { label: "Line 31 — Net profit", value: "$174,740", strong: true },
          ],
          note: "Reconciliation ties out: deductible + limited + non-deductible = total book expenses. Nothing dropped.",
        },
      ],
      tools: ["qb_schedule_c", "qb_tax_summary", "qb_tax_data_info"],
      followups: ["Find deductions I might be missing", "How healthy are my books?"],
    },
  },
  {
    keywords: ["anomal", "duplicate", "fraud", "unusual", "suspicious", "weird"],
    response: {
      intro: "I ran an anomaly + duplicate scan across the last 12 months. 3 things worth a look:",
      cards: [
        {
          kind: "list",
          items: [
            { title: "Possible duplicate — $1,450", detail: "AWS charged twice on Mar 12 & Mar 13, same amount.", badge: "review" },
            { title: "Unusual amount — $9,800", detail: "'Contractor — Dev' is 4.1× the vendor's 6-month average.", badge: "verify" },
            { title: "Weekend transaction — $620", detail: "Office supplies posted Sunday 2:14 AM; atypical for this account.", badge: "low risk" },
          ],
          note: "No changes made — these are flags for you to confirm. AccountingQB never edits your books without asking.",
        },
      ],
      tools: ["qb_anomaly_detection", "qb_find_duplicates"],
      followups: ["How healthy are my books?", "Reconcile my Stripe payouts"],
    },
  },
  {
    keywords: ["health", "audit", "clean", "quality", "hygiene", "how good"],
    response: {
      intro: "Here's your books-health audit:",
      cards: [
        {
          kind: "score",
          title: "Books Health Score",
          score: 82,
          findings: [
            "14 uncategorized transactions ($3,910) — mostly software",
            "2 unknown vendors need a name",
            "1 duplicate candidate flagged (AWS, $1,450)",
            "Bank feed reconciled through last month ✓",
          ],
          note: "Fix the uncategorized items and you'd be at ~94. Ask me to categorize them for you.",
        },
      ],
      tools: ["qb_books_health_audit", "qb_find_uncategorized"],
      followups: ["Find deductions I might be missing", "Any anomalies or duplicates?"],
    },
  },
  {
    keywords: ["p&l", "p and l", "profit", "loss", "income statement", "revenue", "how much did i make"],
    response: {
      intro: `Profit & Loss for ${DEMO_COMPANY} (YTD 2025):`,
      cards: [
        {
          kind: "lines",
          title: "Profit & Loss — Year to Date",
          rows: [
            { label: "Revenue", value: "$487,320" },
            { label: "Cost of goods sold", value: "$61,200" },
            { label: "Gross profit", value: "$426,120", strong: true },
            { label: "Operating expenses", value: "$251,380" },
            { label: "Net income", value: "$174,740", strong: true },
          ],
          note: "Up 18% vs the same period last year. Ask me to drill into any line.",
        },
      ],
      tools: ["qb_profit_loss", "qb_compare_periods"],
      followups: ["What's my burn rate and runway?", "Generate my Schedule C"],
    },
  },
  {
    keywords: ["reconcile", "stripe", "bank", "payout", "match"],
    response: {
      intro: "I reconciled your Stripe payouts against the bank deposits:",
      cards: [
        {
          kind: "lines",
          title: "Stripe ↔ Bank Reconciliation",
          rows: [
            { label: "Payouts matched", value: "142 of 142" },
            { label: "Processing fees separated", value: "$4,880" },
            { label: "Net difference", value: "$0.00", strong: true },
          ],
          note: "Everything ties out. Fees were split from gross so your revenue isn't overstated.",
        },
      ],
      tools: ["qb_stripe_reconcile", "qb_bank_reconciliation"],
      followups: ["Show my P&L", "How healthy are my books?"],
    },
  },
  {
    keywords: ["1099", "contractor", "t4a"],
    response: {
      intro: "Here are the contractors who cross the $600 1099-NEC threshold this year:",
      cards: [
        {
          kind: "list",
          items: [
            { title: "Dana R. — $28,400", detail: "Development. W-9 on file.", badge: "1099-NEC" },
            { title: "Priya S. — $12,150", detail: "Design. W-9 on file.", badge: "1099-NEC" },
            { title: "Marcos L. — $740", detail: "Copywriting. W-9 missing — request before filing.", badge: "needs W-9" },
          ],
          note: "3 of 3 contractors identified from vendor payments. I can draft the filing summary next.",
        },
      ],
      tools: ["qb_1099_report", "qb_vendor_payments"],
      followups: ["How healthy are my books?", "Generate my Schedule C"],
    },
  },
];

const HELP: DemoResponse = {
  intro:
    `This is a live demo on a sample company, ${DEMO_COMPANY} — no sign-up, no QuickBooks needed. ` +
    "Ask me anything about the books, or tap a suggestion below:",
  tools: [],
  followups: DEMO_SUGGESTIONS.slice(0, 4),
};

/** Pure, client-side matcher. Returns a scripted response for any input. */
export function matchDemo(message: string): DemoResponse {
  const m = message.toLowerCase();
  for (const intent of INTENTS) {
    if (intent.keywords.some((k) => m.includes(k))) return intent.response;
  }
  return {
    ...HELP,
    intro:
      "I can only answer from this sample company in the demo, but here's what I'd normally do — " +
      "try one of these on TechStart Inc.'s books:",
  };
}
