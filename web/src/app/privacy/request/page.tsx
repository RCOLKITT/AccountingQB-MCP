"use client";

import { useState } from "react";

// Self-serve data-subject request form (GDPR / CCPA / PIPEDA). Posts to
// /api/privacy/request, which records the request and alerts ops. Fulfillment
// is handled by a human within 30 days.
const TYPES: { value: string; label: string }[] = [
  { value: "access", label: "Access the data you hold about me" },
  { value: "delete", label: "Delete my data" },
  { value: "correction", label: "Correct inaccurate data" },
  { value: "export", label: "Export my data (portable copy)" },
  { value: "other", label: "Something else" },
];

export default function PrivacyRequest() {
  const [email, setEmail] = useState("");
  const [type, setType] = useState("access");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/privacy/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, type, message }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(
          data.error === "invalid_email"
            ? "Please enter a valid email address."
            : "Something went wrong. Email privacy@vasperacapital.com instead.",
        );
        return;
      }
      setDone(true);
    } catch {
      setError(
        "Something went wrong. Email privacy@vasperacapital.com instead.",
      );
    } finally {
      setBusy(false);
    }
  }

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
          <a
            href="/privacy"
            className="text-sm text-gray-400 hover:text-gray-100"
          >
            &larr; Privacy Policy
          </a>
        </div>
      </nav>

      <article className="mx-auto max-w-xl px-6 py-16">
        <h1 className="text-3xl font-bold tracking-tight text-gray-100">
          Privacy request
        </h1>
        <p className="mt-3 text-gray-400">
          Exercise your data rights (access, deletion, correction, export). We
          respond within 30 days and never discriminate against you for asking.
        </p>

        {done ? (
          <p className="mt-8 rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4 text-sm text-emerald-300">
            Thanks — your request is logged and we&apos;ll follow up at this
            email within 30 days.
          </p>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
            className="mt-8 flex flex-col gap-4"
          >
            <label className="text-sm text-gray-300">
              Email (the account the request is about)
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-cyan-400/50"
              />
            </label>
            <label className="text-sm text-gray-300">
              Request type
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/50"
              >
                {TYPES.map((t) => (
                  <option
                    key={t.value}
                    value={t.value}
                    className="bg-[#0a0e1a]"
                  >
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-gray-300">
              Details (optional)
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-cyan-400/50"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40 disabled:opacity-60"
            >
              {busy ? "Submitting…" : "Submit request"}
            </button>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <p className="text-xs text-gray-500">
              Prefer email? Write to{" "}
              <a
                href="mailto:privacy@vasperacapital.com"
                className="underline hover:text-gray-300"
              >
                privacy@vasperacapital.com
              </a>
              .
            </p>
          </form>
        )}
      </article>
    </main>
  );
}
