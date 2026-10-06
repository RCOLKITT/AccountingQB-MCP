"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";

/**
 * /download — the trial gate for the desktop app. /api/download/[platform]
 * redirects here when a download has no trial context. We capture an email
 * (skipped for signed-in users), mint a tracked no-credit-card trial via
 * /api/trial/start, then send the user to the keyed download URL (with `g=1`
 * so /api/download serves the asset instead of bouncing back here).
 */
function platformLabel(p: string): string {
  return p === "windows" ? "Windows" : "macOS";
}

function DownloadContent() {
  const params = useSearchParams();
  const platform = params.get("platform") === "windows" ? "windows" : "macos";
  const { isLoaded, isSignedIn, user } = useUser();
  const signedInEmail = user?.primaryEmailAddress?.emailAddress || "";

  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);

  async function start(addr: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/trial/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: addr, platform }),
      });
      const data = await res.json();
      if (!res.ok || !data.downloadUrl) {
        throw new Error(
          data.error === "invalid_email"
            ? "Please enter a valid email address."
            : "Something went wrong — please try again.",
        );
      }
      setStarted(true);
      // Append g=1 so the download endpoint serves the asset (no gate re-loop),
      // even if trial issuance failed (the email lead is already captured).
      const sep = data.downloadUrl.includes("?") ? "&" : "?";
      window.location.href = `${data.downloadUrl}${sep}g=1`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  // Signed-in users already gave us an email — start immediately.
  useEffect(() => {
    if (isLoaded && isSignedIn && signedInEmail && !busy && !started) {
      void start(signedInEmail);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn, signedInEmail]);

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      <nav className="border-b border-white/5 px-6 py-4">
        <a href="/" className="text-xl font-bold">
          <span className="text-white">Accounting</span>
          <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            QB
          </span>
        </a>
      </nav>

      <div className="mx-auto max-w-md px-6 py-16">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
          <h1 className="text-2xl font-bold">
            Download AccountingQB for {platformLabel(platform)}
          </h1>
          <p className="mt-3 text-gray-400">
            Start your free 14-day trial — no credit card. Enter your email and
            your download will begin; we&apos;ll send your license key so you
            can activate the app.
          </p>

          {started ? (
            <p className="mt-6 rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4 text-sm text-emerald-300">
              Your download is starting and your license key is on its way to
              your inbox…
            </p>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void start(email);
              }}
              className="mt-6 flex flex-col gap-3"
            >
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-cyan-400/50"
              />
              <button
                type="submit"
                disabled={busy}
                className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40 disabled:opacity-60"
              >
                {busy
                  ? "Starting…"
                  : `Start trial & download for ${platformLabel(platform)}`}
              </button>
              {error && <p className="text-xs text-red-400">{error}</p>}
              <p className="text-center text-xs text-gray-500">
                No credit card required. Cancel anytime.
              </p>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}

export default function DownloadPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
          <p className="text-gray-400">Loading…</p>
        </main>
      }
    >
      <DownloadContent />
    </Suspense>
  );
}
