import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Security",
  description:
    "How AccountingQB secures your data — zero-knowledge local mode, zero-retention hosted connector, AES-256-GCM token encryption, and exactly what metadata we collect.",
  alternates: { canonical: "/security" },
};

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#131a2e] p-6">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <div className="mt-3 text-gray-400 leading-relaxed text-[15px]">{children}</div>
    </div>
  );
}

export default function SecurityPage() {
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
        <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/20 bg-cyan-500/[0.08] px-3 py-1 text-xs font-medium text-cyan-300">
          Security & data handling
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-100 sm:text-4xl">
          Security at AccountingQB
        </h1>
        <p className="mt-2 text-sm text-gray-500">Last updated: July 2026</p>
        <p className="mt-6 max-w-2xl text-lg text-gray-400 leading-relaxed">
          AccountingQB connects Claude to your QuickBooks. Your books are the most
          sensitive thing we could touch — so we designed the product so that, in
          normal use, <strong className="text-gray-200">we don&rsquo;t</strong>.
          Everything below is how the product actually works; you can verify it in
          our{" "}
          <a
            href="https://github.com/RCOLKITT/AccountingQB-MCP"
            className="text-cyan-400 hover:underline"
          >
            source code
          </a>
          .
        </p>

        {/* Two deployment models */}
        <h2 className="mt-14 text-xl font-semibold text-gray-100">
          Two ways to run — both private
        </h2>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <Card title="Local — zero-knowledge">
            The MCP server runs entirely on your own machine (the downloadable
            desktop app, the Claude Desktop extension, or{" "}
            <code className="text-gray-300">uvx accountingqb</code>) and talks
            directly to QuickBooks Online using your own OAuth token.
            Your financial data flows between your computer and QuickBooks and{" "}
            <strong className="text-gray-200">never passes through our servers</strong>
            . Your QuickBooks refresh token is encrypted at rest on your machine
            with Fernet symmetric encryption and stored with owner-only file
            permissions (<code className="text-gray-300">0600</code>).
          </Card>
          <Card title="Hosted connector — zero-retention">
            Prefer no install? The hosted connector at{" "}
            <code className="text-gray-300">mcp.accountingqb.com</code> is{" "}
            <strong className="text-gray-200">stateless</strong>: every request is
            independent, and your tokens live only in a per-request context that is
            never written to disk. Your QuickBooks data transits per-request and is{" "}
            <strong className="text-gray-200">
              never stored, logged, or used for analytics
            </strong>
            .
          </Card>
        </div>

        <div className="prose prose-invert mt-14 max-w-none">
          {/* Your QuickBooks data */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            Your QuickBooks data is never stored
          </h2>
          <p className="text-gray-400 leading-relaxed">
            In both modes, we never store your books. We do not keep, log, or
            analyze your transactions, amounts, account balances, invoices, or your
            customer and vendor information. On the local tier that data never even
            reaches us; on the hosted connector it transits per-request with zero
            retention. The only thing the hosted service holds on your behalf is
            your QuickBooks OAuth token — encrypted at rest (see below) — so it can
            act for you when you ask it to.
          </p>

          {/* Tokens & encryption */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            OAuth tokens &amp; encryption
          </h2>
          <p className="text-gray-400 leading-relaxed">
            On the <strong className="text-gray-200">hosted connector</strong>, your
            QuickBooks access and refresh tokens are encrypted at rest with{" "}
            <strong className="text-gray-200">AES-256-GCM</strong> authenticated
            encryption — a unique random initialization vector per value and an
            authentication tag verified on every decrypt. The encryption key is a
            managed secret held outside the database; tokens are encrypted on write
            and decrypted only in memory to fulfill your request. On the{" "}
            <strong className="text-gray-200">local tier</strong>, the refresh token
            is encrypted with Fernet and restricted to owner-only file permissions.
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            Connecting uses OAuth 2.1. Refresh tokens{" "}
            <strong className="text-gray-200">rotate on every use</strong>, and if a
            revoked refresh token is ever replayed, the entire token lineage is
            invalidated — automatic detection of token theft.
          </p>

          {/* Authentication */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            Authentication &amp; access control
          </h2>
          <p className="text-gray-400 leading-relaxed">
            Every hosted-connector request must carry a short-lived,
            audience-bound bearer token (signed JWT); requests without a valid token
            are rejected, and the service fails closed if its signing secret is
            absent. The connector also validates the request host against an
            explicit allow-list (protection against DNS-rebinding). Redirect URIs in
            the OAuth flow must be HTTPS. Our web app and dashboard are
            authenticated with Clerk, and administrative pages are restricted to
            accounts with an explicit admin role.
          </p>

          {/* What we collect */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            What we collect — full transparency
          </h2>
          <p className="text-gray-400 leading-relaxed mb-2">
            We collect the minimum needed to run the service. Concretely:
          </p>
          <ul className="text-gray-400 leading-relaxed list-disc pl-6 space-y-2">
            <li>
              <strong className="text-gray-200">Account &amp; billing:</strong> your
              email, and your license key, tier, and status. Payments are handled by
              Stripe — we never store card numbers.
            </li>
            <li>
              <strong className="text-gray-200">
                Usage metadata (licensed deployments):
              </strong>{" "}
              when your install is tied to a license key, each tool run records the
              tool&rsquo;s name, your QuickBooks company ID (an opaque identifier),
              an estimated time-saved value, and a timestamp — this powers your
              dashboard. It contains{" "}
              <strong className="text-gray-200">no financial content</strong> — no
              amounts, transactions, names, or balances.
            </li>
            <li>
              <strong className="text-gray-200">
                Local, no license key → no telemetry:
              </strong>{" "}
              if you run locally without a license key configured, no usage data is
              sent anywhere.
            </li>
          </ul>
          <p className="text-gray-400 leading-relaxed mt-4">
            We also keep operational event logs for connection events (connect,
            token refresh, disconnect). These are{" "}
            <strong className="text-gray-200">sanitized</strong> before storage —
            tokens, secrets, and credentials are automatically redacted.
          </p>

          {/* Transport & infra */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            Transport &amp; infrastructure
          </h2>
          <p className="text-gray-400 leading-relaxed">
            All traffic is over HTTPS/TLS; the connector forces HTTPS. Our web
            responses set HTTP Strict-Transport-Security (2&nbsp;years, including
            subdomains, preload-eligible), a Content-Security-Policy of{" "}
            <code className="text-gray-300">frame-ancestors &apos;none&apos;</code>,{" "}
            <code className="text-gray-300">X-Frame-Options: DENY</code>,{" "}
            <code className="text-gray-300">X-Content-Type-Options: nosniff</code>, a
            strict Referrer-Policy, and a Permissions-Policy that denies camera,
            microphone, and geolocation. Sensitive endpoints (token, OAuth, and
            checkout) are rate-limited. Secrets are held in a dedicated secrets
            manager and are never committed to source control; our CI actions are
            pinned to specific commit revisions.
          </p>
          <p className="text-gray-400 leading-relaxed mt-3">
            We build on established providers: Vercel (web &amp; API), Fly.io (the
            hosted connector), Supabase/Postgres (licenses and encrypted tokens),
            Stripe (payments), and Clerk (authentication). None of these has access
            to your QuickBooks financial data.
          </p>

          {/* Your control */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            Your control
          </h2>
          <p className="text-gray-400 leading-relaxed">
            You can disconnect a QuickBooks company at any time. When you do, we
            delete its token from our database{" "}
            <strong className="text-gray-200">and</strong> revoke it with Intuit.
            You can request deletion of your account data at any time. Account and
            license data is retained for the duration of your subscription plus 90
            days after cancellation.
          </p>

          {/* Disclosure */}
          <h2 className="text-xl font-semibold mt-10 mb-4 text-gray-100">
            Report a vulnerability
          </h2>
          <p className="text-gray-400 leading-relaxed">
            Found something? We want to hear from you. Email{" "}
            <a
              href="mailto:support@vasperacapital.com"
              className="text-cyan-400 hover:underline"
            >
              support@vasperacapital.com
            </a>{" "}
            and we&rsquo;ll respond promptly. Please give us a reasonable window to
            remediate before any public disclosure.
          </p>

          <p className="text-gray-500 leading-relaxed mt-10 text-sm">
            This page describes the product as built. For how we handle personal
            data, see our{" "}
            <a href="/privacy" className="text-cyan-400 hover:underline">
              Privacy Policy
            </a>
            ; for terms of use, see our{" "}
            <a href="/terms" className="text-cyan-400 hover:underline">
              Terms of Service
            </a>
            .
          </p>
        </div>
      </article>
    </main>
  );
}
