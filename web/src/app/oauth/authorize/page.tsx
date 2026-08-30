"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";

/**
 * /oauth/authorize — OAuth 2.1 consent page for the remote MCP connector.
 *
 * MCP clients (Claude web/desktop/mobile) land here with:
 *   response_type=code, client_id, redirect_uri, state, code_challenge,
 *   code_challenge_method=S256, scope
 *
 * Signed-out users are bounced to /sign-in and returned here. On approval we
 * POST /api/oauth2/authorize (Clerk-authenticated) which validates the
 * client + license ownership, mints a single-use code, and returns the
 * redirect URL.
 */

interface LicenseInfo {
  key: string;
  tier: string;
  status: string;
}

interface ClientInfo {
  client_name: string | null;
  redirect_uris: string[];
}

function AuthorizeContent() {
  const searchParams = useSearchParams();
  const { isLoaded, isSignedIn } = useUser();

  const responseType = searchParams.get("response_type");
  const clientId = searchParams.get("client_id") || "";
  const redirectUri = searchParams.get("redirect_uri") || "";
  const state = searchParams.get("state") || "";
  const codeChallenge = searchParams.get("code_challenge") || "";
  const codeChallengeMethod = searchParams.get("code_challenge_method") || "";
  const scope = searchParams.get("scope") || "";

  const [clientInfo, setClientInfo] = useState<ClientInfo | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [licenses, setLicenses] = useState<LicenseInfo[] | null>(null);
  const [selectedLicense, setSelectedLicense] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Static request validation (before any network calls).
  const requestError = useMemo(() => {
    if (!clientId || !redirectUri) return "Missing client_id or redirect_uri.";
    if (responseType !== "code") return "response_type must be 'code'.";
    if (!codeChallenge) return "Missing PKCE code_challenge.";
    if (codeChallengeMethod && codeChallengeMethod !== "S256")
      return "code_challenge_method must be S256.";
    return null;
  }, [clientId, redirectUri, responseType, codeChallenge, codeChallengeMethod]);

  // Signed-out → sign in, then come back here with the full query string.
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      const returnUrl = `${window.location.pathname}${window.location.search}`;
      window.location.href = `/sign-in?redirect_url=${encodeURIComponent(returnUrl)}`;
    }
  }, [isLoaded, isSignedIn]);

  // Look up the requesting app's registration.
  useEffect(() => {
    if (!clientId) return;
    fetch(`/api/oauth2/client-info?client_id=${encodeURIComponent(clientId)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error("Unknown application");
        setClientInfo(await res.json());
      })
      .catch(() => setClientError("This application is not registered."));
  }, [clientId]);

  // Fetch the signed-in user's licenses; auto-select when there's exactly one.
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    fetch("/api/user/licenses")
      .then(async (res) => (res.ok ? res.json() : { licenses: [] }))
      .then((data) => {
        const usable = (data.licenses || []).filter(
          (l: LicenseInfo) => l.status !== "canceled" && l.status !== "expired",
        );
        setLicenses(usable);
        if (usable.length === 1) setSelectedLicense(usable[0].key);
      })
      .catch(() => setLicenses([]));
  }, [isLoaded, isSignedIn]);

  const appName = clientInfo?.client_name || "An MCP application";

  const deny = () => {
    try {
      const url = new URL(redirectUri);
      url.searchParams.set("error", "access_denied");
      if (state) url.searchParams.set("state", state);
      window.location.href = url.toString();
    } catch {
      window.location.href = "/dashboard";
    }
  };

  const approve = async () => {
    if (!selectedLicense) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch("/api/oauth2/authorize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          redirect_uri: redirectUri,
          state,
          code_challenge: codeChallenge,
          code_challenge_method: codeChallengeMethod || "S256",
          scope,
          license_key: selectedLicense,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.redirect) {
        throw new Error(
          data.error_description || data.error || "Authorization failed",
        );
      }
      window.location.href = data.redirect;
    } catch (err) {
      setSubmitting(false);
      setSubmitError(
        err instanceof Error ? err.message : "Authorization failed",
      );
    }
  };

  if (!isLoaded || (isLoaded && !isSignedIn)) {
    return (
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      <nav className="border-b border-white/5 px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <a href="/" className="text-xl font-bold">
            <span className="text-white">Accounting</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              QB
            </span>
          </a>
        </div>
      </nav>

      <div className="mx-auto max-w-md px-6 py-16">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
          <h1 className="text-2xl font-bold">Authorize access</h1>

          {requestError || clientError ? (
            <div className="mt-6 rounded-xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300">
              {requestError || clientError}
            </div>
          ) : (
            <>
              <p className="mt-3 text-gray-400">
                <span className="font-semibold text-white">{appName}</span>{" "}
                wants to access your QuickBooks data through AccountingQB.
              </p>

              <div className="mt-6 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-gray-300">
                <p className="font-medium text-white mb-2">
                  This will allow it to:
                </p>
                <ul className="space-y-1 text-gray-400">
                  <li>• Read and manage your QuickBooks company data</li>
                  <li>• Run reports, invoices, expenses and more via Claude</li>
                </ul>
              </div>

              {/* License picker */}
              <div className="mt-6">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  License to connect
                </label>
                {licenses === null ? (
                  <p className="text-sm text-gray-500">Loading licenses…</p>
                ) : licenses.length === 0 ? (
                  <div className="rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-4 text-sm text-gray-300">
                    No active license found for your account.{" "}
                    <a
                      href="/pricing"
                      className="text-cyan-400 hover:underline"
                    >
                      Get a license
                    </a>{" "}
                    or{" "}
                    <a
                      href="/dashboard"
                      className="text-cyan-400 hover:underline"
                    >
                      link one in your dashboard
                    </a>
                    , then retry from Claude.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {licenses.map((l) => (
                      <label
                        key={l.key}
                        className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition ${
                          selectedLicense === l.key
                            ? "border-cyan-400/50 bg-cyan-400/10"
                            : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                        }`}
                      >
                        <input
                          type="radio"
                          name="license"
                          value={l.key}
                          checked={selectedLicense === l.key}
                          onChange={() => setSelectedLicense(l.key)}
                          className="accent-cyan-400"
                        />
                        <span className="font-mono text-sm text-cyan-400">
                          {l.key}
                        </span>
                        <span className="ml-auto text-xs uppercase tracking-wide text-gray-500">
                          {l.tier}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {submitError && (
                <div className="mt-4 rounded-xl border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-300">
                  {submitError}
                </div>
              )}

              <div className="mt-8 flex gap-3">
                <button
                  onClick={deny}
                  disabled={submitting}
                  className="flex-1 rounded-xl border border-white/10 px-6 py-3 font-medium hover:bg-white/10 transition disabled:opacity-50"
                >
                  Deny
                </button>
                <button
                  onClick={approve}
                  disabled={submitting || !selectedLicense}
                  className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition disabled:opacity-50"
                >
                  {submitting ? "Authorizing…" : "Approve"}
                </button>
              </div>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-gray-500">
          You&apos;ll be redirected back to the application after approving.
        </p>
      </div>
    </main>
  );
}

export default function OAuthAuthorizePage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
          <p className="text-gray-400">Loading…</p>
        </main>
      }
    >
      <AuthorizeContent />
    </Suspense>
  );
}
