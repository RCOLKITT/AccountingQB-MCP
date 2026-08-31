import type { Metadata } from "next";
import { headers } from "next/headers";
import LandingNav from "@/components/nav/LandingNav";
import Footer from "@/components/Footer";
import { tiers, comparisonRows, pricingFaqs } from "@/lib/pricing";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple monthly plans for AccountingQB — Solopreneur $39, Business $99, Firm $299. 14-day free trial, no credit card, cancel anytime. US & Canadian tax prep on every plan.",
  alternates: { canonical: "/pricing" },
};

function CheckIcon() {
  return (
    <svg
      className="mt-0.5 h-5 w-5 flex-shrink-0 text-cyan-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

export default async function PricingPage() {
  const isCA = (await headers()).get("x-vercel-ip-country") === "CA";

  // FAQPage structured data (D5.3 / D5.5) — helps SEO and AI answer engines.
  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: pricingFaqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
      />
      <LandingNav />

      {/* HERO */}
      <section className="mx-auto max-w-6xl px-6 pt-32 pb-10 text-center sm:pt-36">
        <div className="mb-4 inline-flex items-center rounded-full border border-green-500/20 bg-green-500/[0.08] px-3 py-1 text-xs font-medium text-green-300">
          Pricing
        </div>
        <h1 className="mx-auto max-w-2xl text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Less than the cost of{" "}
          <span className="font-serif font-medium italic text-cyan-300">
            one hour of bookkeeping.
          </span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-[16px] leading-relaxed text-gray-400">
          Every plan includes all 131 tools and US &amp; Canadian tax prep, and
          works with Claude, the downloadable desktop app, or our hosted
          connector. Start with a 14-day free trial — no credit card required,
          cancel anytime.
        </p>
      </section>

      {/* TIER CARDS */}
      <section className="mx-auto max-w-6xl px-6">
        <div className="grid gap-6 lg:grid-cols-3">
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
              <h2 className="text-lg font-semibold text-white">{t.name}</h2>
              <p className="mt-1 text-sm text-gray-500">{t.description}</p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-5xl font-bold text-white">
                  {isCA ? t.priceCad : t.price}
                </span>
                <span className="text-gray-500">{t.period}</span>
              </div>
              {isCA && (
                <p className="mt-1 text-xs text-gray-500">Billed in CAD</p>
              )}
              {t.savings && (
                <p className="mt-2 text-xs font-medium text-cyan-400/80">
                  {t.savings}
                </p>
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
                  <li
                    key={f}
                    className="flex items-start gap-3 text-sm text-gray-400"
                  >
                    <CheckIcon />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-gray-500">
          All plans include a 14-day free trial with full access. No credit card
          required.
        </p>
      </section>

      {/* COMPARISON TABLE */}
      <section className="mx-auto max-w-4xl px-6 py-20">
        <h2 className="text-center text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Compare plans
        </h2>
        <div className="mt-8 overflow-x-auto rounded-2xl border border-white/[0.08]">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[#0c1120]">
                <th className="px-4 py-4 text-left font-medium text-gray-400">
                  Feature
                </th>
                {tiers.map((t) => (
                  <th
                    key={t.name}
                    className={`px-4 py-4 text-center font-semibold ${t.highlight ? "text-cyan-300" : "text-white"}`}
                  >
                    {t.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((row, i) => (
                <tr key={row.label} className={i % 2 ? "bg-white/[0.015]" : ""}>
                  <td className="px-4 py-3 text-left text-gray-300">
                    {row.label}
                  </td>
                  {row.values.map((v, j) => (
                    <td key={j} className="px-4 py-3 text-center text-gray-300">
                      {v === "✓" ? (
                        <span
                          className="inline-block text-cyan-400"
                          aria-label="Included"
                        >
                          ✓
                        </span>
                      ) : v === "—" ? (
                        <span
                          className="inline-block text-gray-600"
                          aria-label="Not included"
                        >
                          —
                        </span>
                      ) : (
                        v
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-center text-xs text-gray-600">
          Not a tax-filing service and not for QuickBooks Desktop yet — these
          are workpapers you or your CPA file from.
        </p>
      </section>

      {/* FAQ */}
      <section className="mx-auto max-w-3xl px-6 pb-24">
        <h2 className="text-center text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Pricing questions
        </h2>
        <div className="mt-8 space-y-4">
          {pricingFaqs.map((f) => (
            <div
              key={f.q}
              className="rounded-xl border border-white/[0.08] bg-[#131a2e] p-5"
            >
              <h3 className="text-[15px] font-semibold text-white">{f.q}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-gray-400">
                {f.a}
              </p>
            </div>
          ))}
        </div>
      </section>

      <Footer />
    </main>
  );
}
