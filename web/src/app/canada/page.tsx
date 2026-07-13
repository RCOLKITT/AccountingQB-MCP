/* ============================================================================
   AccountingQB — Canada Landing Page
   Sibling of the main landing page (same premium dark theme); CRA-flavored
   copy and CAD pricing for Canadian solopreneurs, businesses and bookkeepers.
   ============================================================================ */

import type { Metadata } from "next";
import LandingNav from "@/components/nav/LandingNav";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://accountingqb.com";

export const metadata: Metadata = {
  title: "AccountingQB for Canadian Businesses — GST/HST, T2125 & CRA Tools for Claude",
  description:
    "AI-powered QuickBooks for Canadian books: GST/HST return workpapers, T2125 line mapping, CCA schedules, T4A reports, and CRA instalment estimates — all through Claude. Priced in CAD. 14-day free trial.",
  alternates: {
    canonical: "/canada",
    languages: {
      "en-US": "/",
      "en-CA": "/canada",
      "x-default": "/",
    },
  },
  openGraph: {
    type: "website",
    locale: "en_CA",
    url: `${siteUrl}/canada`,
    siteName: "AccountingQB",
    title: "AccountingQB for Canadian Businesses — GST/HST, T2125 & CRA Tools for Claude",
    description:
      "GST/HST return workpapers, T2125 mapping, CCA schedules, T4A reports and CRA instalments — AI-powered QuickBooks for Canadian books, priced in CAD.",
    images: [
      {
        url: `${siteUrl}/og-image.png`,
        width: 1200,
        height: 630,
        alt: "AccountingQB — Your QuickBooks, Powered by Claude",
      },
    ],
  },
};

const caTiers = [
  {
    name: "Solopreneur",
    price: "CA$49",
    period: "/mo",
    description: "For freelancers & sole proprietors",
    savings: "Save ~5 hrs/mo on bookkeeping & tax prep",
    features: [
      "All 104 QuickBooks tools",
      "T2125 line mapping & GST/HST workpapers",
      "CRA instalment estimates (CPP + CPP2)",
      "Anomaly detection",
      "1 QuickBooks company",
      "Email support",
    ],
    cta: "Start Free Trial",
    href: "/api/stripe/checkout?tier=solopreneur&currency=cad",
    highlight: false,
  },
  {
    name: "Business",
    price: "CA$129",
    period: "/mo",
    description: "For growing small businesses",
    savings: "Save ~12 hrs/mo across 3 companies",
    features: [
      "Everything in Solopreneur",
      "Up to 3 companies",
      "T4A & T5018 contractor reporting",
      "Budget vs actual analysis",
      "Cash flow forecasting",
      "Priority support",
    ],
    cta: "Start Free Trial",
    href: "/api/stripe/checkout?tier=business&currency=cad",
    highlight: true,
  },
  {
    name: "Firm",
    price: "CA$399",
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
    href: "/api/stripe/checkout?tier=firm&currency=cad",
    highlight: false,
  },
];

const caFeatures = [
  {
    title: "GST/HST return workpapers",
    body: "GST34 lines 101–109 computed from your QuickBooks transactions, with the 50% meals ITC restriction applied, Quick Method eligibility flagged, and your province's regime detected — HST, GST+PST, or GST+QST.",
  },
  {
    title: "T2125 line mapping",
    body: "Your expense accounts mapped to T2125 Part 4 lines — 8521 advertising, 8523 meals at 50%, 8910 rent, 9281 vehicle — the way an accountant would prep the Statement of Business Activities.",
  },
  {
    title: "CCA schedules",
    body: "Capital cost allowance by class (8, 10, 10.1, 12, 50, 54) with the half-year rule and Accelerated Investment Incentive applied, including the Class 10.1 passenger-vehicle ceiling.",
  },
  {
    title: "T4A & T5018 contractor reports",
    body: "Pull contractor payments for the year, flag vendors over the reporting threshold, and get slips ready before the end-of-February deadline — T5018 for construction.",
  },
  {
    title: "CRA instalment estimates",
    body: "Quarterly instalments from your live P&L: CPP and CPP2 at current YMPE/YAMPE, approximate federal and provincial income tax, and the Mar/Jun/Sep/Dec 15 schedule.",
  },
  {
    title: "Canadian tax codes, everywhere",
    body: "Invoices, expenses and bills created with the right tax code — HST ON, GST, or your provincial codes — with tax-inclusive or tax-exclusive totals.",
  },
];

const caFaqs = [
  {
    q: "Does AccountingQB file my GST/HST return or taxes with the CRA?",
    a: "No — it produces workpapers, not filings. It computes the GST34 lines, maps T2125, and builds CCA and T4A schedules so you (or your accountant) can review and file with confidence. Always verify against QuickBooks' Sales Tax Centre before filing.",
  },
  {
    q: "Which provinces are supported?",
    a: "All of them. AccountingQB detects your company's province and applies the right regime: HST in Ontario and the Atlantic provinces (including Nova Scotia's 14% rate), GST+PST in BC, Saskatchewan and Manitoba, GST+QST in Québec, and GST-only in Alberta and the territories.",
  },
  {
    q: "What about Québec?",
    a: "QuickBooks tax codes for GST/QST work throughout, and the GST/HST workpaper flags what belongs to Revenu Québec (combined FPZ-500 filing) versus the GST portion. Full QST return computation is on the roadmap — the workpaper tells you exactly what's excluded so nothing is silently wrong.",
  },
  {
    q: "Is my financial data safe?",
    a: "Run AccountingQB locally — the desktop extension runs entirely on your machine and your data never touches our servers. Or use our hosted connector, where data passes through with zero retention. Either way, we never store your books.",
  },
  {
    q: "How do I know the CRA numbers are current?",
    a: "Every rate we use — GST/HST by province (including Nova Scotia's 2025 change to 14%), CPP/CPP2 ceilings, CCA vehicle limits, instalment thresholds — lives in a versioned registry citing its CRA source and verification date. Every tax answer shows its rate vintage in the footer, changes ship through a tamper-evident audit ledger reviewed by a human, and a research agent checks CRA announcements monthly. Ask Claude to run qb_tax_data_info to see the full provenance table.",
  },
  {
    q: "Am I billed in Canadian dollars?",
    a: "Yes — prices on this page are in CAD and checkout is billed in CAD. No FX surprises on your card statement.",
  },
  {
    q: "I use QuickBooks Self-Employed — does this work?",
    a: "QuickBooks Self-Employed isn't available in Canada, which is exactly why we built this. AccountingQB works with QuickBooks Online (EasyStart, Essentials, Plus or Advanced) and gives Canadian solopreneurs the self-employed tax tooling Intuit never shipped here.",
  },
];

/* ---------- Inline Logo SVG Component (local copy, gradient id namespaced) ---------- */
function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg-ca" x1="60" y1="60" x2="452" y2="452" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="40%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <path d="M 210 108 A 148 148 0 1 1 209.99 108 Z M 210 164 A 92 92 0 1 0 210.01 164 Z"
        fill="url(#lg-ca)" fillRule="evenodd" />
      <rect x="290" y="310" width="120" height="52" rx="26" fill="url(#lg-ca)" transform="rotate(42, 350, 336)" />
      <rect x="290" y="118" width="42" height="268" rx="4" fill="url(#lg-ca)" />
      <path d="M 311 118 L 360 118 A 62 62 0 0 1 360 242 L 311 242 Z" fill="url(#lg-ca)" />
      <path d="M 311 242 L 370 242 A 72 72 0 0 1 370 386 L 311 386 Z" fill="url(#lg-ca)" />
      <path d="M 318 148 L 348 148 A 34 34 0 0 1 348 216 L 318 216 Z" fill="#0a0e1a" />
      <path d="M 318 268 L 355 268 A 42 42 0 0 1 355 364 L 318 364 Z" fill="#0a0e1a" />
    </svg>
  );
}

/* ---------- Check Icon ---------- */
function CheckIcon() {
  return (
    <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

export default function CanadaPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AccountingQB",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows, macOS, Linux",
    description:
      "AI-powered QuickBooks tools for Canadian businesses: GST/HST return workpapers, T2125 line mapping, CCA schedules, T4A reports and CRA instalment estimates through Claude.",
    offers: [
      {
        "@type": "Offer",
        name: "Solopreneur",
        price: "49.00",
        priceCurrency: "CAD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
      {
        "@type": "Offer",
        name: "Business",
        price: "129.00",
        priceCurrency: "CAD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
      {
        "@type": "Offer",
        name: "Firm",
        price: "399.00",
        priceCurrency: "CAD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
    ],
  };

  return (
    <main className="min-h-screen overflow-x-hidden">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* ========== NAV ========== */}
      <LandingNav />

      {/* ========== HERO ========== */}
      <section className="relative pt-20">
        <div className="absolute inset-0 bg-[#0a0e1a]" />
        <div className="absolute inset-0 bg-grid opacity-50" />
        <div className="absolute top-0 left-1/4 h-[400px] w-[400px] rounded-full bg-cyan-500/[0.07] blur-[120px]" />
        <div className="absolute top-40 right-1/4 h-[350px] w-[350px] rounded-full bg-indigo-500/[0.07] blur-[120px]" />

        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center sm:py-32">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-red-500/20 bg-red-500/[0.08] px-4 py-1.5 text-xs font-medium text-red-200">
            🍁 Built for Canadian books
          </div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
            QuickBooks Self-Employed
            <br />
            doesn&apos;t exist in Canada.
            <br />
            <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              Claude + AccountingQB does.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-400">
            GST/HST return workpapers, T2125 line mapping, CCA schedules, T4A reports,
            and CRA instalment estimates — 104 AI tools connecting Claude to your
            QuickBooks Online, in plain English.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="#pricing"
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-xl shadow-blue-600/25 transition hover:shadow-blue-500/40 hover:brightness-110"
            >
              Start Your Free Trial
            </a>
            <a
              href="/setup-wizard"
              className="rounded-xl border border-white/10 px-8 py-3.5 text-sm font-semibold text-gray-300 transition hover:border-white/20 hover:bg-white/[0.04] hover:text-white"
            >
              See how it connects
            </a>
          </div>
          <p className="mt-5 text-sm text-gray-500">
            14-day free trial &middot; Billed in CAD &middot; No credit card required
          </p>
        </div>
      </section>

      {/* ========== FEATURES ========== */}
      <section id="features" className="relative border-y border-white/[0.06] bg-[#0c1120] py-28">
        <div className="absolute inset-0 bg-grid opacity-20" />
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/20 bg-cyan-500/[0.08] px-3 py-1 text-xs font-medium text-cyan-300">
              Canadian tax toolkit
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              The CRA workpapers your{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">accountant would build</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              Ask in plain English. Get line-by-line workpapers from your live QuickBooks data.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {caFeatures.map((f) => (
              <div key={f.title} className="rounded-2xl border border-white/[0.06] bg-[#131a2e] p-7 transition hover:border-white/[0.12]">
                <h3 className="text-lg font-semibold text-white">{f.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-gray-400">{f.body}</p>
              </div>
            ))}
          </div>

          <p className="mt-10 text-center text-sm text-gray-500">
            Province-aware: HST in Ontario &amp; the Atlantic provinces, GST+PST in BC, Saskatchewan
            &amp; Manitoba, GST+QST in Québec, GST-only in Alberta &amp; the territories.
          </p>
        </div>
      </section>

      {/* ========== PRICING ========== */}
      <section id="pricing" className="relative py-28">
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-green-500/20 bg-green-500/[0.08] px-3 py-1 text-xs font-medium text-green-300">
              Pricing in CAD
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              Less than the cost of{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">one hour of bookkeeping</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              Start with a 14-day free trial. Billed in Canadian dollars. Cancel anytime.
            </p>
          </div>

          <div className="mt-16 grid gap-6 lg:grid-cols-3">
            {caTiers.map((t) => (
              <div
                key={t.name}
                className={`relative rounded-2xl border p-8 transition duration-300 ${
                  t.highlight
                    ? "border-blue-500/30 bg-[#131a2e] shadow-xl shadow-blue-600/10 ring-1 ring-blue-500/20"
                    : "border-white/[0.06] bg-[#131a2e] hover:border-white/[0.12]"
                }`}
              >
                {t.highlight && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-1 text-xs font-semibold text-white">
                    Most Popular
                  </div>
                )}
                <h3 className="text-lg font-semibold text-white">{t.name}</h3>
                <p className="mt-1 text-sm text-gray-500">{t.description}</p>
                <div className="mt-6 flex items-baseline gap-1">
                  <span className="text-5xl font-bold text-white">{t.price}</span>
                  <span className="text-gray-500">{t.period}</span>
                </div>
                <p className="mt-1 text-xs text-gray-500">Billed in CAD</p>
                {t.savings && (
                  <p className="mt-2 text-xs font-medium text-cyan-400/80">{t.savings}</p>
                )}
                <a
                  href={t.href}
                  className={`mt-8 block w-full rounded-xl py-3 text-center text-sm font-semibold transition ${
                    t.highlight
                      ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-blue-600/20 hover:shadow-blue-500/30 hover:brightness-110"
                      : "border border-white/10 text-gray-300 hover:border-white/20 hover:bg-white/[0.04] hover:text-white"
                  }`}
                >
                  {t.cta}
                </a>
                <ul className="mt-8 space-y-3">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-3 text-sm text-gray-400">
                      <CheckIcon />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <p className="mt-8 text-center text-sm text-gray-500">
            All plans include a 14-day free trial with full access. No credit card required.
          </p>
        </div>
      </section>

      {/* ========== FAQ ========== */}
      <section id="faq" className="relative border-t border-white/[0.06] bg-[#0c1120] py-28">
        <div className="mx-auto max-w-3xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-purple-500/20 bg-purple-500/[0.08] px-3 py-1 text-xs font-medium text-purple-300">
              FAQ
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              Canadian questions, answered
            </h2>
          </div>
          <div className="mt-16 space-y-6">
            {caFaqs.map((faq) => (
              <div key={faq.q} className="gradient-border rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white">{faq.q}</h3>
                <p className="mt-3 text-gray-400">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========== FINAL CTA ========== */}
      <section className="relative border-t border-white/[0.06] py-28">
        <div className="absolute top-0 left-1/3 h-[300px] w-[300px] rounded-full bg-cyan-500/[0.06] blur-[100px]" />
        <div className="absolute bottom-0 right-1/3 h-[300px] w-[300px] rounded-full bg-indigo-500/[0.06] blur-[100px]" />

        <div className="relative mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
            Ready for tax season
            <br />
            <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              without the scramble?
            </span>
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Join Canadian entrepreneurs saving hours every week on bookkeeping, GST/HST and tax prep.
          </p>
          <a
            href="#pricing"
            className="mt-8 inline-block rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-10 py-4 text-sm font-semibold text-white shadow-xl shadow-blue-600/25 transition hover:shadow-blue-500/40 hover:brightness-110"
          >
            Start Your Free Trial
          </a>
          <p className="mt-5 text-sm text-gray-500">
            14-day free trial &middot; Billed in CAD &middot; No credit card required
          </p>
        </div>
      </section>

      {/* ========== FOOTER ========== */}
      <footer className="border-t border-white/[0.06] bg-[#0a0e1a]">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <div className="grid gap-10 sm:grid-cols-3">
            <div>
              <a href="/" className="flex items-center gap-2">
                <LogoMark className="h-7 w-7" />
                <span className="text-lg font-bold text-white">
                  Accounting<span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">QB</span>
                </span>
              </a>
              <p className="mt-4 text-sm text-gray-500">
                AI-powered QuickBooks tools for Claude Desktop and Cowork.
                A <a href="https://vasperacapital.com" className="text-gray-400 transition hover:text-white">Vaspera Capital</a> product.
              </p>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-300">Product</h4>
              <ul className="mt-4 space-y-2.5 text-sm text-gray-500">
                <li><a href="#features" className="transition hover:text-white">Features</a></li>
                <li><a href="#pricing" className="transition hover:text-white">Pricing</a></li>
                <li><a href="#faq" className="transition hover:text-white">FAQ</a></li>
                <li><a href="/" className="transition hover:text-white">US site</a></li>
                <li><a href="/dashboard" className="transition hover:text-white">Dashboard</a></li>
                <li><a href="/sign-in" className="transition hover:text-white">Sign In</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-300">Legal</h4>
              <ul className="mt-4 space-y-2.5 text-sm text-gray-500">
                <li><a href="/privacy" className="transition hover:text-white">Privacy Policy</a></li>
                <li><a href="/terms" className="transition hover:text-white">Terms of Service</a></li>
                <li><a href="mailto:support@vasperacapital.com" className="transition hover:text-white">Contact</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-14 border-t border-white/[0.06] pt-8">
            <p className="text-center text-sm text-gray-600">
              &copy; {new Date().getFullYear()} Vaspera Capital. All rights reserved.
              AccountingQB is not affiliated with Intuit or QuickBooks.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
