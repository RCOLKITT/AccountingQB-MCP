"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useUser, UserButton, SignInButton, SignedIn, SignedOut } from "@clerk/nextjs";
import { SetupPrompt } from "@/components/setup/SetupPrompt";

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

  // Clerk auth
  const { isLoaded: clerkLoaded, isSignedIn, user: clerkUser } = useUser();

  // Legacy auth state (for existing users)
  const [legacyUser, setLegacyUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // Combined user - prefer Clerk, fall back to legacy
  const user = clerkUser
    ? { id: clerkUser.id, email: clerkUser.primaryEmailAddress?.emailAddress || "", displayName: clerkUser.fullName }
    : legacyUser;

  // License state
  const [licenses, setLicenses] = useState<License[]>([]);
  const [selectedLicense, setSelectedLicense] = useState<License | null>(null);
  const [legacyLicenseKey, setLegacyLicenseKey] = useState(keyParam || "");

  // Data state
  const [companies, setCompanies] = useState<Company[]>([]);
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [setupStatus, setSetupStatus] = useState<{
    claudeConfigured: boolean;
    qbConnected: boolean;
  } | null>(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  // Check auth on mount (for legacy users and license linking)
  useEffect(() => {
    if (clerkLoaded) {
      checkAuth();
    }
  }, [clerkLoaded, isSignedIn]);

  // Fetch companies and setup status when license changes
  useEffect(() => {
    if (selectedLicense) {
      fetchCompanies(selectedLicense.key);
      fetchSetupStatus(selectedLicense.key);
    }
  }, [selectedLicense]);

  const checkAuth = async () => {
    try {
      // If Clerk user is signed in, fetch their licenses
      if (isSignedIn && clerkUser) {
        const res = await fetch("/api/user/licenses");
        if (res.ok) {
          const data = await res.json();
          setLicenses(data.licenses || []);
          if (data.licenses?.length > 0) {
            setSelectedLicense(data.licenses[0]);
          }
          fetchStats();
        }
      } else {
        // Try legacy auth for existing users
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          setLegacyUser(data.user);
          setLicenses(data.licenses || []);
          if (data.licenses?.length > 0) {
            setSelectedLicense(data.licenses[0]);
          }
          fetchStats();
        }
      }
    } catch {
      // Auth check failed - continue with license key mode if applicable
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

  const fetchSetupStatus = async (licenseKey: string) => {
    try {
      const res = await fetch(`/api/setup/verify?license_key=${encodeURIComponent(licenseKey)}`);
      if (res.ok) {
        const data = await res.json();
        setSetupStatus(data.setup);
      }
    } catch {
      // Setup status is non-critical
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

  const handleLinkLicense = async (e: React.FormEvent) => {
    e.preventDefault();
    const key = legacyLicenseKey.trim();
    if (!key) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/user/link-license", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: key }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        // Re-fetch licenses so the newly linked license appears durably
        await checkAuth();
      } else {
        setError(data.error || "Failed to link license");
      }
    } catch {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
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
  if (!clerkLoaded || authLoading) {
    return (
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  // Show license key input when not authenticated and no license selected
  const showLegacyInput = !isSignedIn && !legacyUser && (legacyMode || keyParam) && !selectedLicense;

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
            <SignedIn>
              <a
                href="/dashboard/features"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                All 94 Tools
              </a>
              {(clerkUser?.publicMetadata as { role?: string })?.role === "admin" && (
                <a
                  href="/admin"
                  className="text-sm text-cyan-400 hover:text-cyan-300 transition font-medium"
                >
                  Admin
                </a>
              )}
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: "w-8 h-8",
                  },
                }}
              />
            </SignedIn>
            <SignedOut>
              {legacyUser ? (
                <>
                  <span className="text-sm text-gray-400">{legacyUser.email}</span>
                  <button
                    onClick={signOut}
                    disabled={signingOut}
                    className="text-sm text-gray-400 hover:text-white transition"
                  >
                    {signingOut ? "..." : "Sign out"}
                  </button>
                </>
              ) : (
                <SignInButton mode="modal">
                  <button className="text-sm text-gray-400 hover:text-white transition">
                    Sign in
                  </button>
                </SignInButton>
              )}
            </SignedOut>
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

        {/* No License State - for signed in users without a license */}
        {isSignedIn && !selectedLicense && !showLegacyInput && (
          <div className="mt-8 rounded-2xl border border-yellow-500/20 bg-yellow-500/5 p-8">
            <h2 className="text-xl font-semibold text-white">No License Found</h2>
            <p className="mt-2 text-gray-400">
              We couldn&apos;t find a license linked to your account ({clerkUser?.primaryEmailAddress?.emailAddress}).
            </p>
            <div className="mt-6 space-y-4">
              <div className="rounded-xl bg-white/5 p-4">
                <p className="text-sm font-medium text-white mb-2">Already purchased?</p>
                <p className="text-sm text-gray-400 mb-3">
                  Enter your license key below to link it to your account:
                </p>
                <form onSubmit={handleLinkLicense} className="flex gap-2">
                  <input
                    type="text"
                    value={legacyLicenseKey}
                    onChange={(e) => setLegacyLicenseKey(e.target.value)}
                    placeholder="LK-XXXXXXXX..."
                    className="flex-1 rounded-lg bg-black/40 border border-white/10 px-4 py-2 font-mono text-cyan-400 placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/50"
                  />
                  <button
                    type="submit"
                    disabled={loading || !legacyLicenseKey.trim()}
                    className="rounded-lg bg-cyan-500 px-4 py-2 font-medium hover:bg-cyan-600 transition disabled:opacity-50"
                  >
                    {loading ? "..." : "Link"}
                  </button>
                </form>
                {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
              </div>
              <div className="text-center">
                <span className="text-gray-500">or</span>
              </div>
              <a
                href="/#pricing"
                className="block w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-center font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition"
              >
                Start Free Trial
              </a>
            </div>
          </div>
        )}

        {/* Main Dashboard Content */}
        {selectedLicense && (
          <div className="mt-8 space-y-6">
            {/* Setup Prompt - shows until setup is complete */}
            <SetupPrompt
              licenseKey={selectedLicense.key}
              hasClaudeConfigured={setupStatus?.claudeConfigured}
              hasQBConnected={setupStatus?.qbConnected || companies.length > 0}
            />

            {/* Usage Stats (only for authenticated users) */}
            {(isSignedIn || legacyUser) && stats && (
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
            {(isSignedIn || legacyUser) && stats && stats.topTools.length > 0 && (
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
            {(isSignedIn || legacyUser) && licenses.length > 1 && (
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

            {/* Trial Banner (if trialing) */}
            {selectedLicense.status === "trialing" && selectedLicense.trial_ends_at && (
              <div className="rounded-2xl border border-blue-400/30 bg-blue-400/10 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">⏳</span>
                    <div>
                      <p className="font-medium text-white">
                        {(() => {
                          const daysLeft = Math.ceil(
                            (new Date(selectedLicense.trial_ends_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
                          );
                          if (daysLeft <= 0) return "Trial expired";
                          if (daysLeft === 1) return "1 day left in trial";
                          return `${daysLeft} days left in trial`;
                        })()}
                      </p>
                      <p className="text-sm text-blue-300">
                        Your trial ends on {new Date(selectedLicense.trial_ends_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={openBillingPortal}
                    disabled={portalLoading}
                    className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold hover:bg-blue-600 transition disabled:opacity-50"
                  >
                    {portalLoading ? "..." : "Upgrade Now"}
                  </button>
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

            {/* Billing & Subscription */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="text-lg font-semibold mb-4">Billing & Subscription</h2>
              <p className="text-sm text-gray-400 mb-4">
                Manage your subscription, update payment method, view invoices, or cancel anytime.
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={openBillingPortal}
                  disabled={portalLoading}
                  className="rounded-lg bg-white/10 px-4 py-2 text-sm font-medium hover:bg-white/20 transition disabled:opacity-50"
                >
                  {portalLoading ? "Opening..." : "Manage Subscription"}
                </button>
                <button
                  onClick={openBillingPortal}
                  disabled={portalLoading}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-400 hover:text-white hover:border-white/20 transition disabled:opacity-50"
                >
                  Cancel Subscription
                </button>
              </div>
              <p className="mt-3 text-xs text-gray-500">
                Cancel anytime from the billing portal. No questions asked.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
              <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <a
                  href={`/setup-wizard?key=${encodeURIComponent(selectedLicense.key)}`}
                  className="rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-600/10 border border-cyan-500/20 p-4 hover:border-cyan-500/40 transition"
                >
                  <p className="font-medium text-white">Setup Guide</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Install or reinstall extension
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
            {!isSignedIn && !legacyUser && (
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
