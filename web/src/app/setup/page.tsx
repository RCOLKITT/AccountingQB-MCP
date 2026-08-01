"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function StepIndicator({ number, active, done }: { number: number; active: boolean; done: boolean }) {
  return (
    <span
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold transition-all ${
        done
          ? "bg-green-500 text-white"
          : active
          ? "bg-gradient-to-r from-cyan-400 to-blue-500 text-white shadow-lg shadow-cyan-500/25"
          : "border border-white/20 text-gray-500"
      }`}
    >
      {done ? "✓" : number}
    </span>
  );
}

function SetupContent() {
  const searchParams = useSearchParams();
  const licenseKey = searchParams.get("key");
  const [currentStep, setCurrentStep] = useState(1);
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedConfig, setCopiedConfig] = useState(false);

  const copyToClipboard = (text: string, setter: (v: boolean) => void) => {
    navigator.clipboard.writeText(text);
    setter(true);
    setTimeout(() => setter(false), 2000);
  };

  const mcpConfig = `{
  "mcpServers": {
    "quickbooks-accounting": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "${licenseKey || "YOUR_LICENSE_KEY"}",
        "QB_CLIENT_ID": "YOUR_INTUIT_CLIENT_ID",
        "QB_CLIENT_SECRET": "YOUR_INTUIT_CLIENT_SECRET",
        "QB_REALM_ID": "YOUR_COMPANY_ID",
        "QB_REFRESH_TOKEN": "YOUR_REFRESH_TOKEN"
      }
    }
  }
}`;

  const steps = [
    {
      title: "Save Your License Key",
      description: "You'll need this to activate the paid tools.",
    },
    {
      title: "Create a QuickBooks App",
      description: "Get your API credentials from Intuit Developer.",
    },
    {
      title: "Connect QuickBooks",
      description: "Authorize access to your QuickBooks company.",
    },
    {
      title: "Install in Claude Desktop",
      description: "Add the MCP server to your Claude config.",
    },
  ];

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Nav */}
      <nav className="border-b border-white/5 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <a href="/" className="text-xl font-bold">
            <span className="text-white">Accounting</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">QB</span>
          </a>
          <a
            href="mailto:support@vasperacapital.com"
            className="text-sm text-gray-400 hover:text-white transition"
          >
            Need help?
          </a>
        </div>
      </nav>

      <div className="mx-auto max-w-3xl px-6 py-12">
        {/* New easier flow banner */}
        <div className="mb-8 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6">
          <div className="flex items-start gap-4">
            <span className="text-2xl">✨</span>
            <div>
              <h2 className="font-semibold text-white">New: One-Click Setup</h2>
              <p className="mt-1 text-sm text-gray-300">
                We now offer a simpler setup flow — no Intuit developer account needed. Just install the extension and connect your QuickBooks with one click.
              </p>
              <a
                href="/dashboard"
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-sm font-semibold transition hover:shadow-lg hover:shadow-cyan-500/20"
              >
                Use Easy Setup →
              </a>
            </div>
          </div>
        </div>

        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Advanced Setup (Self-Hosted)
        </h1>
        <p className="mt-3 text-lg text-gray-400">
          For developers who want to use their own Intuit OAuth credentials. Most users should use the{" "}
          <a href="/dashboard" className="text-cyan-400 hover:underline">easy setup</a> instead.
        </p>

        {/* Progress bar */}
        <div className="mt-8 flex items-center gap-2">
          {steps.map((_, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <StepIndicator number={i + 1} active={currentStep === i + 1} done={currentStep > i + 1} />
              {i < steps.length - 1 && (
                <div className={`h-px flex-1 ${currentStep > i + 1 ? "bg-green-500" : "bg-white/10"}`} />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: License Key */}
        {currentStep === 1 && (
          <div className="mt-10 space-y-6">
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-8">
              <h2 className="text-xl font-semibold">Step 1: Save Your License Key</h2>
              <p className="mt-2 text-gray-400">
                This key unlocks all 110 QuickBooks tools. Keep it somewhere safe — you&apos;ll paste it into your config in Step 4.
              </p>
              {licenseKey ? (
                <div className="mt-5 flex items-center gap-3">
                  <code className="flex-1 rounded-lg bg-black/40 px-4 py-3 font-mono text-cyan-400 tracking-wide text-center">
                    {licenseKey}
                  </code>
                  <button
                    onClick={() => copyToClipboard(licenseKey, setCopiedKey)}
                    className="rounded-lg border border-white/10 px-4 py-3 text-sm font-medium hover:bg-white/10 transition whitespace-nowrap"
                  >
                    {copiedKey ? "✓ Copied" : "Copy"}
                  </button>
                </div>
              ) : (
                <div className="mt-5 rounded-lg border border-yellow-400/20 bg-yellow-400/5 p-4 text-sm text-yellow-300">
                  No license key detected. Check your email or the checkout success page for your key (starts with <code className="bg-white/10 px-1 rounded">LK-</code>).
                </div>
              )}
            </div>
            <button
              onClick={() => setCurrentStep(2)}
              className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-lg font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
            >
              I&apos;ve saved my key → Next
            </button>
          </div>
        )}

        {/* Step 2: Create QuickBooks App */}
        {currentStep === 2 && (
          <div className="mt-10 space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-xl font-semibold">Step 2: Create a QuickBooks Developer App</h2>
              <p className="mt-2 text-gray-400">
                You need API credentials from Intuit to let AccountingQB read your QuickBooks data. This takes about 2 minutes.
              </p>

              <ol className="mt-6 space-y-5 text-gray-300">
                <li className="flex gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-blue-400 text-sm font-bold">a</span>
                  <div>
                    <p>Go to <a href="https://developer.intuit.com" target="_blank" rel="noopener noreferrer" className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300">developer.intuit.com</a> and sign in with your Intuit account (same one you use for QuickBooks).</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-blue-400 text-sm font-bold">b</span>
                  <div>
                    <p>Click <strong className="text-white">Dashboard</strong> → <strong className="text-white">Create an app</strong>.</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-blue-400 text-sm font-bold">c</span>
                  <div>
                    <p>Select <strong className="text-white">QuickBooks Online and Payments</strong>. Name it anything (e.g. &quot;AccountingQB&quot;).</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-blue-400 text-sm font-bold">d</span>
                  <div>
                    <p>Under <strong className="text-white">Keys &amp; credentials</strong> → <strong className="text-white">Production</strong>, copy your:</p>
                    <ul className="mt-2 space-y-1 text-sm">
                      <li>• <code className="rounded bg-white/10 px-1.5 py-0.5">Client ID</code></li>
                      <li>• <code className="rounded bg-white/10 px-1.5 py-0.5">Client Secret</code></li>
                    </ul>
                  </div>
                </li>
                <li className="flex gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-blue-400 text-sm font-bold">e</span>
                  <div>
                    <p>Under <strong className="text-white">Redirect URIs</strong>, add:</p>
                    <code className="mt-1 block rounded-lg bg-black/40 px-3 py-2 text-sm text-cyan-400">https://accountingqb.com/api/oauth/callback</code>
                  </div>
                </li>
              </ol>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep(1)}
                className="rounded-xl border border-white/10 px-6 py-4 text-sm font-medium hover:bg-white/10 transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setCurrentStep(3)}
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-lg font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
              >
                I have my Client ID &amp; Secret → Next
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Connect QuickBooks */}
        {currentStep === 3 && (
          <div className="mt-10 space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-xl font-semibold">Step 3: Connect Your QuickBooks Company</h2>
              <p className="mt-2 text-gray-400">
                Authorize AccountingQB to access your QuickBooks data. With this self-hosted setup, your data stays on your machine — we never store it on our servers.
              </p>

              <div className="mt-6 rounded-xl border border-green-400/20 bg-green-400/5 p-5">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 text-green-400 text-lg">🔒</span>
                  <div className="text-sm text-gray-300">
                    <p className="font-medium text-green-400">Privacy-first architecture</p>
                    <p className="mt-1">With this setup, OAuth tokens are stored locally on your computer only. QuickBooks data is fetched directly from your machine to Intuit&apos;s API — it never passes through our servers.</p>
                  </div>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <p className="text-gray-300">Once you have the MCP server installed (next step), connect by running the OAuth flow. With this setup, the server will guide you through authorizing access and will automatically save your tokens locally.</p>
                <p className="text-gray-300">You&apos;ll need your <strong className="text-white">Company ID (Realm ID)</strong> — find it in your QuickBooks URL after <code className="rounded bg-white/10 px-1.5 py-0.5 text-sm">app.qbo.intuit.com/app/</code>.</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep(2)}
                className="rounded-xl border border-white/10 px-6 py-4 text-sm font-medium hover:bg-white/10 transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setCurrentStep(4)}
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-lg font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
              >
                Got it → Final Step
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Install in Claude */}
        {currentStep === 4 && (
          <div className="mt-10 space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-xl font-semibold">Step 4: Add to Claude Desktop</h2>
              <p className="mt-2 text-gray-400">
                Add this MCP server configuration to your Claude Desktop settings. Replace the placeholder values with your actual credentials.
              </p>

              <div className="mt-6 space-y-4">
                <div>
                  <p className="text-sm text-gray-400 mb-2">Open your Claude Desktop config file:</p>
                  <div className="space-y-2 text-sm">
                    <p className="text-gray-300"><strong className="text-white">macOS:</strong> <code className="rounded bg-black/40 px-2 py-1 text-cyan-400">~/Library/Application Support/Claude/claude_desktop_config.json</code></p>
                    <p className="text-gray-300"><strong className="text-white">Windows:</strong> <code className="rounded bg-black/40 px-2 py-1 text-cyan-400">%APPDATA%\Claude\claude_desktop_config.json</code></p>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm text-gray-400">Add this to the config (merge with existing if you have other servers):</p>
                    <button
                      onClick={() => copyToClipboard(mcpConfig, setCopiedConfig)}
                      className="rounded border border-white/10 px-3 py-1 text-xs hover:bg-white/10 transition"
                    >
                      {copiedConfig ? "✓ Copied" : "Copy Config"}
                    </button>
                  </div>
                  <pre className="rounded-xl bg-black/60 p-5 text-sm text-cyan-400 overflow-x-auto border border-white/5">
                    <code>{mcpConfig}</code>
                  </pre>
                </div>

                <div className="rounded-xl border border-blue-400/20 bg-blue-400/5 p-5 text-sm">
                  <p className="font-medium text-blue-400">Replace these values:</p>
                  <ul className="mt-2 space-y-1 text-gray-300">
                    <li>• <code className="text-cyan-400">YOUR_INTUIT_CLIENT_ID</code> — from Step 2</li>
                    <li>• <code className="text-cyan-400">YOUR_INTUIT_CLIENT_SECRET</code> — from Step 2</li>
                    <li>• <code className="text-cyan-400">YOUR_COMPANY_ID</code> — from your QuickBooks URL</li>
                    <li>• <code className="text-cyan-400">YOUR_REFRESH_TOKEN</code> — from the OAuth flow in Step 3</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-green-400/20 bg-green-400/5 p-8 text-center">
              <div className="text-4xl mb-3">🎉</div>
              <h3 className="text-xl font-semibold">You&apos;re all set!</h3>
              <p className="mt-2 text-gray-400">
                Restart Claude Desktop and try asking:
              </p>
              <p className="mt-3 text-lg italic text-cyan-400">
                &quot;Show me my P&amp;L for last quarter&quot;
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep(3)}
                className="rounded-xl border border-white/10 px-6 py-4 text-sm font-medium hover:bg-white/10 transition"
              >
                ← Back
              </button>
              <a
                href="/"
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-lg font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40 text-center"
              >
                Back to Home
              </a>
            </div>
          </div>
        )}

        {/* Help footer */}
        <div className="mt-12 border-t border-white/5 pt-8 text-center text-sm text-gray-500">
          <p>
            Stuck? Email <a href="mailto:support@vasperacapital.com" className="text-cyan-400 hover:underline">support@vasperacapital.com</a> and we&apos;ll help you get connected.
          </p>
        </div>
      </div>
    </main>
  );
}

export default function SetupPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    }>
      <SetupContent />
    </Suspense>
  );
}
