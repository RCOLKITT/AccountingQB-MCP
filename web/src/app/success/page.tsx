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

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 text-5xl">
          ✓
        </div>
        <h1 className="mt-8 text-3xl font-bold tracking-tight sm:text-4xl">
          Welcome aboard!
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

        <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-8 text-left">
          <h2 className="text-lg font-semibold">Next steps</h2>
          <ol className="mt-4 space-y-4 text-gray-300">
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                1
              </span>
              <span>
                Copy your license key above (starts with{" "}
                <code className="rounded bg-white/10 px-1.5 py-0.5 text-sm">LK-</code>)
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                2
              </span>
              <span>
                Install the extension in Claude Desktop (one-click from the
                extension directory)
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                3
              </span>
              <span>
                Connect your QuickBooks account through the OAuth setup flow
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                4
              </span>
              <span>
                Start talking to your books — try{" "}
                <em>&ldquo;Show me my P&amp;L for last quarter&rdquo;</em>
              </span>
            </li>
          </ol>
        </div>

        <div className="mt-8 flex items-center justify-center gap-4">
          <a
            href="/"
            className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
          >
            Back to Home
          </a>
          <a
            href="mailto:ryan@vasperacapital.com"
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
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
