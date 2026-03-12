import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "AccountingQB terms of service — the rules governing use of our product.",
};

export default function TermsOfService() {
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
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          Last updated: March 12, 2026
        </p>

        <div className="prose prose-invert mt-12 max-w-none">
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">1. Agreement to Terms</h2>
          <p className="text-gray-400 leading-relaxed">
            By accessing or using AccountingQB (&ldquo;the Service&rdquo;), operated by NutriFitAI LLC
            (&ldquo;we,&rdquo; &ldquo;our,&rdquo; or &ldquo;us&rdquo;), you agree to be bound by these
            Terms of Service. If you do not agree to these terms, do not use the Service.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">2. Description of Service</h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB is a software tool that provides AI-powered tools for interacting with
            QuickBooks Online through the Model Context Protocol (MCP). The Service includes a
            locally-installed MCP server, a cloud-hosted license validation system, and a website
            for account management and documentation.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">3. Eligibility</h2>
          <p className="text-gray-400 leading-relaxed">
            You must be at least 18 years of age and capable of forming a binding contract to use
            the Service. By using the Service, you represent and warrant that you meet these
            requirements.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">4. Account Registration</h2>
          <p className="text-gray-400 leading-relaxed">
            To use the paid features of the Service, you must register for an account by providing
            a valid email address and subscribing to a plan. You are responsible for maintaining the
            confidentiality of your license key and for all activities that occur under your account.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">5. Free Trial</h2>
          <p className="text-gray-400 leading-relaxed">
            We offer a 14-day free trial with full access to all features. No credit card is required
            to start the trial. After the trial period, the Service will automatically degrade to a
            limited read-only mode unless you subscribe to a paid plan. We reserve the right to modify
            or discontinue the free trial at any time.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">6. Subscription and Payment</h2>
          <p className="text-gray-400 leading-relaxed">
            Paid subscriptions are billed monthly through Stripe. By subscribing, you authorize us to
            charge the payment method on file on a recurring basis. All fees are stated in U.S.
            dollars and are non-refundable except as required by law. We reserve the right to change
            pricing with 30 days&apos; notice. You may cancel your subscription at any time through
            the Stripe customer portal, and your access will continue until the end of the current
            billing period.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">7. License and Restrictions</h2>
          <p className="text-gray-400 leading-relaxed">
            Subject to these Terms, we grant you a limited, non-exclusive, non-transferable,
            revocable license to use the Service for your internal business purposes. You may not:
            reverse engineer, decompile, or disassemble the Service; redistribute, sublicense, or
            resell the Service; use the Service to build a competing product; share your license key
            with third parties; or attempt to circumvent the license validation system.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">8. Your Data and Privacy</h2>
          <p className="text-gray-400 leading-relaxed">
            AccountingQB uses a zero-knowledge architecture. Your QuickBooks data is processed
            locally on your machine and never transmitted to our servers. You retain full ownership
            of your data. Our handling of information is described in our{" "}
            <a href="/privacy" className="text-cyan-400 hover:underline">
              Privacy Policy
            </a>
            , which is incorporated into these Terms by reference.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">9. QuickBooks Integration</h2>
          <p className="text-gray-400 leading-relaxed">
            The Service integrates with QuickBooks Online via the Intuit Developer API. You are
            responsible for maintaining a valid QuickBooks Online subscription and for complying
            with Intuit&apos;s terms of service. AccountingQB is not affiliated with, endorsed by,
            or sponsored by Intuit Inc. QuickBooks is a registered trademark of Intuit Inc.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">10. Disclaimer of Warranties</h2>
          <p className="text-gray-400 leading-relaxed">
            THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; WITHOUT
            WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED
            WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
            WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE. THE
            SERVICE IS NOT A SUBSTITUTE FOR PROFESSIONAL ACCOUNTING, TAX, OR FINANCIAL ADVICE.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">11. Limitation of Liability</h2>
          <p className="text-gray-400 leading-relaxed">
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, NUTRIFITAI LLC AND ITS OFFICERS, DIRECTORS,
            EMPLOYEES, AND AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL,
            CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS OR REVENUES, WHETHER
            INCURRED DIRECTLY OR INDIRECTLY, OR ANY LOSS OF DATA, USE, GOODWILL, OR OTHER
            INTANGIBLE LOSSES, RESULTING FROM: (A) YOUR USE OF OR INABILITY TO USE THE SERVICE;
            (B) ANY ERRORS, INACCURACIES, OR OMISSIONS IN THE SERVICE&apos;S OUTPUT; (C)
            UNAUTHORIZED ACCESS TO YOUR DATA; OR (D) ANY THIRD-PARTY CONDUCT ON THE SERVICE.
            OUR TOTAL LIABILITY SHALL NOT EXCEED THE AMOUNT YOU PAID US IN THE TWELVE (12) MONTHS
            PRECEDING THE CLAIM.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">12. Indemnification</h2>
          <p className="text-gray-400 leading-relaxed">
            You agree to indemnify and hold harmless NutriFitAI LLC from any claims, damages,
            losses, liabilities, and expenses (including reasonable attorney&apos;s fees) arising out
            of or related to your use of the Service, your violation of these Terms, or your
            violation of any rights of another party.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">13. Termination</h2>
          <p className="text-gray-400 leading-relaxed">
            We may suspend or terminate your access to the Service at any time, with or without
            cause, and with or without notice. Upon termination, your license to use the Service
            will immediately cease. Sections 10 through 15 shall survive any termination of these
            Terms.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">14. Governing Law</h2>
          <p className="text-gray-400 leading-relaxed">
            These Terms shall be governed by and construed in accordance with the laws of the
            Commonwealth of Massachusetts, without regard to its conflict of law provisions. Any
            legal action or proceeding arising under these Terms shall be brought exclusively in
            the courts located in Worcester County, Massachusetts.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">15. Changes to Terms</h2>
          <p className="text-gray-400 leading-relaxed">
            We may update these Terms from time to time. We will notify you of material changes
            by email or by posting a notice on our website. Your continued use of the Service
            after changes become effective constitutes acceptance of the revised Terms.
          </p>

          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">16. Contact Us</h2>
          <p className="text-gray-400 leading-relaxed">
            If you have questions about these Terms, contact us at{" "}
            <a href="mailto:support@accountingqb.com" className="text-cyan-400 hover:underline">
              support@accountingqb.com
            </a>
            .
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            NutriFitAI LLC<br />
            12 Autumn Hill Ln<br />
            Southborough, MA 01772
          </p>
        </div>
      </article>
    </main>
  );
}
