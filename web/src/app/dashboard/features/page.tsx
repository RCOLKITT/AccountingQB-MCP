"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { redirect } from "next/navigation";
import catalog from "@/lib/tools-catalog.json";
import { TOOL_CATEGORIES } from "@/lib/tools-categories";

interface CatalogTool {
  name: string;
  description: string;
  write: boolean;
}

const BY_NAME = new Map<string, CatalogTool>(
  (catalog as CatalogTool[]).map((t) => [t.name, t]),
);
const TOTAL = catalog.length;
const WRITES = (catalog as CatalogTool[]).filter((t) => t.write).length;
const READS = TOTAL - WRITES;

function Badge({ write }: { write: boolean }) {
  return write ? (
    <span className="shrink-0 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30 px-2.5 py-0.5 text-xs font-medium">
      Writes to QuickBooks
    </span>
  ) : (
    <span className="shrink-0 rounded-full bg-green-500/15 text-green-400 border border-green-500/30 px-2.5 py-0.5 text-xs font-medium">
      Read-only
    </span>
  );
}

function anchor(name: string) {
  return name.toLowerCase().replace(/[^a-z]+/g, "-");
}

export default function FeaturesPage() {
  const { isSignedIn, isLoaded } = useUser();
  const [readOnlyOnly, setReadOnlyOnly] = useState(false);

  if (isLoaded && !isSignedIn) {
    redirect("/sign-in");
  }

  const visible = (names: string[]) =>
    names
      .map((n) => BY_NAME.get(n))
      .filter((t): t is CatalogTool => !!t && (!readOnlyOnly || !t.write));

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0a0e1a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <a
              href="/dashboard"
              className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent"
            >
              AccountingQB
            </a>
            <nav className="flex items-center gap-4">
              <a
                href="/dashboard"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Dashboard
              </a>
              <span className="text-sm text-white font-medium">Tools</span>
            </nav>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Page Title */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-3">All {TOTAL} Tools</h1>
          <p className="text-xl text-gray-400 max-w-3xl">
            Every tool AccountingQB can use on your QuickBooks — and exactly
            which ones only <span className="text-green-400">read</span> vs.{" "}
            <span className="text-amber-400">write</span>.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
            <span className="text-green-400">● {READS} read-only</span>
            <span className="text-amber-400">● {WRITES} write</span>
            <label className="ml-auto flex items-center gap-2 text-gray-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={readOnlyOnly}
                onChange={(e) => setReadOnlyOnly(e.target.checked)}
                className="accent-cyan-500"
              />
              Show read-only tools only
            </label>
          </div>
        </div>

        {/* What we write to QuickBooks */}
        <section className="mb-12 rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-6">
          <h2 className="text-lg font-semibold mb-2">
            What AccountingQB writes to QuickBooks
          </h2>
          <p className="text-gray-300 text-sm max-w-3xl">
            AccountingQB <strong>reads by default</strong>. It only changes your
            books through the {WRITES} tools marked{" "}
            <span className="text-amber-400">Writes to QuickBooks</span> — and
            never silently: every write is an explicit, confirm-gated action
            surfaced for your approval. Writes cover invoices, bills, expenses,
            deposits, transfers, journal entries, credit memos, vendors &amp;
            customers, accounts, payments, reclassification, and recorded
            depreciation.
          </p>
          <p className="text-gray-400 text-sm mt-3 max-w-3xl">
            Want a hard guarantee? Turn on{" "}
            <a
              href="/dashboard/settings"
              className="text-cyan-400 hover:underline"
            >
              read-only mode
            </a>{" "}
            — our servers then refuse every write tool and hide them entirely.
            Tax jurisdiction (US vs. Canada) is detected automatically from your
            QuickBooks company; wrong-jurisdiction tools are refused.
          </p>
        </section>

        {/* Category Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
          {TOOL_CATEGORIES.map((cat) => (
            <a
              key={cat.category}
              href={`#${anchor(cat.category)}`}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-4 hover:bg-white/[0.05] transition group"
            >
              <div className="text-2xl mb-2">{cat.icon}</div>
              <h3 className="font-medium text-white group-hover:text-cyan-400 transition">
                {cat.category}
              </h3>
              <p className="text-sm text-gray-500">{cat.tools.length} tools</p>
            </a>
          ))}
        </div>

        {/* Tool Categories */}
        <div className="space-y-12">
          {TOOL_CATEGORIES.map((category) => {
            const tools = visible(category.tools);
            if (tools.length === 0) return null;
            return (
              <section
                key={category.category}
                id={anchor(category.category)}
                className="scroll-mt-24"
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-3xl">{category.icon}</span>
                  <div>
                    <h2 className="text-2xl font-bold">{category.category}</h2>
                    <p className="text-gray-400">{category.blurb}</p>
                  </div>
                </div>

                <div className="grid gap-3">
                  {tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="rounded-xl border border-white/10 bg-white/[0.02] p-4 hover:bg-white/[0.04] transition"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <code className="text-cyan-400 font-mono text-sm">
                            {tool.name}
                          </code>
                          <p className="text-gray-400 text-sm mt-1">
                            {tool.description}
                          </p>
                        </div>
                        <Badge write={tool.write} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>

        {/* Usage Examples */}
        <section className="mt-16 rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-500/10 to-blue-500/10 p-8">
          <h2 className="text-2xl font-bold mb-6">How to Use These Tools</h2>
          <p className="text-gray-300 mb-6">
            You don&apos;t need to remember tool names. Just ask Claude
            naturally:
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              "What's my P&L for 2025?",
              "Show me all expenses over $500 from last month",
              "Create an expense for $49.99 to GitHub",
              "Run my Schedule C for tax year 2024",
              "Prepare my GST/HST return for Q2",
              "Run my T2125 summary",
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
