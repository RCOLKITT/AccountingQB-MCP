"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

interface Company {
  realmId: string;
  companyName: string;
}

interface License {
  key: string;
  tier: string;
  status: string;
  role?: string;
  trial_ends_at?: string | null;
}

interface User {
  id: string;
  email: string;
  displayName: string | null;
}

interface UsageStats {
  totalCalls: number;
  totalHoursSaved: number;
  callsThisMonth: number;
  callsThisWeek: number;
  topTools: Array<{ name: string; rawName: string; count: number }>;
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const keyParam = searchParams.get("key");
  const legacyMode = searchParams.get("legacy") === "true";

  // Auth state
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // License state
  const [licenses, setLicenses] = useState<License[]>([]);
  const [selectedLicense, setSelectedLicense] = useState<License | null>(null);
  const [legacyLicenseKey, setLegacyLicenseKey] = useState(keyParam || "");

  // Data state
  const [companies, setCompanies] = useState<Company[]>([]);
  const [stats, setStats] = useState<UsageStats | null>(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, []);

  // Fetch companies when license changes
  useEffect(() => {
    if (selectedLicense) {
      fetchCompanies(selectedLicense.key);
    }
  }, [selectedLicense]);

  const checkAuth = async () => {
    try {
      const res = await fetch("/api/auth/me");
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        setLicenses(data.licenses || []);
        if (data.licenses?.length > 0) {
          setSelectedLicense(data.licenses[0]);
        }
        // Fetch usage stats for authenticated users
        fetchStats();
      } else if (!legacyMode && !keyParam) {
        // Not authenticated and not in legacy mode - redirect to login
        router.push("/login");
        return;
      }
    } catch {
      // Auth check failed - continue with legacy mode if applicable
    } finally {
      setAuthLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/usage/stats");
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      // Stats are non-critical
    }
  };

  const fetchCompanies = async (licenseKey: string) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/oauth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey }),
      });

      const data = await res.json();

      if (res.ok) {
        setCompanies(data.companies || []);
        // If we're in legacy mode, also set the license info
        if (!user && data.license) {
          setSelectedLicense(data.license);
        }
      } else if (res.status === 404) {
        setCompanies([]);
        if (!user && data.license) {
          setSelectedLicense(data.license);
        }
      } else {
        setError(data.error || "Failed to fetch license info");
      }
    } catch {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  const handleLegacySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (legacyLicenseKey.trim()) {
      fetchCompanies(legacyLicenseKey.trim());
    }
  };

  const copyKey = () => {
    if (selectedLicense?.key) {
      navigator.clipboard.writeText(selectedLicense.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const disconnectCompany = async (realmId: string) => {
    if (!selectedLicense?.key) return;

    setDisconnecting(realmId);
    try {
      const res = await fetch("/api/oauth/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: selectedLicense.key, realmId }),
      });

      if (res.ok) {
        setCompanies(companies.filter((c) => c.realmId !== realmId));
      } else {
        const data = await res.json();
        alert(data.error || "Failed to disconnect company");
      }
    } catch {
      alert("Failed to disconnect company");
    } finally {
      setDisconnecting(null);
    }
  };

  const openBillingPortal = async () => {
    if (!selectedLicense?.key) return;

    setPortalLoading(true);
    try {
      const res = await fetch("/api/stripe/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: selectedLicense.key }),
      });

      const data = await res.json();

      if (res.ok && data.url) {
        window.location.href = data.url;
      } else {
        alert(data.error || "Failed to open billing portal");
      }
    } catch {
      alert("Failed to open billing portal");
    } finally {
      setPortalLoading(false);
    }
  };

  const signOut = async () => {
    setSigningOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/login");
    } catch {
      alert("Failed to sign out");
      setSigningOut(false);
    }
  };

  const connectQBUrl = selectedLicense?.key
    ? `/api/oauth/start?license_key=${encodeURIComponent(selectedLicense.key)}`
    : "#";

  // Loading state
  if (authLoading) {
    return (
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  // Legacy mode: license key input (when not authenticated)
  const showLegacyInput = !user && (legacyMode || keyParam) && !selectedLicense;

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Nav */}
      <nav className="border-b border-white/5 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <a href="/" className="text-xl font-bold">
            <span className="text-white">Accounting</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              QB
            </span>
          </a>
          <div className="flex items-center gap-4">
            {user && (
              <>
                <span className="text-sm text-gray-400">{user.email}</span>
                <button
                  onClick={signOut}
                  disabled={signingOut}
                  className="text-sm text-gray-400 hover:text-white transition"
                >
                  {signingOut ? "..." : "Sign out"}
                </button>
              </>
            )}
            <a
              href="mailto:support@vasperacapital.com"
              className="text-sm text-gray-400 hover:text-white transition"
            >
              Support
            </a>
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-2 text-gray-400">
          Manage your AccountingQB license and connected QuickBooks companies.
        </p>

        {/* Legacy License Key Input */}
        {showLegacyInput && (
          <form onSubmit={handleLegacySubmit} className="mt-8">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Enter your license key
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={legacyLicenseKey}
                  onChange={(e) => setLegacyLicenseKey(e.target.value)}
                  placeholder="LK-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
                  className="flex-1 rounded-lg bg-black/40 border border-white/10 px-4 py-3 font-mono text-cyan-400 placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/50"
                />
                <button
                  type="submit"
                  disabled={loading || !legacyLicenseKey.trim()}
                  className="rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 font-semibold transition hover:shadow-lg hover:shadow-cyan-500/20 disabled:opacity-50"
                >
                  {loading ? "Loading..." : "View Dashboard"}
                </button>
              </div>
              {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
              <p className="mt-4 text-sm text-gray-500">
                Prefer magic link login?{" "}
                <a href="/login" className="text-cyan-400 hover:underline">
                  Sign in with email
                </a>
              </p>
            </div>
          </form>
        )}

        {/* Main Dashboard Content */}
        {selectedLicense && (
          <div className="mt-8 space-y-6">
            {/* Usage Stats (only for authenticated users) */}
            {user && stats && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4 text-center">
                  <p className="text-3xl font-bold text-cyan-400">
                    {stats.totalHoursSaved}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">Hours Saved</p>
                </div>
                <div className="rounded-2xl border border-blue-400/20 bg-blue-400/5 p-4 text-center">
                  <p className="text-3xl font-bold text-blue-400">
                    {stats.totalCalls.toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">Total Queries</p>
                </div>
                <div className="rounded-2xl border border-purple-400/20 bg-purple-400/5 p-4 text-center">
                  <p className="text-3xl font-bold text-purple-400">
                    {stats.callsThisMonth}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">This Month</p>
                </div>
                <div className="rounded-2xl border border-green-400/20 bg-green-400/5 p-4 text-center">
                  <p className="text-3xl font-bold text-green-400">
                    {stats.callsThisWeek}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">This Week</p>
                </div>
              </div>
            )}

            {/* Top Tools (only for authenticated users with usage) */}
            {user && stats && stats.topTools.length > 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                <h2 className="text-lg font-semibold mb-4">Most Used Tools</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {stats.topTools.slice(0, 6).map((tool) => (
                    <div
                      key={tool.rawName}
                      className="flex items-center justify-between rounded-lg bg-white/[0.03] px-4 py-2"
                    >
                      <span className="text-gray-300">{tool.name}</span>
                      <span className="text-sm text-gray-500">
                        {tool.count}x
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* License Selector (for users with multiple licenses) */}
            {user && licenses.length > 1 && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                <h2 className="text-lg font-semibold mb-4">Your Licenses</h2>
                <div className="flex flex-wrap gap-2">
                  {licenses.map((lic) => (
                    <button
                      key={lic.key}
                      onClick={() => setSelectedLicense(lic)}
                      className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                        selectedLicense?.key === lic.key
                          ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                          : "bg-white/5 text-gray-400 border border-white/10 hover:border-white/20"
                      }`}
                    >
                      {lic.tier} ({lic.status})
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* License Card */}
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 uppercase tracking-wider">
                    License Key
                  </p>
                  <div className="mt-2 flex items-center gap-3">
                    <code className="rounded-lg bg-black/40 px-3 py-2 font-mono text-cyan-400 text-sm">
                      {selectedLicense.key}
                    </code>
                    <button
                      onClick={copyKey}
                      className="rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/10 transition"
                    >
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-400">Plan</p>
                  <p className="mt-1 font-semibold capitalize text-white">
                    {selectedLicense.tier}
                  </p>
                  <span
                    className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${
                      selectedLicense.status === "active"
                        ? "bg-green-500/20 text-green-400"
                        : selectedLicense.status === "trialing"
                        ? "bg-blue-500/20 text-blue-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {selectedLicense.status}
                  </span>
                </div>
              </div>
            </div>

            {/* Connected Companies */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Connected Companies</h2>
                <a
                  href={connectQBUrl}
                  className="rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 px-4 py-2 text-sm font-semibold transition hover:shadow-lg hover:shadow-green-500/20"
                >
                  + Connect QuickBooks
                </a>
              </div>

              {loading ? (
                <p className="text-gray-400">Loading companies...</p>
              ) : companies.length > 0 ? (
                <div className="space-y-3">
                  {companies.map((company) => (
                    <div
                      key={company.realmId}
                      className="flex items-center justify-between rounded-xl bg-white/[0.03] p-4"
                    >
                      <div>
                        <p className="font-medium text-white">
                          {company.companyName}
                        </p>
                        <p className="text-sm text-gray-500">
                          ID: {company.realmId}
                        </p>
                      </div>
                      <button
                        onClick={() => disconnectCompany(company.realmId)}
                        disabled={disconnecting === company.realmId}
                        className="rounded-lg border border-red-500/30 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition disabled:opacity-50"
                      >
                        {disconnecting === company.realmId
                          ? "Disconnecting..."
                          : "Disconnect"}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
                  <p className="text-gray-400">
                    No QuickBooks companies connected yet.
                  </p>
                  <a
                    href={connectQBUrl}
                    className="mt-4 inline-block rounded-lg bg-white/10 px-4 py-2 text-sm font-medium hover:bg-white/20 transition"
                  >
                    Connect your first company
                  </a>
                </div>
              )}
            </div>

            {/* Billing */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="text-lg font-semibold mb-4">Billing</h2>
              <p className="text-sm text-gray-400 mb-4">
                Manage your subscription, update payment method, or view
                invoices.
              </p>
              <button
                onClick={openBillingPortal}
                disabled={portalLoading}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm font-medium hover:bg-white/10 transition disabled:opacity-50"
              >
                {portalLoading ? "Opening..." : "Open Billing Portal"}
              </button>
            </div>

            {/* Quick Actions */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <a
                  href="mcpb://install?name=accountingqb"
                  className="rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-600/10 border border-cyan-500/20 p-4 hover:border-cyan-500/40 transition"
                >
                  <p className="font-medium text-white">Reinstall Extension</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Open in Claude Desktop
                  </p>
                </a>
                <a
                  href="mailto:support@vasperacapital.com"
                  className="rounded-xl bg-white/[0.03] border border-white/10 p-4 hover:border-white/20 transition"
                >
                  <p className="font-medium text-white">Contact Support</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Get help with your account
                  </p>
                </a>
              </div>
            </div>

            {/* Change License (legacy mode only) */}
            {!user && (
              <div className="text-center">
                <button
                  onClick={() => {
                    setSelectedLicense(null);
                    setCompanies([]);
                    setLegacyLicenseKey("");
                  }}
                  className="text-sm text-gray-500 hover:text-white transition"
                >
                  Use a different license key
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
          <p className="text-gray-400">Loading...</p>
        </main>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
