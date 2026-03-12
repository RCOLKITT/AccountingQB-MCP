const tiers = [
  {
    name: "Solopreneur",
    price: "$39",
    period: "/month",
    description: "For freelancers and sole proprietors",
    features: [
      "All 91 QuickBooks tools",
      "Schedule C tax prep",
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
    period: "/month",
    description: "For growing small businesses",
    features: [
      "Everything in Solopreneur",
      "Multi-company support (up to 3)",
      "1099 contractor reporting",
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
    period: "/month",
    description: "For accounting firms and bookkeepers",
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

const features = [
  {
    title: "91 Accounting Tools",
    desc: "From P&L reports to Schedule C prep, anomaly detection to cash flow forecasting. The most comprehensive QuickBooks MCP ever built.",
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    title: "Your Data Stays Local",
    desc: "Zero cloud routing. The MCP server runs on your machine and talks directly to QuickBooks. We never see your financial data.",
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
  },
  {
    title: "Talk to Your Books",
    desc: 'Ask Claude natural questions: "What did I spend on software last quarter?" or "Am I missing any tax deductions?"',
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
      </svg>
    ),
  },
  {
    title: "Tax Season Ready",
    desc: "Schedule C mapping, quarterly tax estimates, deduction finder, depreciation schedules, 1099 contractor reports, and home office calculator.",
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
  },
  {
    title: "Smart Bookkeeping",
    desc: "Auto-categorization suggestions, duplicate detection, unknown vendor reports, anomaly flagging, and books health audit scored 0-100.",
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
      </svg>
    ),
  },
  {
    title: "14-Day Free Trial",
    desc: "No credit card required. Full access to all 91 tools. See the value before you pay a cent.",
    icon: (
      <svg className="h-7 w-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1114.625 7.5H12m0 0V21m-8.625-9.75h18c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-18c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
      </svg>
    ),
  },
];

const faqs = [
  {
    q: "Is my financial data safe?",
    a: "Yes. AccountingQB runs entirely on your machine. Your financial data flows directly between your computer and QuickBooks — it never passes through our servers. We use a zero-knowledge architecture by design.",
  },
  {
    q: "Do I need to know how to code?",
    a: "Not at all. Install the extension in Claude Desktop with one click, connect your QuickBooks account, and start asking questions in plain English.",
  },
  {
    q: "What happens after the 14-day trial?",
    a: "You keep access to 25 essential read-only tools for free. To continue using all 91 tools including write operations, tax prep, and advanced analytics, choose a paid plan.",
  },
  {
    q: "Can I use this with QuickBooks Desktop?",
    a: "AccountingQB currently supports QuickBooks Online only. QuickBooks Desktop support is on our roadmap.",
  },
  {
    q: "What Claude apps does this work with?",
    a: "AccountingQB works with Claude Desktop (via MCP extension) and Cowork (via plugin). Any app that supports MCP servers can use it.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel your subscription at any time from your billing portal. No contracts, no cancellation fees.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Nav */}
      <nav className="fixed top-0 z-50 w-full border-b border-white/10 bg-slate-900/80 backdrop-blur-lg">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="/" className="text-lg font-bold text-white">
            Accounting<span className="text-blue-400">QB</span>
          </a>
          <div className="hidden items-center gap-8 sm:flex">
            <a href="#features" className="text-sm text-gray-300 transition hover:text-white">
              Features
            </a>
            <a href="#how-it-works" className="text-sm text-gray-300 transition hover:text-white">
              How It Works
            </a>
            <a href="#pricing" className="text-sm text-gray-300 transition hover:text-white">
              Pricing
            </a>
            <a href="#faq" className="text-sm text-gray-300 transition hover:text-white">
              FAQ
            </a>
          </div>
          <a
            href="#pricing"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
          >
            Get Started
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 pt-24 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(59,130,246,0.15),transparent_50%)]" />
        <div className="relative mx-auto max-w-6xl px-6 py-24 sm:py-32 lg:py-40">
          <div className="text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
              <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
              Now available for Claude Desktop &amp; Cowork
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              Your QuickBooks.
              <br />
              <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                Powered by AI.
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-gray-300">
              91 tools connecting Claude to your QuickBooks Online. Run reports,
              reconcile books, prep for taxes, detect anomalies — all through
              natural conversation. Your financial data never leaves your machine.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <a
                href="#pricing"
                className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500 hover:shadow-blue-500/30"
              >
                Start Free Trial
              </a>
              <a
                href="#how-it-works"
                className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                See How It Works
              </a>
            </div>
            <p className="mt-4 text-sm text-gray-400">
              14-day free trial &middot; No credit card required &middot; Cancel anytime
            </p>
          </div>
        </div>
      </section>

      {/* Trust Bar */}
      <section className="border-b border-gray-100 bg-gray-50 py-8">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex flex-col items-center justify-center gap-6 sm:flex-row sm:gap-12">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              Zero-knowledge architecture
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
              Encrypted token storage
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              SOC 2 compliant infrastructure
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-24">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to manage your books with AI
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Built by an entrepreneur, for entrepreneurs. Every tool we wished existed.
          </p>
        </div>
        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-gray-200 p-8 transition hover:border-blue-200 hover:shadow-lg"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50">
                {f.icon}
              </div>
              <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-gray-600">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="bg-gray-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
            Up and running in 3 minutes
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-center text-lg text-gray-600">
            No coding. No complex setup. Just install, connect, and go.
          </p>
          <div className="mt-16 grid gap-12 sm:grid-cols-3">
            {[
              {
                step: "1",
                title: "Install the Extension",
                desc: "One-click install in Claude Desktop or Cowork. No coding, no terminal commands.",
              },
              {
                step: "2",
                title: "Connect QuickBooks",
                desc: "Authorize with your QuickBooks Online account. OAuth handles the rest securely.",
              },
              {
                step: "3",
                title: "Start Talking to Your Books",
                desc: 'Ask Claude anything about your finances. "What\'s my burn rate?" "Find missing deductions." It has 91 tools ready.',
              },
            ].map((s) => (
              <div key={s.step} className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-lg font-bold text-white">
                  {s.step}
                </div>
                <h3 className="mt-4 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-gray-600">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
          What you can do with AccountingQB
        </h2>
        <div className="mt-16 grid gap-6 sm:grid-cols-2">
          {[
            {
              title: "Tax Prep in Minutes",
              desc: "Generate your Schedule C, find missed deductions, estimate quarterly payments, and get 1099 reports — all in a conversation.",
              tag: "Tax Season",
            },
            {
              title: "Monthly Close Workflow",
              desc: "Run a books health audit, resolve uncategorized transactions, fix unknown vendors, and close your month with a scored checklist.",
              tag: "Bookkeeping",
            },
            {
              title: "Cash Flow Intelligence",
              desc: "Forecast cash flow, calculate runway, compare periods, and track burn rate trends — without touching a spreadsheet.",
              tag: "Financial Analysis",
            },
            {
              title: "Anomaly Detection",
              desc: "Automatically flag duplicate payments, unusual amounts, round-number patterns, and vendor concentration risks.",
              tag: "Risk Management",
            },
          ].map((uc) => (
            <div key={uc.title} className="rounded-2xl border border-gray-200 p-8">
              <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-600">
                {uc.tag}
              </span>
              <h3 className="mt-4 text-lg font-semibold">{uc.title}</h3>
              <p className="mt-2 text-gray-600">{uc.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="bg-gray-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Simple, transparent pricing
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Start with a 14-day free trial. No credit card required.
            </p>
          </div>
          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {tiers.map((t) => (
              <div
                key={t.name}
                className={`relative rounded-2xl border bg-white p-8 ${
                  t.highlight
                    ? "border-blue-600 shadow-xl shadow-blue-600/10 ring-1 ring-blue-600"
                    : "border-gray-200"
                }`}
              >
                {t.highlight && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-4 py-1 text-xs font-semibold text-white">
                    Most Popular
                  </div>
                )}
                <h3 className="text-lg font-semibold">{t.name}</h3>
                <p className="mt-1 text-sm text-gray-500">{t.description}</p>
                <div className="mt-6">
                  <span className="text-4xl font-bold">{t.price}</span>
                  <span className="text-gray-500">{t.period}</span>
                </div>
                <a
                  href={t.href}
                  className={`mt-8 block w-full rounded-lg py-3 text-center text-sm font-semibold transition ${
                    t.highlight
                      ? "bg-blue-600 text-white hover:bg-blue-500"
                      : "border border-gray-300 text-gray-900 hover:bg-gray-50"
                  }`}
                >
                  {t.cta}
                </a>
                <ul className="mt-8 space-y-3">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-3 text-sm">
                      <svg
                        className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-3xl px-6 py-24">
        <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
          Frequently asked questions
        </h2>
        <div className="mt-16 space-y-8">
          {faqs.map((faq) => (
            <div key={faq.q} className="border-b border-gray-200 pb-8">
              <h3 className="text-lg font-semibold">{faq.q}</h3>
              <p className="mt-3 text-gray-600">{faq.a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 py-24 text-white">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to put AI in charge of your books?
          </h2>
          <p className="mt-4 text-lg text-gray-300">
            Join entrepreneurs who are saving hours every week on bookkeeping and tax prep.
          </p>
          <a
            href="#pricing"
            className="mt-8 inline-block rounded-lg bg-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
          >
            Start Your Free Trial
          </a>
          <p className="mt-4 text-sm text-gray-400">
            14-day free trial &middot; No credit card required
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="grid gap-8 sm:grid-cols-3">
            <div>
              <a href="/" className="text-lg font-bold text-gray-900">
                Accounting<span className="text-blue-600">QB</span>
              </a>
              <p className="mt-3 text-sm text-gray-500">
                AI-powered QuickBooks tools for Claude Desktop and Cowork. Built by entrepreneurs, for entrepreneurs.
              </p>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-900">Product</h4>
              <ul className="mt-3 space-y-2 text-sm text-gray-500">
                <li><a href="#features" className="hover:text-gray-900">Features</a></li>
                <li><a href="#pricing" className="hover:text-gray-900">Pricing</a></li>
                <li><a href="#faq" className="hover:text-gray-900">FAQ</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-900">Legal</h4>
              <ul className="mt-3 space-y-2 text-sm text-gray-500">
                <li><a href="/privacy" className="hover:text-gray-900">Privacy Policy</a></li>
                <li><a href="/terms" className="hover:text-gray-900">Terms of Service</a></li>
                <li><a href="mailto:support@accountingqb.com" className="hover:text-gray-900">Contact</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 border-t border-gray-100 pt-8">
            <p className="text-center text-sm text-gray-400">
              &copy; {new Date().getFullYear()} AccountingQB. All rights reserved.
              AccountingQB is not affiliated with Intuit or QuickBooks.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
