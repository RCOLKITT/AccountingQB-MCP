import type { Metadata } from "next";
import Image from "next/image";
import LandingNav from "@/components/nav/LandingNav";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "About",
  description:
    "AccountingQB was built by its founder to solve his own bookkeeping struggle — which is why your books stay local or transit with zero retention. The story behind the product.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <LandingNav />

      <div className="mx-auto max-w-3xl px-6">
        {/* HERO */}
        <section className="pt-32 pb-10 text-center sm:pt-36">
          <p className="text-[13px] uppercase tracking-[0.18em] text-cyan-300">
            Our story
          </p>
          <h1 className="mt-4 text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl">
            I built AccountingQB because{" "}
            <span className="font-serif font-medium italic text-cyan-300">
              I needed it first.
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-[16px] leading-relaxed text-gray-400">
            It didn&rsquo;t start as a product. It started as me, late at night,
            trying to make sense of my own books.
          </p>
        </section>

        {/* FOUNDER intro */}
        <section className="flex flex-col items-center gap-6 py-8 sm:flex-row sm:gap-8">
          <div className="relative h-28 w-28 flex-shrink-0 overflow-hidden rounded-2xl ring-1 ring-white/10">
            <Image
              src="/founder.png"
              alt="Ryan Colkitt, Founder of AccountingQB"
              fill
              sizes="112px"
              className="object-cover object-top"
              priority
            />
          </div>
          <div className="text-center sm:text-left">
            <div className="text-lg font-semibold text-white">Ryan Colkitt</div>
            <div className="text-[14px] text-gray-400">
              Founder, AccountingQB &middot; Boston, USA
            </div>
            <div className="mt-2 flex justify-center gap-3 text-[13px] sm:justify-start">
              <a
                href="https://www.linkedin.com/in/ryancolkitt/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-300 transition hover:text-cyan-200"
              >
                LinkedIn
              </a>
              <span className="text-gray-600">&middot;</span>
              <a
                href="https://vasperacapital.com"
                className="text-cyan-300 transition hover:text-cyan-200"
              >
                A Vaspera Capital company
              </a>
            </div>
          </div>
        </section>

        {/* THE STORY */}
        <section className="space-y-5 py-8 text-[16px] leading-[1.75] text-gray-300">
          <p className="text-[13px] font-semibold uppercase tracking-wide text-cyan-300">
            The struggle
          </p>
          <p>
            I run my own business. And for a long time, the part I dreaded most
            wasn&rsquo;t the work &mdash; it was the books. Reconciliations I
            put off. A stack of transactions I couldn&rsquo;t reconcile against
            the bank. Tax season that always seemed to arrive before I was
            ready, with questions I couldn&rsquo;t answer:{" "}
            <em>
              what&rsquo;s actually deductible here? Am I setting aside enough?
              Where did the money go this quarter?
            </em>
          </p>
          <p>
            I&rsquo;m not an accountant. I had QuickBooks, and I had the data
            &mdash; I just couldn&rsquo;t get straight answers out of it without
            hours of clicking, exporting, and second-guessing myself.
          </p>

          <p className="pt-4 text-[13px] font-semibold uppercase tracking-wide text-cyan-300">
            The turning point
          </p>
          <p>
            Then I started asking an AI assistant my accounting questions
            &mdash; and realized the only thing missing was a safe, accurate
            bridge to my actual QuickBooks data. Not another dashboard. Not
            another export. A way to just <em>ask</em> &mdash;
            &ldquo;what&rsquo;s my burn rate,&rdquo; &ldquo;find the deductions
            I&rsquo;m missing,&rdquo; &ldquo;get me ready for taxes&rdquo;
            &mdash; and get an answer I could trust, with the numbers cited.
          </p>
          <p>
            So I built it. First for myself. It turned a weekend of bookkeeping
            into a conversation, and it caught things I&rsquo;d have missed.
            Then I realized every other owner and bookkeeper I knew had the same
            problem &mdash; and AccountingQB became a product.
          </p>
        </section>

        {/* PRIVACY PULL-QUOTE */}
        <section className="py-10">
          <blockquote className="rounded-2xl border border-white/10 bg-[#131a2e] p-8 text-center">
            <p className="font-serif text-[22px] italic leading-snug text-white sm:text-[26px]">
              &ldquo;These are my books too. I was never going to hand my own
              financials to a black box &mdash; so I didn&rsquo;t build
              one.&rdquo;
            </p>
            <p className="mt-5 text-[14px] leading-relaxed text-gray-400">
              That&rsquo;s why AccountingQB runs on your machine by default, and
              why the hosted option keeps{" "}
              <span className="text-gray-200">zero retention</span> &mdash; your
              books transit, they&rsquo;re never stored. The less we hold, the
              less there is to lose. It&rsquo;s not a compliance checkbox;
              it&rsquo;s the whole design, because it&rsquo;s how I wanted{" "}
              <em>my</em> data handled.
            </p>
          </blockquote>
        </section>

        {/* WHAT I CARE ABOUT */}
        <section className="py-8">
          <h2 className="text-2xl font-bold tracking-tight text-white">
            What I care about building
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[
              {
                title: "Numbers you can defend",
                body: "Every tax figure sourced, dated, and audit-logged. If I’m going to file on it, it has to be right.",
              },
              {
                title: "Your data stays yours",
                body: "Local-first, zero-retention. The privacy I wanted for my own books, built in for everyone’s.",
              },
              {
                title: "Built by someone who uses it",
                body: "I run my own business on AccountingQB. If it doesn’t work for me, it doesn’t ship.",
              },
            ].map((c) => (
              <div
                key={c.title}
                className="rounded-xl border border-white/10 bg-[#131a2e] p-5"
              >
                <div className="mb-3 h-8 w-8 rounded-lg bg-cyan-500/[0.12] ring-1 ring-cyan-500/20" />
                <h3 className="text-[15px] font-semibold text-white">
                  {c.title}
                </h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-gray-400">
                  {c.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* SIGNATURE */}
        <section className="py-8">
          <p className="text-[16px] leading-relaxed text-gray-300">
            If you&rsquo;ve ever stared at your books wishing you could just{" "}
            <em>ask</em> them a question &mdash; that&rsquo;s exactly who I
            built this for. I&rsquo;d genuinely love to hear what you think.
          </p>
          <div className="mt-6">
            <div className="font-serif text-2xl italic text-white">
              Ryan Colkitt
            </div>
            <div className="text-[14px] text-gray-500">
              Founder, AccountingQB
            </div>
            <a
              href="mailto:contact@vasperacapital.com"
              className="mt-1 inline-block text-[14px] text-cyan-300 transition hover:text-cyan-200"
            >
              reach me directly &rarr;
            </a>
          </div>
        </section>

        {/* CTA */}
        <section className="my-8 rounded-2xl border border-white/[0.06] bg-[radial-gradient(80%_120%_at_50%_0%,rgba(34,211,238,0.08),transparent)] px-6 py-12 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Try it on your own books.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-[15px] text-gray-400">
            14-day trial. Run it locally in five minutes &mdash; the same way I
            do.
          </p>
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="/#pricing"
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-[14px] font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:brightness-110"
            >
              Start free trial
            </a>
            <a
              href="/#demo"
              className="rounded-xl border border-white/10 bg-white/[0.03] px-6 py-3 text-[14px] font-semibold text-gray-200 transition hover:bg-white/[0.06]"
            >
              See how it works
            </a>
          </div>
        </section>
      </div>

      <Footer />
    </main>
  );
}
