import type { Metadata } from "next";
import { POLICY_LAST_UPDATED } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "AccountingQB privacy policy — how we handle your data.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPolicy() {
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
          <a href="/" className="text-sm text-gray-400 hover:text-gray-100">
            &larr; Back to home
          </a>
        </div>
      </nav>

      <article className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="text-3xl font-bold tracking-tight text-gray-100 sm:text-4xl">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Last updated: {POLICY_LAST_UPDATED}
        </p>

        <div className="prose prose-invert mt-12 max-w-none">
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            1. Overview
          </h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB (&ldquo;we,&rdquo; &ldquo;our,&rdquo; or
            &ldquo;us&rdquo;) is a software product operated by NutriFitAI LLC,
            doing business as Vaspera Capital, a Delaware limited liability
            company. We are committed to protecting your privacy and being
            transparent about how we handle data. This policy explains what
            information we collect, how we use it, and your rights.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            2. Zero-Knowledge Architecture
          </h2>
          <p className="text-gray-400 leading-relaxed">
            When you run AccountingQB locally (via the desktop extension or a
            self-hosted install), it operates with a zero-knowledge
            architecture. The MCP server runs locally on your machine and
            communicates directly with QuickBooks Online using your OAuth
            credentials. Your financial data — transactions, reports, account
            balances, and all QuickBooks content — never passes through our
            servers. We cannot see, access, or store your QuickBooks data.
          </p>
          <h3 className="text-lg font-semibold mt-6 mb-3 text-gray-100">
            Hosted Connector (mcp.accountingqb.com)
          </h3>
          <p className="text-gray-400 leading-relaxed">
            If you connect through our hosted remote connector instead, your
            QuickBooks OAuth tokens are held encrypted server-side so the
            connector can act on your behalf. QuickBooks data transits our
            service per-request and is never stored, logged, or used for
            analytics (&ldquo;zero retention&rdquo;). In both modes, we never
            store your books.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            3. What We Collect
          </h2>
          <p className="text-gray-400 leading-relaxed mb-4">
            We collect only the minimum data necessary to operate the service:
          </p>
          <p className="text-gray-400 leading-relaxed">
            <strong>Account information:</strong> When you start a trial or
            subscribe, we collect your email address and payment information
            (processed by Stripe — we never store card numbers).
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            <strong>License data:</strong> We store a license key, subscription
            tier, and status in our database to validate your subscription.
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            <strong>Usage metadata:</strong> For licensed deployments, we record
            which tools are run — the tool name, your QuickBooks company ID (an
            opaque identifier), an estimated time saved, and a timestamp —
            linked to your license key, to power your dashboard and improve the
            product. This data contains no financial information. If you run
            locally without a license key, no usage metadata is collected. See
            our{" "}
            <a href="/security" className="text-cyan-400 hover:underline">
              Security page
            </a>{" "}
            for details.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            4. What We Do NOT Collect
          </h2>
          <p className="text-gray-400 leading-relaxed">
            We never store your QuickBooks data (transactions, reports,
            balances, vendor or customer information) or any financial data that
            flows between the MCP server and QuickBooks Online. On the local
            tier, that data never even reaches us; on the hosted connector, it
            transits per-request with zero retention. We never use your
            QuickBooks data for analytics.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            5. How We Use Your Information
          </h2>
          <p className="text-gray-400 leading-relaxed">
            We use the information we collect to: provide and maintain the
            service, process payments and manage subscriptions, send
            transactional emails (purchase confirmations, license keys), improve
            the product based on aggregate usage patterns, and comply with legal
            obligations.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            6. Third-Party Services &amp; Sub-processors
          </h2>
          <p className="text-gray-400 leading-relaxed">
            We rely on a small set of vetted service providers
            (&ldquo;sub-processors&rdquo;) to operate AccountingQB. Each
            receives only the data it needs for its function. The current,
            itemized list — each provider, what it processes, and a link to its
            own policy — is maintained on our{" "}
            <a href="/subprocessors" className="text-cyan-400 hover:underline">
              Sub-processors page
            </a>
            . In summary: Stripe (payments), Vercel (hosting), Supabase (our
            database — license and billing metadata and encrypted OAuth tokens),
            Clerk (sign-in/identity), Resend (email delivery), PostHog (product
            analytics, no financial data), and Intuit (the QuickBooks connection
            itself). When you use AccountingQB inside an AI assistant, your
            prompts and the QuickBooks results you ask for are processed by that
            assistant&apos;s AI provider — for Claude that is Anthropic, whose
            commercial API does not train on or retain your data for model
            training. We never sell your personal information (see §10).
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            7. Data Security
          </h2>
          <p className="text-gray-400 leading-relaxed">
            On the local tier, QuickBooks OAuth tokens are encrypted at rest
            using Fernet symmetric encryption and stored locally on your machine
            with restricted file permissions (0600). On the hosted connector
            tier, OAuth tokens are held encrypted at rest on our servers and
            used only to fulfill your requests. License validation uses HTTPS
            for all API calls. We follow industry best practices for securing
            our infrastructure. We do not hold any security certification (such
            as SOC&nbsp;2) today; our{" "}
            <a href="/security" className="text-cyan-400 hover:underline">
              Security page
            </a>{" "}
            describes exactly what we do and don&apos;t do.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            8. International Data Transfers
          </h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB is operated from the United States, and the account,
            license, and billing metadata we hold is stored and processed on US
            infrastructure (Vercel and Supabase). If you are located in Canada,
            the EU/UK, or elsewhere, using the service involves transferring
            that metadata to the United States. For Canadian customers, this
            means your personal information may be stored outside Canada and
            accessible to US authorities under applicable law (PIPEDA
            cross-border disclosure). Your QuickBooks financial data is not
            stored by us in any region — on the local tier it never reaches us,
            and on the hosted connector it transits per-request with zero
            retention.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            9. Data Retention
          </h2>
          <p className="text-gray-400 leading-relaxed">
            We retain data only as long as needed for the purpose it was
            collected:
          </p>
          <ul className="mt-3 list-disc space-y-1.5 pl-6 text-gray-400">
            <li>
              <strong>QuickBooks financial data:</strong> not retained — local
              on your device, or zero-retention pass-through on the hosted
              connector.
            </li>
            <li>
              <strong>Account, license &amp; billing metadata:</strong> for the
              life of your account and up to 90 days after cancellation, then
              deleted or anonymized (longer only where law requires, e.g. tax
              and payment records).
            </li>
            <li>
              <strong>Usage metadata:</strong> raw rows up to ~90 days;
              thereafter only aggregate, non-identifying totals.
            </li>
            <li>
              <strong>Audit &amp; consent records</strong> (event logs,
              acceptance ledger): retained for the integrity of the audit trail;
              corrections are added as new rows rather than edits.
            </li>
            <li>
              <strong>Backups:</strong> rolling, and expire on their own
              schedule after the records above are removed.
            </li>
          </ul>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            10. Your Rights &amp; Choices
          </h2>
          <p className="text-gray-400 leading-relaxed">
            Depending on where you live — including under the EU/UK GDPR,
            California&apos;s CCPA/CPRA, and Canada&apos;s PIPEDA — you have the
            right to access the personal data we hold about you, correct
            inaccurate data, request deletion, receive a portable copy, and
            withdraw consent. <strong>We do not sell or share</strong> your
            personal information, and we do not use it for cross-context
            behavioral advertising. To exercise any of these rights, use our{" "}
            <a
              href="/privacy/request"
              className="text-cyan-400 hover:underline"
            >
              privacy request form
            </a>{" "}
            or email{" "}
            <a
              href="mailto:privacy@vasperacapital.com"
              className="text-cyan-400 hover:underline"
            >
              privacy@vasperacapital.com
            </a>
            ; we respond within 30 days and never discriminate against you for
            exercising a right. You can unsubscribe from marketing email at any
            time via the link in any such message.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            11. Children&apos;s Privacy
          </h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB is not intended for use by individuals under the age of
            18. We do not knowingly collect information from children.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            12. Changes to This Policy
          </h2>
          <p className="text-gray-400 leading-relaxed">
            We may update this privacy policy from time to time. We will notify
            you of material changes by email or by posting a notice on our
            website.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            13. Contact Us
          </h2>
          <p className="text-gray-400 leading-relaxed">
            If you have questions about this privacy policy or our data
            practices, contact us at{" "}
            <a
              href="mailto:support@vasperacapital.com"
              className="text-cyan-400 hover:underline"
            >
              support@vasperacapital.com
            </a>
            .
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            NutriFitAI LLC, d/b/a Vaspera Capital
            <br />
            12 Autumn Hill Ln
            <br />
            Southborough, MA 01772
          </p>
        </div>
      </article>
    </main>
  );
}
