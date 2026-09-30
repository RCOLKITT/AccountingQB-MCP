"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";

/**
 * Desktop-app download as a tracked, no-credit-card trial (Door 2).
 *
 * Clicking a platform captures an email (skipped for signed-in users), which
 * POSTs /api/trial/start to mint/reuse a 14-day trialing license, then the
 * returned key-tagged download URL starts the download. When `enabled` is false
 * we render the original direct-download links (instant rollback via the
 * TRIAL_AT_DOWNLOAD_ENABLED flag on the server).
 */
type Platform = "macos" | "windows";

const MAC_ICON =
  "M16.365 1.43c0 1.14-.416 2.2-1.11 2.99-.84.95-2.2 1.68-3.32 1.6-.14-1.12.42-2.3 1.08-3.03.75-.83 2.05-1.46 3.35-1.56zM20.9 17.02c-.55 1.27-.81 1.83-1.52 2.95-.99 1.56-2.39 3.5-4.12 3.51-1.54.02-1.94-1-4.03-.99-2.09.01-2.53 1.01-4.07.99-1.73-.02-3.06-1.77-4.05-3.33-2.77-4.37-3.06-9.5-1.35-12.22 1.21-1.93 3.13-3.06 4.93-3.06 1.83 0 2.98 1.01 4.5 1.01 1.47 0 2.36-1.01 4.48-1.01 1.6 0 3.3.87 4.51 2.38-3.96 2.17-3.32 7.83.29 9.79z";
const WIN_ICON =
  "M3 5.1l7.5-1.02v7.23H3V5.1zm0 13.8l7.5 1.02v-7.14H3v6.12zM11.4 3.95L21 2.62v8.69h-9.6V3.95zm0 16.1L21 21.38v-8.61h-9.6v7.28z";

const PILL =
  "flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-[#0a0e1a] shadow-lg shadow-black/20 transition hover:bg-slate-200 disabled:opacity-60";

function PlatformIcon({ platform }: { platform: Platform }) {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d={platform === "macos" ? MAC_ICON : WIN_ICON} />
    </svg>
  );
}

export default function DownloadTrial({ enabled }: { enabled: boolean }) {
  const { isSignedIn, user } = useUser();
  const signedInEmail = user?.primaryEmailAddress?.emailAddress || "";

  const [picked, setPicked] = useState<Platform | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function start(platform: Platform, addr: string) {
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
      setSentTo(addr);
      // Start the (key-tagged) download.
      window.location.href = data.downloadUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  function onPick(platform: Platform) {
    setError(null);
    if (signedInEmail) {
      // Known user — no need to ask again.
      void start(platform, signedInEmail);
      return;
    }
    setPicked((p) => (p === platform ? null : platform));
  }

  // Rollback path: plain direct-download links (pre-trial behavior).
  if (!enabled) {
    return (
      <div className="flex flex-col items-center gap-3 sm:flex-row">
        <a href="/api/download/macos" className={PILL}>
          <PlatformIcon platform="macos" /> Download for macOS
        </a>
        <a href="/api/download/windows" className={PILL}>
          <PlatformIcon platform="windows" /> Download for Windows
        </a>
      </div>
    );
  }

  if (sentTo) {
    return (
      <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 px-5 py-4 text-center text-sm">
        <p className="font-semibold text-emerald-300">
          Your download is starting.
        </p>
        <p className="mt-1 text-gray-400">
          We emailed your 14-day trial license key to{" "}
          <span className="text-white">{sentTo}</span>. No credit card required.
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-3">
      <div className="flex flex-col items-center gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => onPick("macos")}
          disabled={busy}
          className={PILL}
        >
          <PlatformIcon platform="macos" /> Download for macOS
        </button>
        <button
          type="button"
          onClick={() => onPick("windows")}
          disabled={busy}
          className={PILL}
        >
          <PlatformIcon platform="windows" /> Download for Windows
        </button>
      </div>

      {picked && !signedInEmail && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void start(picked, email);
          }}
          className="flex w-full flex-col items-center gap-2"
        >
          <p className="text-xs text-gray-400">
            Start your free 14-day trial — no credit card. We&apos;ll email your
            license key.
          </p>
          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-cyan-400/50"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40 disabled:opacity-60"
            >
              {busy
                ? "Starting…"
                : `Download for ${picked === "macos" ? "macOS" : "Windows"}`}
            </button>
          </div>
        </form>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
