import type { Metadata } from "next";
import data from "@/lib/tax-changes.json";

export const metadata: Metadata = {
  title: "2026 vs 2025 Tax Changes — Sourced Reference",
  description:
    "Every 2026 vs 2025 US federal, US state, and Canadian tax rate/threshold change — with its effective date, governing statute, and a link to the official source. OBBBA bonus depreciation, SALT cap, 1099-NEC, brackets, mileage, CPP, GST/HST.",
  alternates: { canonical: "/tax-changes" },
};

interface Change {
  category: string;
  item: string;
  from: string;
  to: string;
  effective: string;
  statute: string;
  source: string;
  source_url: string;
  verified: string;
}

const CATEGORY_ORDER = ["US Federal", "US State", "Canada"];

export default function TaxChangesPage() {
  const changes = data.changes as Change[];
  const byCat = CATEGORY_ORDER.map((cat) => ({
    cat,
    rows: changes.filter((c) => c.category === cat),
  })).filter((g) => g.rows.length > 0);

  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <nav className="border-b border-white/[0.06] bg-[#0a0e1a]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <a href="/" className="text-lg font-bold text-gray-100">
            Accounting
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              QB
            </span>
          </a>
          <a href="/" className="text-sm text-gray-400 hover:text-gray-100">
            &larr; Back to home
          </a>
        </div>
      </nav>

      <article className="mx-auto max-w-5xl px-6 py-16">
        <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/20 bg-cyan-500/[0.08] px-3 py-1 text-xs font-medium text-cyan-300">
          Tax reference · {data.count} tracked changes
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-100 sm:text-4xl">
          2026 vs 2025 Tax Changes
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-gray-400 leading-relaxed">
          What changed for the {data.yearTo} tax year — US federal, US state, and
          Canadian rate and threshold changes in one place. Every figure carries
          its effective date, the statute behind it, and a link to the official
          source. No figure without where it came from.
        </p>
        <p className="mt-3 text-sm text-gray-500">
          TAX_DATA v{data.taxDataVersion} · verified {data.verified}. This tracks
          the marquee changes a bookkeeper or CPA needs at hand — it is not
          comprehensive tax law, and it is a reference, not advice.
        </p>

        {byCat.map(({ cat, rows }) => (
          <section key={cat} className="mt-12">
            <h2 className="text-xl font-semibold text-gray-100">{cat}</h2>
            <div className="mt-4 overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/[0.03] text-gray-400">
                    <th className="px-4 py-3 font-medium">Item</th>
                    <th className="px-4 py-3 font-medium">2025</th>
                    <th className="px-4 py-3 font-medium">2026</th>
                    <th className="px-4 py-3 font-medium">Effective</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/5 last:border-0 align-top"
                    >
                      <td className="px-4 py-3 text-gray-200">{c.item}</td>
                      <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                        {c.from}
                      </td>
                      <td className="px-4 py-3 font-semibold text-cyan-300 whitespace-nowrap">
                        {c.to}
                      </td>
                      <td className="px-4 py-3 text-gray-400">{c.effective}</td>
                      <td className="px-4 py-3">
                        <a
                          href={c.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-400 hover:underline"
                          title={c.source}
                        >
                          {c.statute || "source"} ↗
                        </a>
                        <div className="text-xs text-gray-600">
                          verified {c.verified}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}

        <div className="mt-12 rounded-xl border border-white/10 bg-[#131a2e] p-6 text-sm text-gray-400 leading-relaxed">
          <p>
            <strong className="text-gray-200">How this stays current:</strong>{" "}
            these figures come straight from the same sourced, dated, hash-chained
            tax-data control plane that powers AccountingQB&rsquo;s Schedule&nbsp;C,
            quarterly-estimate, depreciation, and GST/HST tools — so the reference
            and the calculators can never disagree. Inside Claude, ask{" "}
            <code className="text-gray-300">qb_tax_law_changes</code> for the same
            data, filtered by topic or jurisdiction.
          </p>
          <p className="mt-3 text-gray-500">
            Reference only — not tax, legal, or accounting advice. Verify against
            official IRS / CRA / state sources and confirm with a qualified tax
            professional before filing. See our{" "}
            <a href="/security" className="text-cyan-400 hover:underline">
              Security page
            </a>{" "}
            for how the data plane is sourced and verified.
          </p>
        </div>
      </article>
    </main>
  );
}
