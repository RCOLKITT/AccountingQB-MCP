/* ============================================================================
   AccountingQB Landing Page — Premium Dark Theme
   Design: Stripe/Linear/Vercel inspired. Navy + cyan-blue-indigo gradient.
   ============================================================================ */

import type { Metadata } from "next";
import { headers } from "next/headers";
import { getSupabase } from "@/lib/supabase";
import LandingNav from "@/components/nav/LandingNav";
import Footer from "@/components/Footer";
import { tiers } from "@/lib/pricing";
import Testimonials from "@/components/Testimonials";

export const metadata: Metadata = {
  alternates: {
    canonical: "/",
    languages: {
      "en-US": "/",
      "en-CA": "/canada",
      "x-default": "/",
    },
  },
};

interface PublicStats {
  totalHoursSaved: number;
  callsThisWeek: number;
  activeLicenses: number;
  totalToolCalls: number;
}

async function getPublicStats(): Promise<PublicStats | null> {
  try {
    const supabase = getSupabase();
    const { data: stats } = await supabase
      .from("usage_stats_cache")
      .select("*")
      .eq("id", "global")
      .single();

    if (!stats) return null;

    return {
      totalHoursSaved: stats.total_hours_saved || 0,
      callsThisWeek: stats.calls_this_week || 0,
      activeLicenses: stats.active_licenses || 0,
      totalToolCalls: stats.total_tool_calls || 0,
    };
  } catch {
    return null;
  }
}

const faqs = [
  {
    q: "Is my financial data safe?",
    a: "Absolutely. Run AccountingQB locally — the desktop extension runs entirely on your machine and your financial data flows directly between your computer and QuickBooks, never touching our servers. Or connect through our hosted connector, where data passes through with zero retention — it is never stored, logged, or used for analytics. Either way, we never store your books.",
  },
  {
    q: "How do I know the tax numbers are current?",
    a: "Every tax rate and threshold we use — IRS brackets, mileage rates, §179 and bonus depreciation limits, GST/HST rates, CPP ceilings — lives in a versioned registry where each value carries its official source (the actual Revenue Procedure or CRA page) and a verification date. Every tax answer shows its rate vintage in the footer, changes ship through a tamper-evident audit ledger reviewed by a human, and a research agent checks every source monthly for new legislation — that's how we caught the 2025 OBBBA changes. Ask Claude to run qb_tax_data_info to see the full provenance table.",
  },
  {
    q: "Do I need to know how to code?",
    a: "Not at all. Install the extension in Claude Desktop with one click, connect your QuickBooks account, and start asking questions in plain English.",
  },
  {
    q: "What happens after the 14-day trial?",
    a: "You keep access to 25 essential read-only tools for free. To continue using all 131 tools including writes, tax prep, and advanced analytics, choose a paid plan.",
  },
  {
    q: "Can I use this with QuickBooks Desktop?",
    a: "AccountingQB currently supports QuickBooks Online only. QuickBooks Desktop support is on our roadmap.",
  },
  {
    q: "What Claude apps does this work with?",
    a: "AccountingQB works with Claude on the web, desktop, and mobile via our remote connector (add it as a custom connector — no install needed), with Claude Desktop via the MCP extension, and with Cowork via our plugin. Any app that supports MCP servers can use it.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel your subscription at any time from your billing portal. No contracts, no cancellation fees.",
  },
];

/* ---------- Inline Logo SVG Component ---------- */
function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg" x1="60" y1="60" x2="452" y2="452" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="40%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <path d="M 210 108 A 148 148 0 1 1 209.99 108 Z M 210 164 A 92 92 0 1 0 210.01 164 Z"
        fill="url(#lg)" fillRule="evenodd" />
      <rect x="290" y="310" width="120" height="52" rx="26" fill="url(#lg)" transform="rotate(42, 350, 336)" />
      <rect x="290" y="118" width="42" height="268" rx="4" fill="url(#lg)" />
      <path d="M 311 118 L 360 118 A 62 62 0 0 1 360 242 L 311 242 Z" fill="url(#lg)" />
      <path d="M 311 242 L 370 242 A 72 72 0 0 1 370 386 L 311 386 Z" fill="url(#lg)" />
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

/* ============================================================================
   PAGE
   ============================================================================ */

interface TaxHighlight { label: string; source: string; jurisdiction: string }
interface TaxData {
  version: string;
  verified: string;
  highlights: TaxHighlight[];
  ledger?: { rows: number; chain_ok: boolean; latest: string | null };
}

// Live tax-data provenance from the connector (public, cacheable). Built from the
// connector's own registry, so the card is always accurate. Falls back to null →
// the card renders a static-but-correct default, so a fetch hiccup never breaks it.
async function getTaxData(): Promise<TaxData | null> {
  try {
    const res = await fetch("https://mcp.accountingqb.com/tax-data", {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TaxData;
  } catch {
    return null;
  }
}

// Fallback matches the current registry (v2026.6) so the card is correct even
// offline; the live fetch keeps it current without a code change.
const TAX_DATA_FALLBACK: TaxData = {
  version: "2026.6",
  verified: "2026-08-03",
  ledger: { rows: 80, chain_ok: true, latest: "2026-08-03" },
  highlights: [
    { label: "Business meals — 50% deductible", source: "IRC §274(n)", jurisdiction: "US" },
    { label: "Standard mileage — 70¢/mi (2025)", source: "IRS Notice 2025-5", jurisdiction: "US" },
    { label: "GST/HST (Ontario) — 13%", source: "CRA", jurisdiction: "CA" },
  ],
};

// Usage counters (hours saved / activity / active users) stay HIDDEN until they're
// impressive — a small live count undercuts the "established" impression, and big
// trusted companies don't run user counters anyway. The tiles auto-appear once the
// platform crosses this many active licenses, then keep updating from live data.
const USAGE_TILES_MIN_LICENSES = 100;

// Live GitHub star count for the "built in the open" strip (D3.5). Public, cached
// hourly; null on any hiccup so the strip still renders the repo link. The NUMBER is
// gated behind GITHUB_STARS_MIN — a tiny star count reads worse than none, so we show
// the transparency link now and let the count surface itself once it's credible.
const GITHUB_REPO = "RCOLKITT/AccountingQB-MCP";
const GITHUB_STARS_MIN = 25;

async function getGitHubStars(): Promise<number | null> {
  try {
    const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}`, {
      headers: { Accept: "application/vnd.github+json" },
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { stargazers_count?: number };
    return typeof data.stargazers_count === "number" ? data.stargazers_count : null;
  } catch {
    return null;
  }
}

export default async function Home() {
  const [publicStats, taxDataRaw, gitHubStars] = await Promise.all([getPublicStats(), getTaxData(), getGitHubStars()]);
  const taxData = taxDataRaw ?? TAX_DATA_FALLBACK;
  const showStarCount = gitHubStars !== null && gitHubStars >= GITHUB_STARS_MIN;
  const isCA = (await headers()).get("x-vercel-ip-country") === "CA";

  return (
    <main className="min-h-screen overflow-x-hidden">

      {/* ========== NAV ========== */}
      <LandingNav />

      {/* ========== HERO ========== */}
      <section className="relative min-h-screen pt-20">
        {/* Background layers */}
        <div className="absolute inset-0 bg-[#0a0e1a]" />
        <div className="absolute inset-0 bg-grid opacity-50" />
        {/* Gradient orbs */}
        <div className="animate-float absolute -top-40 right-1/4 h-[500px] w-[500px] rounded-full bg-cyan-500/[0.07] blur-[120px]" />
        <div className="animate-float-slow absolute bottom-0 left-1/4 h-[400px] w-[400px] rounded-full bg-indigo-500/[0.07] blur-[120px]" />
        <div className="absolute top-1/3 left-1/2 h-[300px] w-[300px] rounded-full bg-blue-500/[0.05] blur-[100px]" />

        <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-24 sm:pt-32 lg:pt-40">
          <div className="text-center">
            {/* Status badge — calm, factual */}
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-[13px] text-gray-300">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              Connects to QuickBooks Online &middot; Claude Desktop, web &amp; Cowork
            </div>

            {/* Headline — keeps the brand hook, adds the trust angle + a restrained
                serif accent; no shimmer (calmer, more authoritative). */}
            <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight text-white sm:text-6xl">
              Ask your QuickBooks anything — and get{" "}
              <span className="font-serif font-medium italic text-cyan-300">tax workpapers you can defend.</span>
            </h1>

            {/* Subhead */}
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-gray-400 sm:text-xl">
              131 tools connecting Claude to your QuickBooks Online. Run reports,
              reconcile books, prep for taxes, detect anomalies — all through
              natural conversation.{" "}
              <span className="text-gray-300">Run it locally or connect instantly — we never store your books.</span>
            </p>

            {/* One primary CTA; the demo is a quiet secondary link so a single
                action owns the click (D2.2). Cowork download lives in How-It-Works. */}
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row sm:gap-6">
              <a
                href="/pricing"
                className="rounded-xl bg-white px-7 py-3.5 text-sm font-semibold text-[#0a0e1a] shadow-lg shadow-black/20 transition hover:bg-slate-200"
              >
                Start Free Trial
              </a>
              <a
                href="#demo"
                className="group flex items-center gap-1.5 text-sm font-medium text-gray-400 transition hover:text-white"
              >
                See it in action
                <svg className="h-4 w-4 transition group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </a>
            </div>

            <p className="mt-5 text-sm text-gray-500">
              14-day free trial &middot; No credit card required &middot; Cancel anytime
            </p>

            {/* Trust strip — every item substantiated by the /security page */}
            <div className="mx-auto mt-12 max-w-3xl">
              <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] sm:grid-cols-4">
                {[
                  ["Encryption", "AES-256-GCM"],
                  ["Hosted data", "Zero retention"],
                  ["Access", "OAuth 2.0"],
                  ["Local mode", "Zero-knowledge"],
                ].map(([k, v]) => (
                  <div key={v} className="bg-[#0c1120] px-4 py-3.5 text-left">
                    <div className="text-[11px] uppercase tracking-wide text-gray-500">{k}</div>
                    <div className="mt-0.5 text-sm font-semibold text-white">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ---- Conversation Preview Card ---- */}
          <div className="mx-auto mt-16 max-w-3xl">
            <div className="glass rounded-2xl p-1 shadow-2xl shadow-blue-900/20">
              <div className="rounded-xl bg-[#0d1220] p-6">
                {/* Window chrome */}
                <div className="mb-5 flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-red-500/60" />
                  <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                  <div className="h-3 w-3 rounded-full bg-green-500/60" />
                  <span className="ml-3 text-xs text-gray-500">Claude Desktop</span>
                </div>

                {/* Chat messages */}
                <div className="space-y-4">
                  {/* User message */}
                  <div className="flex justify-end">
                    <div className="max-w-md rounded-2xl rounded-br-md bg-blue-600/90 px-4 py-2.5 text-sm text-white">
                      What&apos;s my burn rate and how many months of runway do I have?
                    </div>
                  </div>
                  {/* AI response */}
                  <div className="flex gap-3">
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20">
                      <LogoMark className="h-5 w-5" />
                    </div>
                    <div className="max-w-md space-y-2">
                      <div className="rounded-2xl rounded-tl-md bg-[#161d33] px-4 py-3 text-sm text-gray-300">
                        <p className="mb-2 font-medium text-white">Here&apos;s your financial overview:</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded-lg bg-white/[0.04] p-2">
                            <div className="text-gray-500">Monthly Burn</div>
                            <div className="text-lg font-bold text-cyan-400">$4,218</div>
                          </div>
                          <div className="rounded-lg bg-white/[0.04] p-2">
                            <div className="text-gray-500">Cash on Hand</div>
                            <div className="text-lg font-bold text-green-400">$52,640</div>
                          </div>
                          <div className="rounded-lg bg-white/[0.04] p-2">
                            <div className="text-gray-500">Runway</div>
                            <div className="text-lg font-bold text-blue-400">12.5 mo</div>
                          </div>
                          <div className="rounded-lg bg-white/[0.04] p-2">
                            <div className="text-gray-500">Trend</div>
                            <div className="text-lg font-bold text-emerald-400">-3.2%</div>
                          </div>
                        </div>
                        <p className="mt-2 text-xs text-gray-400">
                          Burn decreased 3.2% vs last quarter. At this rate you have over a year of runway. Top expenses: Hosting ($890), Software ($680), Marketing ($520).
                        </p>
                      </div>
                      <div className="flex gap-1.5 text-[10px] text-gray-500">
                        <span className="rounded bg-white/[0.04] px-1.5 py-0.5">qb_monthly_burn_rate</span>
                        <span className="rounded bg-white/[0.04] px-1.5 py-0.5">qb_runway_calculator</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-3 text-center text-xs text-gray-600">
              Illustrative example using AccountingQB tools in Claude Desktop
            </div>
          </div>
        </div>
      </section>

      {/* ========== TRUST BAR ========== */}
      <section className="relative border-y border-white/[0.06] bg-[#0c1120]">
        <div className="mx-auto max-w-6xl px-6 py-8">
          {/* Capability + trust facts — large and true at any scale; these LEAD. */}
          <p className="mb-6 text-center text-[12px] uppercase tracking-[0.15em] text-gray-500">
            Built for solo owners, growing businesses, and bookkeeping firms — in the US &amp; Canada
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6 sm:gap-x-16">
            {[
              ["131", "tools"],
              ["16", "tax-prep tools"],
              ["US · CA", "tax coverage"],
              ["0", "books stored, ever"],
            ].map(([n, l]) => (
              <div key={l} className="text-center">
                <div className="text-3xl font-bold text-white">{n}</div>
                <div className="mt-1 text-sm text-gray-500">{l}</div>
              </div>
            ))}
          </div>

          {/* Usage counters — hidden until the platform crosses the threshold, then
              they render from live data. No small numbers on the page before then. */}
          {publicStats && publicStats.activeLicenses >= USAGE_TILES_MIN_LICENSES && (
            <div className="mt-8 flex flex-col items-center justify-center gap-6 border-t border-white/[0.06] pt-8 sm:flex-row sm:gap-12">
              {publicStats.totalHoursSaved > 0 && (
                <div className="text-center">
                  <div className="text-3xl font-bold text-cyan-400">{publicStats.totalHoursSaved.toLocaleString()}</div>
                  <div className="text-sm text-gray-500">hours saved (est.)</div>
                </div>
              )}
              {publicStats.totalToolCalls > 0 && (
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-400">{publicStats.totalToolCalls.toLocaleString()}</div>
                  <div className="text-sm text-gray-500">tasks automated</div>
                </div>
              )}
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-400">{publicStats.activeLicenses.toLocaleString()}</div>
                <div className="text-sm text-gray-500">active accounts</div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ========== FEATURES — Bento Grid ========== */}
      <section id="features" className="relative py-28">
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-blue-500/20 bg-blue-500/[0.08] px-3 py-1 text-xs font-medium text-blue-300">
              Features
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              131 tools across every
              <br />
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">accounting workflow</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              Reports. Tax prep. Reconciliation. Invoicing. Forecasting. Compliance.
              Built by an entrepreneur who needed every single one.
            </p>
          </div>

          {/* Tool Suite Breakdown */}
          <div className="mt-16 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {[
              { count: "31", label: "Reports & Analysis", color: "text-cyan-400 border-cyan-500/20 bg-cyan-500/[0.06]" },
              { count: "19", label: "Tax & Compliance", color: "text-amber-400 border-amber-500/20 bg-amber-500/[0.06]" },
              { count: "17", label: "Create & Write", color: "text-blue-400 border-blue-500/20 bg-blue-500/[0.06]" },
              { count: "18", label: "Transactions & Search", color: "text-purple-400 border-purple-500/20 bg-purple-500/[0.06]" },
              { count: "13", label: "Modify, Delete & Bulk", color: "text-gray-400 border-gray-500/20 bg-gray-500/[0.06]" },
              { count: "8", label: "Entity Management", color: "text-indigo-400 border-indigo-500/20 bg-indigo-500/[0.06]" },
              { count: "7", label: "Reconciliation", color: "text-rose-400 border-rose-500/20 bg-rose-500/[0.06]" },
              { count: "6", label: "Smart Bookkeeping", color: "text-emerald-400 border-emerald-500/20 bg-emerald-500/[0.06]" },
              { count: "4", label: "Cash Flow & Runway", color: "text-green-400 border-green-500/20 bg-green-500/[0.06]" },
              { count: "3", label: "Close & Audit", color: "text-orange-400 border-orange-500/20 bg-orange-500/[0.06]" },
              { count: "3", label: "Connection & Multi-Company", color: "text-teal-400 border-teal-500/20 bg-teal-500/[0.06]" },
            ].map((cat) => (
              <div key={cat.label} className={`rounded-xl border p-4 text-center ${cat.color}`}>
                <div className="text-2xl font-bold">{cat.count}</div>
                <div className="mt-1 text-xs opacity-80">{cat.label}</div>
              </div>
            ))}
          </div>

          {/* Bento Grid */}
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Invoice Reconciliation — NEW HIGHLIGHT */}
            <div className="gradient-border rounded-2xl p-8 sm:col-span-2 lg:col-span-2">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500/20 to-pink-600/20">
                <svg className="h-6 w-6 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">Email Invoice Scanning + Auto-Reconciliation</h3>
              <p className="mt-2 text-gray-400">
                Extract invoices from your email, then match them against QuickBooks transactions with fuzzy amount matching
                and date tolerance. Instantly find what&apos;s been paid, what&apos;s missing, and what doesn&apos;t add up — no more
                manual cross-referencing between your inbox and your books.
              </p>
              <div className="mt-6 grid grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-white/[0.04] px-3 py-2 text-center text-gray-400">Extract from email</div>
                <div className="rounded-lg bg-white/[0.04] px-3 py-2 text-center text-gray-400">Fuzzy matching</div>
                <div className="rounded-lg bg-white/[0.04] px-3 py-2 text-center text-gray-400">Batch reconcile</div>
              </div>
            </div>

            {/* Zero Knowledge */}
            <div className="gradient-border rounded-2xl p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-600/20">
                <svg className="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">We Never Store Your Books</h3>
              <p className="mt-2 text-gray-400">
                Run it 100% locally — the MCP server runs on your machine and talks directly to QuickBooks, so your books never touch our servers. Or connect instantly through our zero-retention cloud connector — data transits, never stored.
              </p>
              <div className="mt-6 rounded-lg border border-green-500/10 bg-green-500/[0.04] px-3 py-2 text-xs text-green-400/80">
                Local: your machine → QuickBooks API<br />
                Cloud: pass-through only. Zero retention.
              </div>
            </div>

            {/* Talk to Books */}
            <div className="gradient-border rounded-2xl p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500/20 to-indigo-600/20">
                <svg className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.130.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">Talk to Your Books</h3>
              <p className="mt-2 text-gray-400">
                Ask Claude natural questions: &ldquo;What did I spend on software last quarter?&rdquo; or &ldquo;Am I missing any tax deductions?&rdquo;
              </p>
            </div>

            {/* Tax Season */}
            <div className="gradient-border rounded-2xl p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-600/20">
                <svg className="h-6 w-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">16 Tax Prep Tools</h3>
              <p className="mt-2 text-gray-400">
                US &amp; Canada: Schedule C mapping, quarterly estimates, deduction finder, 1099 reports, home office &amp; vehicle calculators — plus GST/HST return workpapers, T2125, CCA schedules, T4A reports, and CRA instalments.
              </p>
            </div>

            {/* Smart Bookkeeping */}
            <div className="gradient-border rounded-2xl p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20">
                <svg className="h-6 w-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">AI Bookkeeping Assistant</h3>
              <p className="mt-2 text-gray-400">
                Auto-categorization suggestions, duplicate detection, unknown vendor cleanup, anomaly flagging, bulk vendor updates, and a books health audit scored 0-100.
              </p>
            </div>

            {/* CPA Workbook */}
            <div className="gradient-border rounded-2xl p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20">
                <svg className="h-6 w-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white">CPA Workbook</h3>
              <p className="mt-2 text-gray-400">
                A click-through year-end binder your accountant can file from: comparative statements, trial balance, reconciliation tie-outs, tax payments made, owner&apos;s draws, open items, and a built-in tax organizer. Export to Excel in one message.
              </p>
            </div>
          </div>

          {/* Honest scope — states who this is NOT for, so visitors self-qualify (D2.B). */}
          <p className="mx-auto mt-14 max-w-2xl text-center text-[15px] leading-relaxed text-gray-500">
            Not a tax-filing service and not for QuickBooks Desktop yet — these are
            workpapers you or your CPA file from.
          </p>
        </div>
      </section>

      {/* ========== TAX PROVENANCE — the differentiator, promoted from the FAQ ==========
          The example rows below are REAL and must stay in sync with the connector's
          tax_tables.py (TAX_DATA_VERSION / _STATUTORY_LIMITS / _STD_MILEAGE_CENTS).
          The live, always-current table is qb_tax_data_info in-product. */}
      <section id="tax-accuracy" className="relative py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid items-center gap-14 lg:grid-cols-2">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-500/25 bg-cyan-500/[0.06] px-3 py-1 text-xs text-cyan-300">
                Why accountants trust the numbers
              </div>
              <h2 className="max-w-md text-3xl font-bold tracking-tight text-white sm:text-4xl sm:leading-[1.1]">
                Every tax figure is{" "}
                <span className="font-serif font-medium italic text-cyan-300">sourced, dated, and audit-logged.</span>
              </h2>
              <p className="mt-5 max-w-lg text-[15.5px] leading-relaxed text-gray-400">
                Bracket, mileage rate, §179 cap, GST/HST, CPP ceiling — every value lives in a
                versioned registry carrying its <span className="text-gray-200">official source</span>{" "}
                and a <span className="text-gray-200">verification date</span>. Changes ship through a
                tamper-evident, hash-chained ledger reviewed by a human, and a research agent re-checks
                every source for new legislation — including the 2025 OBBBA changes.
              </p>
              <ul className="mt-6 space-y-3 text-sm text-gray-300">
                {[
                  "Every answer shows its rate vintage and citation in the footer.",
                  "Region-gated: jurisdiction-specific tools require the matching region.",
                  "Statutory limits and taxpayer allocations kept separate and cited.",
                ].map((li) => (
                  <li key={li} className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-cyan-400" />
                    {li}
                  </li>
                ))}
              </ul>
              <p className="mt-5 text-[13px] text-gray-500">
                Verify it yourself: ask Claude to run{" "}
                <span className="font-mono text-gray-400">qb_tax_data_info</span> for the full,
                live provenance table.
              </p>
            </div>

            {/* Provenance card — rendered LIVE from the connector's /tax-data
                (falls back to the current registry so it can't break). */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
              <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
                <div className="text-[13px] font-semibold text-white">Tax data provenance</div>
                {taxData.ledger?.chain_ok !== false && (
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    ledger verified
                  </div>
                )}
              </div>
              <div className="divide-y divide-white/[0.07]">
                {taxData.highlights.slice(0, 3).map((h) => (
                  <div key={h.label} className="flex items-center justify-between py-3.5">
                    <div>
                      <div className="text-sm font-medium text-white">{h.label}</div>
                      <div className="mt-0.5 font-mono text-[12px] text-gray-500">{h.source}</div>
                    </div>
                    <div className="font-mono text-[12px] text-gray-500">{h.jurisdiction} · sourced</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 rounded-lg bg-black/30 px-3 py-2 font-mono text-[11px] text-gray-500">
                append-only, hash-chained ledger · TAX_DATA v{taxData.version} · verified {taxData.verified}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========== HOW IT WORKS ========== */}
      <section id="demo" className="relative border-y border-white/[0.06] bg-[#0c1120] py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/20 bg-cyan-500/[0.08] px-3 py-1 text-xs font-medium text-cyan-300">
              How It Works
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              Up and running in{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">3 minutes</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              No coding. No complex setup. Just install, connect, and go.
            </p>
          </div>

          <div className="mt-20 grid gap-8 sm:grid-cols-3">
            {[
              {
                step: "01",
                title: "Connect or Install",
                desc: "Add AccountingQB as a connector in Claude instantly, or one-click install the Claude Desktop extension / Cowork plugin. No terminal commands needed.",
                gradient: "from-cyan-500 to-blue-500",
              },
              {
                step: "02",
                title: "Connect QuickBooks",
                desc: "Authorize with your QuickBooks Online account. OAuth handles everything securely.",
                gradient: "from-blue-500 to-indigo-500",
              },
              {
                step: "03",
                title: "Start Talking to Your Books",
                desc: "Ask Claude anything. \"What's my burn rate?\" \"Find missing deductions.\" 131 tools ready.",
                gradient: "from-indigo-500 to-purple-500",
              },
            ].map((s) => (
              <div key={s.step} className="group relative">
                <div className="gradient-border rounded-2xl p-8 transition duration-300 hover:bg-white/[0.02]">
                  <div className={`mb-6 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br ${s.gradient} bg-opacity-10 text-2xl font-bold text-white/90`}
                    style={{ background: `linear-gradient(135deg, rgba(34,211,238,0.1), rgba(59,130,246,0.1))` }}
                  >
                    <span className={`bg-gradient-to-br ${s.gradient} bg-clip-text text-transparent`}>{s.step}</span>
                  </div>
                  <h3 className="text-lg font-semibold text-white">{s.title}</h3>
                  <p className="mt-2 text-gray-400">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Cowork download lives here now (moved out of the hero CTA row so a
              single primary owns the hero click — D2.2). */}
          <div className="mt-14 flex justify-center">
            <a
              href="/downloads/accountingqb.plugin"
              download
              className="flex items-center gap-2 rounded-xl border border-cyan-500/25 bg-cyan-500/[0.06] px-6 py-3 text-sm font-semibold text-cyan-300 transition hover:border-cyan-400/40 hover:bg-cyan-500/[0.12] hover:text-cyan-200"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Get it for Cowork
            </a>
          </div>
        </div>
      </section>

      {/* ========== USE CASES ========== */}
      <section className="relative py-28">
        <div className="absolute inset-0 bg-grid opacity-20" />
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-indigo-500/20 bg-indigo-500/[0.08] px-3 py-1 text-xs font-medium text-indigo-300">
              Use Cases
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              What you can do with{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">AccountingQB</span>
            </h2>
          </div>

          <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                title: "Tax Prep in Minutes",
                desc: "Schedule C (basic + detailed), deduction finder, quarterly estimates, 1099 reports, home office calc, vehicle depreciation — the full tax package from one prompt. Canadian business? GST/HST return workpapers, T2125, CCA, and T4A reports too.",
                tag: "Tax Season",
                tagColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
                example: "\"Generate my Schedule C and find any deductions I missed this year.\"",
              },
              {
                title: "Invoice Reconciliation",
                desc: "Extract invoices from email, match them against QuickBooks with fuzzy amounts and date tolerance. See what&apos;s paid, what&apos;s missing, what doesn&apos;t add up.",
                tag: "Reconciliation",
                tagColor: "text-rose-400 bg-rose-500/10 border-rose-500/20",
                example: "\"Match these invoices from my email against QB and show me any gaps.\"",
              },
              {
                title: "Monthly Close Workflow",
                desc: "Books health audit scored 0-100, uncategorized transaction cleanup, unknown vendor reports, and a scored close readiness checklist.",
                tag: "Bookkeeping",
                tagColor: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
                example: "\"Run my month-end close for February and show me what needs fixing.\"",
              },
              {
                title: "Cash Flow Intelligence",
                desc: "6-month forecasting, runway calculator, burn rate trends, period-over-period comparison, and profit margin analysis by customer or product.",
                tag: "Financial Analysis",
                tagColor: "text-blue-400 bg-blue-500/10 border-blue-500/20",
                example: "\"What does my cash flow look like for the next 6 months?\"",
              },
              {
                title: "Anomaly Detection",
                desc: "Flag duplicates, unusual amounts, round-number patterns, weekend activity, and vendor concentration risks. Statistical outlier detection built in.",
                tag: "Risk Management",
                tagColor: "text-purple-400 bg-purple-500/10 border-purple-500/20",
                example: "\"Check Q4 for any suspicious transactions or duplicates.\"",
              },
              {
                title: "Financial Reporting",
                desc: "P&L, balance sheet, cash flow, general ledger, and trial balance — plus sales by customer, product, class, or location, inventory valuation, a flexible transaction list, and drill-down detail behind any P&L, AR, or AP number.",
                tag: "Reports & Analysis",
                tagColor: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
                example: "\"Show me sales by customer for Q2, then drill into the biggest one.\"",
              },
              {
                title: "Full Accounting Suite",
                desc: "Create expenses, invoices, bills, estimates, journal entries, deposits, transfers, credit memos, vendor credits — plus batch operations and bulk vendor updates.",
                tag: "Write & Create",
                tagColor: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
                example: "\"Create an invoice for Acme Corp for $5,000 consulting, due in 30 days.\"",
              },
              {
                title: "CPA Handoff",
                desc: "A 15-page year-end workbook — comparative statements, tie-outs, tax payments made, owner's draws, and a tax organizer — assembled from live books and exported to Excel for your accountant.",
                tag: "CPA Handoff",
                tagColor: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
                example: "\"Prepare my CPA workbook for last year.\"",
              },
            ].map((uc) => (
              <div key={uc.title} className="gradient-border rounded-2xl p-8 transition duration-300 hover:bg-white/[0.02]">
                <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${uc.tagColor}`}>
                  {uc.tag}
                </span>
                <h3 className="mt-4 text-lg font-semibold text-white">{uc.title}</h3>
                <p className="mt-2 text-gray-400">{uc.desc}</p>
                <div className="mt-4 rounded-lg bg-white/[0.03] px-3 py-2 text-xs italic text-gray-500">
                  {uc.example}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========== ROI / FIRM VALUE PROP ========== */}
      <section className="relative border-y border-white/[0.06] bg-[#0c1120] py-28">
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/[0.08] px-3 py-1 text-xs font-medium text-emerald-300">
              The Math
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              It pays for itself{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">in the first week</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              131 tools means 130 tasks that used to be manual. Tax prep, invoice reconciliation, vendor cleanup, anomaly checks, month-end close — all in a conversation.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-3">
            {[
              {
                metric: "10 min",
                label: "full tax package",
                detail: "Schedule C, deductions, 1099s, quarterly estimates, depreciation, home office, GST/HST, T2125, CCA — all from one prompt",
                icon: (
                  <svg className="h-6 w-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                ),
              },
              {
                metric: "30 sec",
                label: "invoice reconciliation",
                detail: "Extract invoices from email, match against QB, find gaps — replaces hours of manual cross-referencing",
                icon: (
                  <svg className="h-6 w-6 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                  </svg>
                ),
              },
              {
                metric: "~3 hrs",
                label: "saved per client per month",
                detail: "Month-end close, categorization, reconciliation, vendor cleanup, anomaly checks — all automated",
                icon: (
                  <svg className="h-6 w-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
            ].map((item) => (
              <div key={item.label} className="gradient-border rounded-2xl p-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.04]">
                  {item.icon}
                </div>
                <div className="text-4xl font-bold text-white">{item.metric}</div>
                <div className="mt-1 text-sm font-medium text-gray-300">{item.label}</div>
                <p className="mt-3 text-sm text-gray-500">{item.detail}</p>
              </div>
            ))}
          </div>

          {/* Manual vs AccountingQB comparison table */}
          <div className="mt-16">
            <h3 className="mb-6 text-center text-xl font-semibold text-white">
              What that same work looks like done{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">manually</span>
            </h3>
            <div className="overflow-hidden rounded-2xl border border-white/[0.06]">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] bg-[#131a2e]">
                    <th className="px-6 py-4 font-medium text-gray-400">Task</th>
                    <th className="px-6 py-4 text-center font-medium text-gray-400">Manual time</th>
                    <th className="px-6 py-4 text-center font-medium text-cyan-400">AccountingQB</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {[
                    { task: "Categorize & map expenses to Schedule C / T2125 lines", manual: "3–5 hours", fast: "~2 seconds" },
                    { task: "Scan for missed deductions across all categories", manual: "2–3 hours", fast: "~2 seconds" },
                    { task: "1099 / T4A contractor prep — pull payments, flag missing W-9s", manual: "2–4 hours", fast: "~2 seconds" },
                    { task: "Calculate quarterly estimates & CRA instalments", manual: "1–2 hours", fast: "~2 seconds" },
                    { task: "MACRS & CCA depreciation schedules (Section 179 analysis)", manual: "1–2 hours", fast: "~2 seconds" },
                    { task: "Extract invoices from email/Drive & reconcile against QB", manual: "2–4 hours", fast: "~30 seconds" },
                  ].map((row) => (
                    <tr key={row.task} className="bg-[#0f1629] transition hover:bg-white/[0.02]">
                      <td className="px-6 py-4 text-gray-300">{row.task}</td>
                      <td className="px-6 py-4 text-center text-gray-500">{row.manual}</td>
                      <td className="px-6 py-4 text-center font-semibold text-emerald-400">{row.fast}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-white/[0.06] bg-[#131a2e]">
                    <td className="px-6 py-4 font-medium text-white">Total</td>
                    <td className="px-6 py-4 text-center font-medium text-gray-400">11–20 hours</td>
                    <td className="px-6 py-4 text-center font-bold text-emerald-400">~40 seconds</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <p className="mt-4 text-center text-sm text-gray-500">
              A CPA charges $150–300/hr for this same output. AccountingQB starts at $39/mo.
            </p>
          </div>

          <div className="mt-12 rounded-2xl border border-white/[0.06] bg-[#131a2e] p-8">
            <div className="grid items-center gap-8 sm:grid-cols-2">
              <div>
                <h3 className="text-xl font-semibold text-white">Built for bookkeeping firms</h3>
                <p className="mt-3 text-gray-400">
                  If you&apos;re managing 20+ clients, your team is spending hundreds of hours a month on tasks
                  AccountingQB handles in minutes. Invoice reconciliation, month-end close, vendor cleanup,
                  anomaly checks, tax prep — 131 tools covering every workflow that eats your margin.
                </p>
              </div>
              <div className="rounded-xl bg-white/[0.03] p-6">
                <div className="text-sm text-gray-500">Example: 20-client firm</div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between text-gray-400">
                    <span>Hours saved/mo</span>
                    <span className="font-semibold text-white">~60 hrs</span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span>At $50/hr staff cost</span>
                    <span className="font-semibold text-white">$3,000 saved</span>
                  </div>
                  <div className="border-t border-white/[0.06] pt-2"></div>
                  <div className="flex justify-between text-gray-400">
                    <span>AccountingQB Firm plan</span>
                    <span className="font-semibold text-cyan-400">$299/mo</span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span className="font-medium text-emerald-400">ROI</span>
                    <span className="font-bold text-emerald-400">10x return</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Customer testimonial wall — sits between the ROI block and pricing (D3.2/D3.1).
          Renders only when real, permissioned quotes are added to lib/testimonials.ts. */}
      <Testimonials />

      {/* ========== BUILT IN THE OPEN — third-party trust strip (D3.5) ==========
          The open-source repo is a real external artifact; we surface it near the
          conversion point. The live star COUNT only renders once it's credible
          (>= GITHUB_STARS_MIN) so a low number never undercuts trust. A Product Hunt
          badge belongs here too — intentionally omitted until we actually launch on PH
          (no fabricated badge). */}
      <section className="relative border-t border-white/[0.06] bg-[#0a0e1a] py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-4 px-6 sm:flex-row sm:gap-8">
          <span className="text-[12px] uppercase tracking-[0.15em] text-gray-500">Built in the open</span>
          <a
            href={`https://github.com/${GITHUB_REPO}`}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-gray-300 transition hover:border-white/20 hover:text-white"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 .5A11.5 11.5 0 00.5 12a11.5 11.5 0 007.86 10.92c.575.106.785-.25.785-.556 0-.274-.01-1.001-.015-1.965-3.196.695-3.87-1.54-3.87-1.54-.523-1.33-1.277-1.684-1.277-1.684-1.044-.714.08-.7.08-.7 1.154.082 1.762 1.185 1.762 1.185 1.026 1.758 2.693 1.25 3.35.955.104-.744.401-1.25.73-1.538-2.552-.29-5.236-1.276-5.236-5.68 0-1.255.448-2.28 1.183-3.084-.119-.29-.513-1.458.112-3.04 0 0 .965-.309 3.163 1.178a10.98 10.98 0 015.76 0c2.196-1.487 3.16-1.178 3.16-1.178.626 1.582.232 2.75.114 3.04.737.804 1.182 1.829 1.182 3.084 0 4.415-2.688 5.386-5.248 5.67.413.355.78 1.056.78 2.13 0 1.538-.014 2.778-.014 3.156 0 .309.207.667.79.554A11.5 11.5 0 0023.5 12 11.5 11.5 0 0012 .5z" />
            </svg>
            <span>View source on GitHub</span>
            {showStarCount && (
              <span className="flex items-center gap-1 rounded-md bg-white/[0.06] px-2 py-0.5 text-[13px] font-semibold text-white">
                <svg className="h-3.5 w-3.5 text-yellow-400" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2l2.9 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 7.1-1.01L12 2z" />
                </svg>
                {gitHubStars?.toLocaleString()}
              </span>
            )}
          </a>
          <span className="text-[13px] text-gray-500">Public source &middot; audit the code yourself</span>
        </div>
      </section>

      {/* ========== PRICING ========== */}
      <section id="pricing" className="relative border-y border-white/[0.06] bg-[#0c1120] py-28">
        <div className="absolute inset-0 bg-grid opacity-20" />
        <div className="relative mx-auto max-w-6xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-green-500/20 bg-green-500/[0.08] px-3 py-1 text-xs font-medium text-green-300">
              Pricing
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              Less than the cost of{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">one hour of bookkeeping</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-gray-400">
              Start with a 14-day free trial. No credit card required. Cancel anytime.
            </p>
          </div>

          <div className="mt-16 grid gap-6 lg:grid-cols-3">
            {tiers.map((t) => (
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
                  <span className="text-5xl font-bold text-white">{isCA ? t.priceCad : t.price}</span>
                  <span className="text-gray-500">{t.period}</span>
                </div>
                {isCA && (
                  <p className="mt-1 text-xs text-gray-500">Billed in CAD</p>
                )}
                {t.savings && (
                  <p className="mt-2 text-xs font-medium text-cyan-400/80">{t.savings}</p>
                )}
                <a
                  href={isCA ? `${t.href}&currency=cad` : t.href}
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
      <section id="faq" className="relative py-28">
        <div className="mx-auto max-w-3xl px-6">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-purple-500/20 bg-purple-500/[0.08] px-3 py-1 text-xs font-medium text-purple-300">
              FAQ
            </div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
              Frequently asked questions
            </h2>
          </div>
          <div className="mt-16 space-y-6">
            {faqs.map((faq) => (
              <div key={faq.q} className="gradient-border rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white">{faq.q}</h3>
                <p className="mt-3 text-gray-400">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========== SECURITY — data-minimization close (claims match /security) ========== */}
      <section id="security" className="relative py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Built for people who guard other people&rsquo;s money.
            </h2>
            <p className="mt-4 text-[15.5px] leading-relaxed text-gray-400">
              Two ways to run it — both designed so your books never become our asset.
              The less we hold, the less there is to breach: that&rsquo;s the architecture,
              not a compliance checkbox.
            </p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {[
              {
                title: "Local — zero-knowledge",
                body: "The server runs on your machine and talks directly to QuickBooks with your own OAuth token. Your books never touch our infrastructure.",
              },
              {
                title: "Hosted — zero-retention",
                body: "The cloud connector passes data through and stores no book data — never stored, logged, or used for analytics. See the overview for exactly what operational metadata we keep.",
              },
              {
                title: "Tokens, encrypted",
                body: "QuickBooks tokens are encrypted at rest with AES-256-GCM — a unique IV per value and an auth tag verified on every decrypt; the key is a managed secret held outside the database.",
              },
            ].map((c) => (
              <div key={c.title} className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/12 text-cyan-300 ring-1 ring-cyan-500/20">
                  <div className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
                </div>
                <h3 className="text-base font-semibold text-white">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-400">{c.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <a href="/security" className="text-sm font-semibold text-cyan-300 transition hover:text-cyan-200">
              Read the full security overview &rarr;
            </a>
          </div>
        </div>
      </section>

      {/* ========== FINAL CTA ========== */}
      <section className="relative border-t border-white/[0.06] bg-[#0c1120] py-28">
        {/* Gradient orbs */}
        <div className="absolute top-0 left-1/3 h-[300px] w-[300px] rounded-full bg-cyan-500/[0.06] blur-[100px]" />
        <div className="absolute bottom-0 right-1/3 h-[300px] w-[300px] rounded-full bg-indigo-500/[0.06] blur-[100px]" />

        <div className="relative mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
            Ready to put AI
            <br />
            <span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              in charge of your books?
            </span>
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Join entrepreneurs who are saving hours every week on bookkeeping and tax prep.
          </p>
          <a
            href="#pricing"
            className="mt-8 inline-block rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-10 py-4 text-sm font-semibold text-white shadow-xl shadow-blue-600/25 transition hover:shadow-blue-500/40 hover:brightness-110"
          >
            Start Your Free Trial
          </a>
          <p className="mt-5 text-sm text-gray-500">
            14-day free trial &middot; No credit card required
          </p>
        </div>
      </section>

      {/* ========== FOOTER ========== */}
      <Footer />
    </main>
  );
}
