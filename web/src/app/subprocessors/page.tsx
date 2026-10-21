import type { Metadata } from "next";
import { POLICY_LAST_UPDATED } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Sub-processors",
  description:
    "The third-party service providers AccountingQB uses to operate the service, and what each one processes.",
  alternates: { canonical: "/subprocessors" },
};

type Row = {
  name: string;
  purpose: string;
  data: string;
  region: string;
  url: string;
};

// Keep this list current — it is referenced by the Privacy Policy. QuickBooks
// financial data is NOT stored by AccountingQB in any region (local on the
// device, or zero-retention pass-through on the hosted connector), so no
// sub-processor below holds your books at rest.
const SUBPROCESSORS: Row[] = [
  {
    name: "Stripe",
    purpose: "Payments & subscription billing",
    data: "Name, email, billing details, card tokens (we never see card numbers)",
    region: "USA",
    url: "https://stripe.com/privacy",
  },
  {
    name: "Vercel",
    purpose: "Website & API hosting",
    data: "Request metadata, IP (transient), logs",
    region: "USA",
    url: "https://vercel.com/legal/privacy-policy",
  },
  {
    name: "Supabase",
    purpose: "Application database",
    data: "License & billing metadata, usage metadata, encrypted OAuth tokens",
    region: "USA",
    url: "https://supabase.com/privacy",
  },
  {
    name: "Clerk",
    purpose: "Authentication & identity",
    data: "Email, name, authentication identifiers",
    region: "USA",
    url: "https://clerk.com/legal/privacy",
  },
  {
    name: "Resend",
    purpose: "Transactional & marketing email delivery",
    data: "Email address, message content",
    region: "USA",
    url: "https://resend.com/legal/privacy-policy",
  },
  {
    name: "PostHog",
    purpose: "Product analytics (no financial data)",
    data: "Usage events, anonymized/opaque identifiers",
    region: "USA",
    url: "https://posthog.com/privacy",
  },
  {
    name: "Intuit (QuickBooks Online)",
    purpose: "The accounting platform you connect",
    data: "OAuth authorization; your QuickBooks data flows between you and Intuit",
    region: "USA",
    url: "https://www.intuit.com/privacy/statement/",
  },
  {
    name: "Anthropic (Claude)",
    purpose:
      "AI assistant that runs AccountingQB's tools (when you use Claude)",
    data: "Your prompts and the QuickBooks results you request, in-session",
    region: "USA",
    url: "https://www.anthropic.com/legal/privacy",
  },
];

export default function Subprocessors() {
  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <nav className="border-b border-white/[0.06] bg-[#0a0e1a]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <a href="/" className="text-lg font-bold text-gray-100">
            Accounting
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              QB
            </span>
          </a>
          <a
            href="/privacy"
            className="text-sm text-gray-400 hover:text-gray-100"
          >
            &larr; Privacy Policy
          </a>
        </div>
      </nav>

      <article className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="text-3xl font-bold tracking-tight text-gray-100 sm:text-4xl">
          Sub-processors
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Last updated: {POLICY_LAST_UPDATED}
        </p>
        <p className="mt-6 max-w-none text-gray-400 leading-relaxed">
          AccountingQB uses the vetted service providers below to operate the
          service. Each receives only the data it needs for its function. We do
          not store your QuickBooks financial data in any region — on the local
          tier it never reaches us, and on the hosted connector it transits
          per-request with zero retention — so none of these providers hold your
          books at rest. We will update this page before adding a new
          sub-processor that handles personal data.
        </p>

        <div className="mt-10 overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.03] text-gray-300">
                <th className="px-4 py-3 font-semibold">Provider</th>
                <th className="px-4 py-3 font-semibold">Purpose</th>
                <th className="px-4 py-3 font-semibold">Data processed</th>
                <th className="px-4 py-3 font-semibold">Region</th>
              </tr>
            </thead>
            <tbody>
              {SUBPROCESSORS.map((p) => (
                <tr
                  key={p.name}
                  className="border-b border-white/5 align-top text-gray-400"
                >
                  <td className="px-4 py-3">
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400 hover:underline"
                    >
                      {p.name}
                    </a>
                  </td>
                  <td className="px-4 py-3">{p.purpose}</td>
                  <td className="px-4 py-3">{p.data}</td>
                  <td className="px-4 py-3">{p.region}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          Questions about our sub-processors or a data processing agreement?
          Email{" "}
          <a
            href="mailto:privacy@vasperacapital.com"
            className="text-cyan-400 hover:underline"
          >
            privacy@vasperacapital.com
          </a>
          .
        </p>
      </article>
    </main>
  );
}
