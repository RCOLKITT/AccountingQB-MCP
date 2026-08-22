import type { Metadata } from "next";
import LandingNav from "@/components/nav/LandingNav";
import Footer from "@/components/Footer";
import DemoChat from "./DemoChat";

export const metadata: Metadata = {
  title: "Live Demo",
  description:
    "Try AccountingQB on a sample company — ask its books anything and see real answers (P&L, deductions, Schedule C, anomalies) with no sign-up and no QuickBooks connection.",
  alternates: { canonical: "/demo" },
};

export default function DemoPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <LandingNav />

      {/* HERO */}
      <section className="mx-auto max-w-3xl px-6 pt-32 pb-8 text-center sm:pt-36">
        <p className="text-[13px] uppercase tracking-[0.18em] text-cyan-300">Live demo</p>
        <h1 className="mx-auto mt-4 max-w-2xl text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl">
          See it work before you{" "}
          <span className="font-serif font-medium italic text-cyan-300">set anything up.</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-[16px] leading-relaxed text-gray-400">
          This is a real, interactive session on a sample company&rsquo;s books — no sign-up, no
          QuickBooks connection. Ask a question or tap a suggestion.
        </p>
      </section>

      {/* DEMO CHAT */}
      <section className="mx-auto max-w-3xl px-6">
        <DemoChat />
        <p className="mt-3 text-center text-xs text-gray-600">
          Illustrative sample data. Your real books stay on your machine — we never store them.
        </p>
      </section>

      {/* CTA */}
      <section className="mx-auto my-16 max-w-3xl px-6">
        <div className="rounded-2xl border border-white/[0.06] bg-[radial-gradient(80%_120%_at_50%_0%,rgba(34,211,238,0.08),transparent)] px-6 py-12 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Now run it on your own books.</h2>
          <p className="mx-auto mt-3 max-w-md text-[15px] text-gray-400">
            14-day free trial. No credit card required. Connect QuickBooks in a couple of minutes.
          </p>
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="/pricing"
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-[14px] font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:brightness-110"
            >
              Start free trial
            </a>
            <a
              href="/#demo"
              className="rounded-xl border border-white/10 bg-white/[0.03] px-6 py-3 text-[14px] font-semibold text-gray-200 transition hover:bg-white/[0.06]"
            >
              How setup works
            </a>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
