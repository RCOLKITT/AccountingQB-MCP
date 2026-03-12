import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "AccountingQB privacy policy — how we handle your data.",
};

export default function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-[#0a0e1a]">
      <nav className="border-b border-white/[0.06] bg-[#0a0e1a]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <a href="/" className="text-lg font-bold text-gray-100">
            Accounting<span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">QB</span>
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
          Last updated: March 12, 2026
        </p>

        <div className="prose prose-invert mt-12 max-w-none">
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">1. Overview</h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB (&ldquo;we,&rdquo; &ldquo;our,&rdquo; or &ldquo;us&rdquo;) is a software product
            operated by NutriFitAI LLC, doing business as Vaspera Capital, a Delaware limited liability company. We are committed to protecting
            your privacy and being transparent about how we handle data. This policy explains what
            information we collect, how we use it, and your rights.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">2. Zero-Knowledge Architecture</h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB is built with a zero-knowledge architecture. The MCP server runs locally on your
            machine and communicates directly with QuickBooks Online using your OAuth credentials. Your
            financial data — transactions, reports, account balances, and all QuickBooks content — never
            passes through our servers. We cannot see, access, or store your QuickBooks data.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">3. What We Collect</h2>
          <p className="text-gray-400 leading-relaxed mb-4">
            We collect only the minimum data necessary to operate the service:
          </p>
          <p className="text-gray-400 leading-relaxed">
            <strong>Account information:</strong> When you start a trial or subscribe, we collect your email
            address and payment information (processed by Stripe — we never store card numbers).
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            <strong>License data:</strong> We store a license key, subscription tier, and status in our
            database to validate your subscription.
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            <strong>Usage metadata:</strong> We may collect anonymous, aggregate usage statistics such as
            which tools are used most frequently. This data contains no financial information.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">4. What We Do NOT Collect</h2>
          <p className="text-gray-400 leading-relaxed">
            We do not collect, store, transmit, or have access to: your QuickBooks data (transactions,
            reports, balances, vendor or customer information), your QuickBooks OAuth tokens (stored locally
            on your machine with Fernet encryption), or any financial data that flows between the MCP server
            and QuickBooks Online.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">5. How We Use Your Information</h2>
          <p className="text-gray-400 leading-relaxed">
            We use the information we collect to: provide and maintain the service, process payments and
            manage subscriptions, send transactional emails (purchase confirmations, license keys), improve
            the product based on aggregate usage patterns, and comply with legal obligations.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">6. Third-Party Services</h2>
          <p className="text-gray-400 leading-relaxed">
            We use the following third-party services: Stripe for payment processing (see Stripe&apos;s privacy
            policy at stripe.com/privacy), Vercel for hosting our website and API endpoints, and Supabase for
            license database hosting. None of these services have access to your QuickBooks data.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">7. Data Security</h2>
          <p className="text-gray-400 leading-relaxed">
            QuickBooks OAuth tokens are encrypted at rest using Fernet symmetric encryption and stored locally
            on your machine with restricted file permissions (0600). License validation uses HTTPS for all
            API calls. We follow industry best practices for securing our infrastructure.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">8. Data Retention</h2>
          <p className="text-gray-400 leading-relaxed">
            Account and license data is retained for the duration of your subscription plus 90 days after
            cancellation. You may request deletion of your data at any time by contacting us.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">9. Your Rights</h2>
          <p className="text-gray-400 leading-relaxed">
            You have the right to: access the personal data we hold about you, request correction of
            inaccurate data, request deletion of your data, export your data in a portable format, and
            withdraw consent at any time by canceling your subscription.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">10. Children&apos;s Privacy</h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB is not intended for use by individuals under the age of 18. We do not knowingly
            collect information from children.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">11. Changes to This Policy</h2>
          <p className="text-gray-400 leading-relaxed">
            We may update this privacy policy from time to time. We will notify you of material changes by
            email or by posting a notice on our website.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">12. Contact Us</h2>
          <p className="text-gray-400 leading-relaxed">
            If you have questions about this privacy policy or our data practices, contact us at{" "}
            <a href="mailto:support@accountingqb.com" className="text-cyan-400 hover:underline">
              support@accountingqb.com
            </a>
            .
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            NutriFitAI LLC, d/b/a Vaspera Capital<br />
            12 Autumn Hill Ln<br />
            Southborough, MA 01772
          </p>
        </div>
      </article>
    </main>
  );
}
