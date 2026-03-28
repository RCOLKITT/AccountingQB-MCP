"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function ErrorContent() {
  const searchParams = useSearchParams();
  const message = searchParams.get("message") || "An unexpected error occurred.";

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-red-500/20 text-5xl">
          ✕
        </div>
        <h1 className="mt-8 text-3xl font-bold tracking-tight text-red-400">
          Connection Failed
        </h1>
        <p className="mt-4 text-lg text-gray-300">
          {message}
        </p>

        <div className="mt-8 rounded-2xl border border-red-400/20 bg-red-400/5 p-6">
          <p className="text-gray-300">
            Please close this window and try connecting again.
            If the problem persists, contact support.
          </p>
        </div>

        <div className="mt-8 flex items-center justify-center gap-4">
          <a
            href="/"
            className="rounded-xl border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
          >
            Back to Home
          </a>
          <a
            href="mailto:support@accountingqb.com"
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-sm font-semibold shadow-lg transition hover:shadow-cyan-500/40"
          >
            Contact Support
          </a>
        </div>
      </div>
    </main>
  );
}

export default function OAuthErrorPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    }>
      <ErrorContent />
    </Suspense>
  );
}
