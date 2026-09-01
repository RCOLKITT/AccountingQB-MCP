/* Single source of truth for plan tiers + the comparison matrix. Shared by the
   homepage pricing section and the dedicated /pricing page so they never drift.
   NOTE: prices are monthly. An annual mechanic is deliberately NOT wired here —
   it needs real Stripe annual prices + a discount decision (audit D4.3), so it's
   flagged rather than faked. */

export interface Tier {
  name: string;
  price: string;
  priceCad: string;
  period: string;
  description: string;
  savings: string;
  features: string[];
  cta: string;
  href: string;
  highlight: boolean;
}

export const tiers: Tier[] = [
  {
    name: "Solopreneur",
    price: "$39",
    priceCad: "CA$49",
    period: "/mo",
    description: "For freelancers & sole proprietors",
    savings: "Save ~5 hrs/mo on bookkeeping & tax prep",
    features: [
      "All 133 QuickBooks tools",
      "US & Canadian tax prep (Schedule C / T2125)",
      "Deduction finder",
      "Anomaly detection",
      "1 QuickBooks company",
      "Email support",
    ],
    cta: "Start Free Trial",
    href: "/api/stripe/checkout?tier=solopreneur",
    highlight: false,
  },
  {
    name: "Business",
    price: "$99",
    priceCad: "CA$130",
    period: "/mo",
    description: "For growing small businesses",
    savings: "Save ~12 hrs/mo across 3 companies",
    features: [
      "Everything in Solopreneur",
      "Up to 3 companies",
      "1099 & T4A contractor reporting",
      "Budget vs actual analysis",
      "Cash flow forecasting",
      "Priority support",
    ],
    cta: "Start Free Trial",
    href: "/api/stripe/checkout?tier=business",
    highlight: true,
  },
  {
    name: "Firm",
    price: "$299",
    priceCad: "CA$399",
    period: "/mo",
    description: "For accounting firms & bookkeepers",
    savings: "Save ~3 hrs/client/mo — pays for itself at 3 clients",
    features: [
      "Everything in Business",
      "Unlimited companies",
      "Month-end close workflows",
      "Year-end close checklist",
      "Bulk operations",
      "Dedicated support",
    ],
    cta: "Start Free Trial",
    href: "/api/stripe/checkout?tier=firm",
    highlight: false,
  },
];

/* Comparison matrix for the /pricing table. Values are literal cell contents;
   "✓"/"—" render as icons. Kept factual and in step with the tier feature lists. */
export interface CompareRow {
  label: string;
  values: [string, string, string]; // [Solopreneur, Business, Firm]
}

export const comparisonRows: CompareRow[] = [
  { label: "Monthly price (USD)", values: ["$39", "$99", "$299"] },
  { label: "QuickBooks companies", values: ["1", "Up to 3", "Unlimited"] },
  { label: "All 133 tools (read + write)", values: ["✓", "✓", "✓"] },
  {
    label: "US & Canadian tax prep (Schedule C / T2125)",
    values: ["✓", "✓", "✓"],
  },
  { label: "Deduction finder & anomaly detection", values: ["✓", "✓", "✓"] },
  { label: "1099 & T4A contractor reporting", values: ["—", "✓", "✓"] },
  {
    label: "Budget vs actual & cash-flow forecasting",
    values: ["—", "✓", "✓"],
  },
  { label: "Month-end & year-end close workflows", values: ["—", "—", "✓"] },
  { label: "Bulk operations", values: ["—", "—", "✓"] },
  { label: "Support", values: ["Email", "Priority", "Dedicated"] },
];

/* Pricing-page FAQs — also emitted as FAQPage JSON-LD for SEO/AI discovery (D5.3/D5.5). */
export const pricingFaqs: { q: string; a: string }[] = [
  {
    q: "Is there a free trial?",
    a: "Yes — every plan starts with a 14-day free trial with full access to all 133 tools. No credit card required to start.",
  },
  {
    q: "What happens when the trial ends?",
    a: "You keep access to 25 essential read-only tools for free. To keep using all 133 tools — including writes, tax prep, and advanced analytics — choose a paid plan.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel from your billing portal at any time. No contracts and no cancellation fees.",
  },
  {
    q: "Do you charge in Canadian dollars?",
    a: "Yes. If you're in Canada we show and bill in CAD; otherwise pricing is in USD.",
  },
  {
    q: "Which plan do I need?",
    a: "Solopreneur fits one company and a single owner. Business covers up to three companies plus contractor reporting and forecasting. Firm is for bookkeepers and accountants with unlimited companies and month-end/year-end close workflows.",
  },
];
