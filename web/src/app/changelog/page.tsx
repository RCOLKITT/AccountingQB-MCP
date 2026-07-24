import type { Metadata } from "next";
import { RELEASES } from "@/lib/changelog";

export const metadata: Metadata = {
  title: "What's New — Release Notes",
  description:
    "New features and improvements in AccountingQB — the AI-powered QuickBooks assistant for Claude. CPA workbook, Canada tax support, sourced tax data, and more.",
  alternates: { canonical: "/changelog" },
};

const tagColor: Record<string, string> = {
  Feature: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  Tax: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  Canada: "bg-red-500/10 text-red-300 border-red-500/30",
  Platform: "bg-blue-500/10 text-blue-300 border-blue-500/30",
};

function fmt(d: string): string {
  return new Date(d).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function ChangelogPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a] text-gray-100">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a
          href="/"
          className="text-sm text-gray-500 hover:text-white transition"
        >
          ← AccountingQB
        </a>
        <h1 className="mt-6 text-4xl font-bold tracking-tight">What&rsquo;s New</h1>
        <p className="mt-3 text-lg text-gray-400">
          New features and improvements in AccountingQB. Have an idea?{" "}
          <a
            href="mailto:support@vasperacapital.com"
            className="text-cyan-400 hover:underline"
          >
            Tell us
          </a>
          .
        </p>

        <div className="mt-14 space-y-14">
          {RELEASES.map((r) => (
            <article key={r.version} className="relative border-l border-white/10 pl-8">
              <div className="absolute -left-[7px] top-1.5 h-3 w-3 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500" />
              <div className="flex flex-wrap items-center gap-3">
                {r.tag && (
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      tagColor[r.tag] || tagColor.Feature
                    }`}
                  >
                    {r.tag}
                  </span>
                )}
                <time className="text-xs text-gray-500">{fmt(r.date)}</time>
                <span className="text-xs text-gray-600">
                  {r.version.match(/^\d/) ? `v${r.version}` : r.version}
                </span>
              </div>
              <h2 className="mt-3 text-2xl font-semibold text-white">{r.title}</h2>
              <p className="mt-2 text-gray-400 leading-relaxed">{r.summary}</p>
              <ul className="mt-4 space-y-2">
                {r.highlights.map((h, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-300">
                    <span className="mt-1 text-cyan-400">→</span>
                    <span className="leading-relaxed">{h}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <div className="mt-16 rounded-2xl border border-cyan-500/20 bg-[#131a2e] p-8 text-center">
          <p className="text-lg font-semibold text-white">Ready to try it?</p>
          <p className="mt-1 text-gray-400">
            14-day free trial, no card required.
          </p>
          <a
            href="/#pricing"
            className="mt-4 inline-block rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-2.5 font-medium text-white transition hover:opacity-90"
          >
            Get started
          </a>
        </div>
      </div>
    </main>
  );
}
