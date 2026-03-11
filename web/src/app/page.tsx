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
    icon: "📊",
  },
  {
    title: "Your Data Stays Local",
    desc: "Zero cloud routing. The MCP server runs on your machine and talks directly to QuickBooks. We never see your financial data.",
    icon: "🔒",
  },
  {
    title: "Talk to Your Books",
    desc: "Ask Claude natural questions: 'What did I spend on software last quarter?' or 'Am I missing any tax deductions?'",
    icon: "💬",
  },
  {
    title: "Tax Season Ready",
    desc: "Schedule C mapping, quarterly tax estimates, deduction finder, depreciation schedules, 1099 contractor reports, and home office calculator.",
    icon: "🧾",
  },
  {
    title: "Smart Bookkeeping",
    desc: "Auto-categorization suggestions, duplicate detection, unknown vendor reports, anomaly flagging, and books health audit scored 0-100.",
    icon: "🤖",
  },
  {
    title: "14-Day Free Trial",
    desc: "No credit card required. Full access to all 91 tools. See the value before you pay a cent.",
    icon: "🎁",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(59,130,246,0.15),transparent_50%)]" />
        <div className="relative mx-auto max-w-6xl px-6 py-24 sm:py-32 lg:py-40">
          <div className="text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
              <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
              Now available for Claude Desktop
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              Your QuickBooks.
              <br />
              <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                Powered by Claude.
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
                href="#features"
                className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                See All Features
              </a>
            </div>
            <p className="mt-4 text-sm text-gray-400">
              14-day free trial · No credit card required · Cancel anytime
            </p>
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
              <div className="text-3xl">{f.icon}</div>
              <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-gray-600">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-gray-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
            Up and running in 3 minutes
          </h2>
          <div className="mt-16 grid gap-12 sm:grid-cols-3">
            {[
              {
                step: "1",
                title: "Install the Extension",
                desc: "One-click install in Claude Desktop. No coding, no terminal commands.",
              },
              {
                step: "2",
                title: "Connect QuickBooks",
                desc: "Authorize with your QuickBooks account. OAuth handles the rest securely.",
              },
              {
                step: "3",
                title: "Start Talking to Your Books",
                desc: "Ask Claude anything about your finances. It has 91 tools at its fingertips.",
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

      {/* Pricing */}
      <section id="pricing" className="mx-auto max-w-6xl px-6 py-24">
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
              className={`relative rounded-2xl border p-8 ${
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
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-gray-50">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <p className="text-sm text-gray-500">
              &copy; {new Date().getFullYear()} QuickBooks Accounting for Claude.
              All rights reserved.
            </p>
            <div className="flex gap-6 text-sm text-gray-500">
              <a href="/privacy" className="hover:text-gray-900">
                Privacy
              </a>
              <a href="/terms" className="hover:text-gray-900">
                Terms
              </a>
              <a
                href="mailto:ryan@vasperacapital.com"
                className="hover:text-gray-900"
              >
                Contact
              </a>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
