"use client";

import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (res.ok) {
        setSent(true);
      } else {
        const data = await res.json();
        setError(data.error || "Failed to send magic link");
      }
    } catch {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <div className="max-w-md text-center p-8">
          <div className="text-6xl mb-6">&#x2709;</div>
          <h1 className="text-2xl font-bold">Check your email</h1>
          <p className="mt-4 text-gray-400">
            We sent a magic link to{" "}
            <span className="text-cyan-400">{email}</span>. Click the link to
            sign in.
          </p>
          <p className="mt-6 text-sm text-gray-500">
            Didn&apos;t receive it? Check your spam folder or{" "}
            <button
              onClick={() => setSent(false)}
              className="text-cyan-400 hover:underline"
            >
              try again
            </button>
            .
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
      <div className="max-w-md w-full p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <a href="/" className="inline-block">
            <span className="text-2xl font-bold">
              <span className="text-white">Accounting</span>
              <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                QB
              </span>
            </span>
          </a>
        </div>

        <h1 className="text-3xl font-bold text-center">Sign in</h1>
        <p className="mt-2 text-center text-gray-400">
          Enter your email to receive a magic link
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="email" className="sr-only">
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
              className="w-full rounded-lg bg-black/40 border border-white/10 px-4 py-3 text-white placeholder:text-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 py-3 font-semibold text-white transition hover:shadow-lg hover:shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Sending..." : "Send Magic Link"}
          </button>
        </form>

        <div className="mt-8 pt-8 border-t border-white/10">
          <p className="text-center text-sm text-gray-500">
            Have a license key?
          </p>
          <a
            href="/dashboard?legacy=true"
            className="mt-2 block text-center text-sm text-cyan-400 hover:underline"
          >
            Use license key login
          </a>
        </div>

        <p className="mt-8 text-center text-xs text-gray-600">
          By signing in, you agree to our{" "}
          <a href="/terms" className="text-gray-500 hover:text-white">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="/privacy" className="text-gray-500 hover:text-white">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </main>
  );
}
