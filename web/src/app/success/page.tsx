"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function SuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [licenseKey, setLicenseKey] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      return;
    }

    // Poll for the license key (webhook may take a moment)
    let attempts = 0;
    const maxAttempts = 10;

    const poll = async () => {
      try {
        const res = await fetch(`/api/stripe/session?id=${sessionId}`);
        const data = await res.json();

        if (data.licenseKey) {
          setLicenseKey(data.licenseKey);
          setEmail(data.email);
          setTier(data.tier);
          setLoading(false);
          return;
        }
      } catch {
        // ignore
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 2000);
      } else {
        setLoading(false);
      }
    };

    poll();
  }, [sessionId]);

  const copyKey = () => {
    if (licenseKey) {
      navigator.clipboard.writeText(licenseKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const installUrl = "mcpb://install?name=accountingqb";
  const connectQBUrl = licenseKey
    ? `/api/oauth/start?license_key=${encodeURIComponent(licenseKey)}`
    : "#";

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 text-5xl">
          ✓
        </div>
        <h1 className="mt-8 text-3xl font-bold tracking-tight sm:text-4xl">
          Welcome to AccountingQB!
        </h1>
        <p className="mt-4 text-lg text-gray-300">
          Your 14-day free trial is active.
        </p>

        {/* License key display */}
        {loading ? (
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-8">
            <div className="flex items-center justify-center gap-3 text-gray-400">
              <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Generating your license key...
            </div>
          </div>
        ) : licenseKey ? (
          <div className="mt-8 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-8">
            <p className="text-sm text-gray-400 uppercase tracking-wider">Your License Key</p>
            <div className="mt-3 flex items-center justify-center gap-3">
              <code className="rounded-lg bg-black/40 px-4 py-3 text-lg font-mono text-cyan-400 tracking-wide">
                {licenseKey}
              </code>
              <button
                onClick={copyKey}
                className="rounded-lg border border-white/10 px-3 py-3 text-sm hover:bg-white/10 transition"
                title="Copy to clipboard"
              >
                {copied ? "✓" : "Copy"}
              </button>
            </div>
            {email && (
              <p className="mt-3 text-sm text-gray-400">
                Registered to <span className="text-gray-300">{email}</span>
                {tier && <> — <span className="capitalize text-cyan-400">{tier}</span> plan</>}
              </p>
            )}
          </div>
        ) : (
          <div className="mt-8 rounded-2xl border border-yellow-400/20 bg-yellow-400/5 p-8">
            <p className="text-gray-300">
              Your license key is being generated. Check your email shortly, or contact support if you don&apos;t receive it within a few minutes.
            </p>
          </div>
        )}

        {/* 3-Step Setup Flow */}
        {licenseKey && (
          <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-8 text-left">
            <h2 className="text-lg font-semibold text-center mb-6">Get Started in 3 Steps</h2>

            {/* Progress indicators */}
            <div className="flex justify-center gap-2 mb-8">
              {[1, 2, 3].map((step) => (
                <button
                  key={step}
                  onClick={() => setCurrentStep(step)}
                  className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold transition-all ${
                    currentStep === step
                      ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/25"
                      : currentStep > step
                      ? "bg-green-500 text-white"
                      : "border border-white/20 text-gray-500"
                  }`}
                >
                  {currentStep > step ? "✓" : step}
                </button>
              ))}
            </div>

            {/* Step 1: Install Extension */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                    1
                  </span>
                  <div>
                    <h3 className="font-semibold text-white">Install the Extension</h3>
                    <p className="mt-1 text-sm text-gray-400">
                      Click below to install AccountingQB in Claude Desktop. You&apos;ll be prompted to enter your license key.
                    </p>
                  </div>
                </div>
                <a
                  href={installUrl}
                  className="block w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-center text-lg font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
                >
                  Install in Claude Desktop
                </a>
                <p className="text-xs text-center text-gray-500">
                  Don&apos;t have Claude Desktop?{" "}
                  <a
                    href="https://claude.ai/download"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-cyan-400 hover:underline"
                  >
                    Download it here
                  </a>
                </p>
                <button
                  onClick={() => setCurrentStep(2)}
                  className="mt-4 w-full rounded-xl border border-white/10 px-6 py-3 text-sm font-medium hover:bg-white/10 transition"
                >
                  I&apos;ve installed it → Next
                </button>
              </div>
            )}

            {/* Step 2: Connect QuickBooks */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                    2
                  </span>
                  <div>
                    <h3 className="font-semibold text-white">Connect QuickBooks</h3>
                    <p className="mt-1 text-sm text-gray-400">
                      Authorize AccountingQB to access your QuickBooks Online company. You can connect multiple companies.
                    </p>
                  </div>
                </div>
                <div className="rounded-xl border border-green-400/20 bg-green-400/5 p-4">
                  <div className="flex items-start gap-3">
                    <span className="text-green-400 text-lg">🔒</span>
                    <div className="text-sm text-gray-300">
                      <p className="font-medium text-green-400">Your data stays secure</p>
                      <p className="mt-1">OAuth tokens are stored securely. Your financial data flows directly between Claude and QuickBooks.</p>
                    </div>
                  </div>
                </div>
                <a
                  href={connectQBUrl}
                  className="block w-full rounded-xl bg-gradient-to-r from-green-500 to-emerald-600 px-6 py-4 text-center text-lg font-semibold shadow-lg shadow-green-500/20 transition hover:shadow-green-500/40"
                >
                  Connect QuickBooks
                </a>
                <div className="flex gap-3">
                  <button
                    onClick={() => setCurrentStep(1)}
                    className="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium hover:bg-white/10 transition"
                  >
                    ← Back
                  </button>
                  <button
                    onClick={() => setCurrentStep(3)}
                    className="flex-1 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium hover:bg-white/10 transition"
                  >
                    Skip for now →
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Start Using */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-500 text-sm font-bold">
                    ✓
                  </span>
                  <div>
                    <h3 className="font-semibold text-white">You&apos;re All Set!</h3>
                    <p className="mt-1 text-sm text-gray-400">
                      Open Claude Desktop and start talking to your books.
                    </p>
                  </div>
                </div>
                <div className="rounded-xl bg-white/[0.03] p-5 text-center">
                  <p className="text-sm text-gray-400 mb-3">Try asking Claude:</p>
                  <p className="text-lg italic text-cyan-400">
                    &quot;Show me my P&amp;L for last quarter&quot;
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg bg-white/[0.04] p-3 text-center text-gray-400">
                    <span className="block text-2xl mb-1">91</span>
                    QuickBooks tools
                  </div>
                  <div className="rounded-lg bg-white/[0.04] p-3 text-center text-gray-400">
                    <span className="block text-2xl mb-1">9</span>
                    Tax prep tools
                  </div>
                </div>
                <a
                  href={`/dashboard?key=${encodeURIComponent(licenseKey)}`}
                  className="block w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-center font-semibold shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
                >
                  Go to Dashboard
                </a>
                <button
                  onClick={() => setCurrentStep(2)}
                  className="w-full rounded-xl border border-white/10 px-4 py-3 text-sm font-medium hover:bg-white/10 transition"
                >
                  ← Back
                </button>
              </div>
            )}
          </div>
        )}

        <div className="mt-6 flex items-center justify-center gap-4">
          <a
            href="/"
            className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
          >
            Back to Home
          </a>
          <a
            href="mailto:support@accountingqb.com"
            className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
          >
            Need Help?
          </a>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          Your trial includes full access to all 91 QuickBooks tools.
          <br />
          No credit card was charged. Cancel anytime.
        </p>
      </div>
    </main>
  );
}

export default function SuccessPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    }>
      <SuccessContent />
    </Suspense>
  );
}
