"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

// Prevent static generation - this page uses search params
export const dynamic = "force-dynamic";

function SuccessContent() {
  const searchParams = useSearchParams();
  const company = searchParams.get("company") || "your company";

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 text-5xl">
          ✓
        </div>
        <h1 className="mt-8 text-3xl font-bold tracking-tight">
          QuickBooks Connected!
        </h1>
        <p className="mt-4 text-lg text-gray-300">
          <span className="text-cyan-400 font-medium">{company}</span> is now
          connected to AccountingQB.
        </p>

        <div className="mt-8 rounded-2xl border border-green-400/20 bg-green-400/5 p-6">
          <p className="text-gray-300">
            You can close this window and return to Claude Desktop. Your
            QuickBooks data is now accessible through natural conversation.
          </p>
        </div>

        <div className="mt-8 space-y-3">
          <p className="text-sm text-gray-500">Try asking Claude:</p>
          <p className="text-cyan-400 italic">
            &quot;Show me my P&L for last quarter&quot;
          </p>
        </div>

        <a
          href="/"
          className="mt-8 inline-block rounded-xl border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
        >
          Back to AccountingQB
        </a>
      </div>
    </main>
  );
}

export default function OAuthSuccessPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
          <p className="text-gray-400">Loading...</p>
        </main>
      }
    >
      <SuccessContent />
    </Suspense>
  );
}
