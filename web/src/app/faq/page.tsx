import type { Metadata } from "next";
import Link from "next/link";

const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";

export const metadata: Metadata = {
  title: "FAQ — AccountingQB",
  description:
    "Answers about AccountingQB: what it is, how it connects Claude to QuickBooks Online, data safety, US & Canadian tax support, pricing, and supported Claude apps.",
  alternates: { canonical: `${siteUrl}/faq` },
};

const faqs: { q: string; a: string }[] = [
  {
    q: "What is AccountingQB?",
    a: "AccountingQB is an AI-powered QuickBooks Online integration for Claude. It gives Claude 129 tools to run financial reports, clean up bookkeeping, reconcile accounts, and prepare US and Canadian taxes through natural conversation. It connects to QuickBooks Online over the Model Context Protocol (MCP) — as a desktop extension or a hosted connector.",
  },
  {
    q: "How does AccountingQB work?",
    a: "You connect your QuickBooks Online company to Claude once. Then you ask Claude in plain English — \"What's my P&L for Q2?\", \"Find uncategorized transactions\", \"Run my Schedule C\" — and it uses AccountingQB's tools to read and update your books. It runs locally as a desktop extension, or through a zero-retention hosted connector you add to Claude as a custom connector.",
  },
  {
    q: "Is my financial data safe?",
    a: "Yes. Run AccountingQB locally and your financial data flows directly between your computer and QuickBooks, never touching our servers. Or use the hosted connector, where data passes through with zero retention — it is never stored, logged, or used for analytics. Either way, we never store your books.",
  },
  {
    q: "What can AccountingQB do?",
    a: "129 tools spanning financial reports (P&L, balance sheet, cash flow, general ledger, AR/AP aging, sales by customer/product/class), bookkeeping cleanup (uncategorized transactions, duplicates, anomaly detection, a structural books-hygiene audit), reconciliation, sales-tax economic-nexus screening, and full US and Canadian tax preparation.",
  },
  {
    q: "Does AccountingQB support Canadian businesses?",
    a: "Yes. It auto-detects the company's tax edition and ships a full Canadian suite: GST/HST (GST34) return workpapers, T2125 business statements, CCA depreciation schedules, T4A/T5018 contractor reporting, and CRA instalment + CPP estimates — with province-aware sales-tax handling and CAD pricing.",
  },
  {
    q: "How much does AccountingQB cost?",
    a: "Three plans: Solopreneur at $39/month, Business at $99/month, and Firm at $299/month (with CAD pricing for Canadian customers), each with a 14-day free trial. After the trial you keep 25 essential read-only tools for free; paid plans unlock all 129 tools including writes, tax prep, and advanced analytics.",
  },
  {
    q: "Which Claude apps does AccountingQB work with?",
    a: "AccountingQB works with Claude on the web, desktop, and mobile via the remote connector (add it as a custom connector — no install needed), with Claude Desktop via the MCP extension, and with Cowork via the plugin. Any app that supports MCP servers can use it.",
  },
  {
    q: "Does AccountingQB work with QuickBooks Desktop?",
    a: "AccountingQB currently supports QuickBooks Online only. QuickBooks Desktop support is on the roadmap.",
  },
  {
    q: "How do you keep the tax numbers current?",
    a: "Every tax rate and threshold we use — IRS brackets, mileage rates, §179 and bonus depreciation limits, GST/HST rates, CPP ceilings — lives in a versioned registry where each value carries its official source and a verification date. Changes ship through a tamper-evident audit ledger reviewed by a human, and a research agent checks the sources monthly.",
  },
  {
    q: "How is AccountingQB different from other QuickBooks integrations?",
    a: "It is the most comprehensive QuickBooks MCP server for Claude — 129 tools versus a handful in typical integrations — it uniquely covers both US and Canadian tax prep with sourced, dated tax data, and its connector is current with the 2026-07-28 MCP specification: stateless, load-balancer-ready, and using none of the deprecated protocol features.",
  },
];

export default function FaqPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <main className="min-h-screen bg-[#0a0e1a] px-6 py-16 text-gray-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← AccountingQB
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-white">
          Frequently asked questions
        </h1>
        <p className="mt-2 text-gray-400">
          What AccountingQB is, how it connects Claude to QuickBooks Online, and how
          it handles your data and taxes.
        </p>

        <div className="mt-10 space-y-8">
          {faqs.map((f) => (
            <div key={f.q} className="border-b border-white/10 pb-6">
              <h2 className="text-lg font-semibold text-white">{f.q}</h2>
              <p className="mt-2 leading-relaxed text-gray-300">{f.a}</p>
            </div>
          ))}
        </div>

        <div className="mt-12 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.06] p-6">
          <p className="text-gray-200">
            Ready to try it?{" "}
            <Link href="/#pricing" className="font-semibold text-cyan-300 hover:text-cyan-200">
              Start a 14-day free trial →
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
