"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";

interface Company {
  realmId: string;
  companyName: string;
}

interface LicenseInfo {
  key: string;
  tier: string;
  status: string;
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const keyParam = searchParams.get("key");

  const [licenseKey, setLicenseKey] = useState(keyParam || "");
  const [license, setLicense] = useState<LicenseInfo | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

  // Auto-fetch if key is in URL
  useEffect(() => {
    if (keyParam) {
      fetchLicenseInfo(keyParam);
    }
  }, [keyParam]);

  const fetchLicenseInfo = async (key: string) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/oauth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: key }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 404 && data.companies?.length === 0) {
          // No companies connected yet, but license is valid
          setLicense(data.license || { key, tier: "unknown", status: "active" });
          setCompanies([]);
        } else {
          setError(data.error || "Failed to fetch license info");
          setLicense(null);
          setCompanies([]);
        }
      } else {
        setLicense(data.license);
        setCompanies(data.companies || []);
      }
    } catch {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (licenseKey.trim()) {
      fetchLicenseInfo(licenseKey.trim());
    }
  };

  const copyKey = () => {
    if (license?.key) {
      navigator.clipboard.writeText(license.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const disconnectCompany = async (realmId: string) => {
    if (!license?.key) return;

    setDisconnecting(realmId);
    try {
      const res = await fetch("/api/oauth/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: license.key, realmId }),
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
    if (!license?.key) return;

    setPortalLoading(true);
    try {
      const res = await fetch("/api/stripe/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey: license.key }),
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

  const connectQBUrl = license?.key
    ? `/api/oauth/start?license_key=${encodeURIComponent(license.key)}`
    : "#";

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Nav */}
      <nav className="border-b border-white/5 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <a href="/" className="text-xl font-bold">
            <span className="text-white">Accounting</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">QB</span>
          </a>
          <a
            href="mailto:support@accountingqb.com"
            className="text-sm text-gray-400 hover:text-white transition"
          >
            Support
          </a>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-2 text-gray-400">
          Manage your AccountingQB license and connected QuickBooks companies.
        </p>

        {/* License Key Input */}
        {!license && (
          <form onSubmit={handleSubmit} className="mt-8">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Enter your license key
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={licenseKey}
                  onChange={(e) => setLicenseKey(e.target.value)}
                  placeholder="LK-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
                  className="flex-1 rounded-lg bg-black/40 border border-white/10 px-4 py-3 font-mono text-cyan-400 placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/50"
                />
                <button
                  type="submit"
                  disabled={loading || !licenseKey.trim()}
                  className="rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3 font-semibold transition hover:shadow-lg hover:shadow-cyan-500/20 disabled:opacity-50"
                >
                  {loading ? "Loading..." : "View Dashboard"}
                </button>
              </div>
              {error && (
                <p className="mt-3 text-sm text-red-400">{error}</p>
              )}
            </div>
          </form>
        )}

        {/* License Info */}
        {license && (
          <div className="mt-8 space-y-6">
            {/* License Card */}
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 uppercase tracking-wider">License Key</p>
                  <div className="mt-2 flex items-center gap-3">
                    <code className="rounded-lg bg-black/40 px-3 py-2 font-mono text-cyan-400">
                      {license.key}
                    </code>
                    <button
                      onClick={copyKey}
                      className="rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/10 transition"
                    >
                      {copied ? "✓" : "Copy"}
                    </button>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-400">Plan</p>
                  <p className="mt-1 font-semibold capitalize text-white">{license.tier}</p>
                  <span
                    className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${
                      license.status === "active"
                        ? "bg-green-500/20 text-green-400"
                        : license.status === "trialing"
                        ? "bg-blue-500/20 text-blue-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {license.status}
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

              {companies.length > 0 ? (
                <div className="space-y-3">
                  {companies.map((company) => (
                    <div
                      key={company.realmId}
                      className="flex items-center justify-between rounded-xl bg-white/[0.03] p-4"
                    >
                      <div>
                        <p className="font-medium text-white">{company.companyName}</p>
                        <p className="text-sm text-gray-500">ID: {company.realmId}</p>
                      </div>
                      <button
                        onClick={() => disconnectCompany(company.realmId)}
                        disabled={disconnecting === company.realmId}
                        className="rounded-lg border border-red-500/30 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition disabled:opacity-50"
                      >
                        {disconnecting === company.realmId ? "Disconnecting..." : "Disconnect"}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
                  <p className="text-gray-400">No QuickBooks companies connected yet.</p>
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
                Manage your subscription, update payment method, or view invoices.
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
                  <p className="text-sm text-gray-400 mt-1">Open in Claude Desktop</p>
                </a>
                <a
                  href="mailto:support@accountingqb.com"
                  className="rounded-xl bg-white/[0.03] border border-white/10 p-4 hover:border-white/20 transition"
                >
                  <p className="font-medium text-white">Contact Support</p>
                  <p className="text-sm text-gray-400 mt-1">Get help with your account</p>
                </a>
              </div>
            </div>

            {/* Change License */}
            <div className="text-center">
              <button
                onClick={() => {
                  setLicense(null);
                  setCompanies([]);
                  setLicenseKey("");
                }}
                className="text-sm text-gray-500 hover:text-white transition"
              >
                Use a different license key
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    }>
      <DashboardContent />
    </Suspense>
  );
}
