"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";

/**
 * /download — download-FIRST capture. The desktop app starts downloading the
 * moment this page loads (no email wall), then we offer to email the license
 * key + setup steps. Email is encouraged, never required — getting the file is
 * decoupled from the trial mint, so we stop losing the download to a form.
 * /api/trial/start mints the tracked no-credit-card trial and emails the key.
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
  const [keySent, setKeySent] = useState(false);
  const dlStarted = useRef(false);

  // g=1 tells /api/download the gate is satisfied → it serves the asset.
  const assetUrl = `/api/download/${platform}?g=1`;

  // Download-first: kick off the file immediately on load, no email required.
  useEffect(() => {
    if (dlStarted.current) return;
    dlStarted.current = true;
    const a = document.createElement("a");
    a.href = assetUrl;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Capture email → mint the trial + email the key. Does NOT gate the download
  // (the file is already on its way) — this only sends the key.
  async function sendKey(addr: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/trial/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: addr, platform }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          data.error === "invalid_email"
            ? "Please enter a valid email address."
            : "Something went wrong — please try again.",
        );
      }
      setKeySent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  // Signed-in users: send the key automatically — zero friction.
  useEffect(() => {
    if (isLoaded && isSignedIn && signedInEmail && !keySent && !busy) {
      void sendKey(signedInEmail);
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
            AccountingQB for {platformLabel(platform)} is downloading…
          </h1>
          <p className="mt-3 text-sm text-gray-400">
            Your download started automatically. If it didn&apos;t,{" "}
            <a href={assetUrl} className="text-cyan-400 underline">
              click here
            </a>
            .
          </p>

          {keySent ? (
            <p className="mt-6 rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4 text-sm text-emerald-300">
              Your license key and setup steps are on their way to your inbox —
              activate the app with it to start your free 14-day trial.
            </p>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void sendKey(email);
              }}
              className="mt-6 flex flex-col gap-3"
            >
              <p className="text-sm text-gray-300">
                Want your <strong>free 14-day trial key</strong> (no credit
                card)? Enter your email and we&apos;ll send it with setup steps.
              </p>
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
                {busy ? "Sending…" : "Email me my license key"}
              </button>
              {error && <p className="text-xs text-red-400">{error}</p>}
              <p className="text-center text-xs text-gray-500">
                No credit card required. Cancel anytime. By continuing you agree
                to our{" "}
                <a href="/terms" className="underline hover:text-gray-300">
                  Terms of Service
                </a>{" "}
                and{" "}
                <a href="/privacy" className="underline hover:text-gray-300">
                  Privacy Policy
                </a>
                .
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
