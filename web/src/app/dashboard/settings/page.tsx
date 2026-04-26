"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

interface UserProfile {
  email: string;
  tier: string;
  status: string;
  licenseKey: string;
  trialEndsAt: string | null;
  cardLastFour: string | null;
  cardBrand: string | null;
  nextBillingDate: string | null;
  billingAmountCents: number | null;
  qbConnections: { realmId: string; companyName: string | null }[];
}

export default function SettingsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const licenseKey = searchParams.get("key");

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);

  useEffect(() => {
    if (licenseKey) {
      fetchProfile();
    }
  }, [licenseKey]);

  const fetchProfile = async () => {
    try {
      const res = await fetch(`/api/user/profile?key=${licenseKey}`);
      const data = await res.json();
      if (res.ok) {
        setProfile(data.profile);
      }
    } catch (err) {
      console.error("Failed to fetch profile:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    setCancelLoading(true);
    try {
      const res = await fetch("/api/user/subscription/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey }),
      });

      if (res.ok) {
        setShowCancelModal(false);
        alert(
          "Your subscription has been cancelled. You'll retain access until the end of your billing period."
        );
        fetchProfile();
      } else {
        const data = await res.json();
        alert(data.error || "Failed to cancel subscription");
      }
    } catch {
      alert("Network error");
    } finally {
      setCancelLoading(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      const res = await fetch("/api/stripe/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ licenseKey }),
      });

      const data = await res.json();
      if (res.ok && data.url) {
        window.location.href = data.url;
      } else {
        alert("Failed to open billing portal");
      }
    } catch {
      alert("Network error");
    }
  };

  if (!licenseKey) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl text-white mb-2">No license key provided</h2>
          <p className="text-gray-400">
            Please access this page from your dashboard.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl text-white mb-2">Profile not found</h2>
          <Link href="/" className="text-cyan-400 hover:text-cyan-300">
            Go home
          </Link>
        </div>
      </div>
    );
  }

  const tierName =
    profile.tier === "solopreneur"
      ? "Solopreneur"
      : profile.tier === "business"
        ? "Business"
        : "Firm";

  return (
    <div className="min-h-screen bg-[#0a0e1a]">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#131a2e]">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href={`/dashboard?key=${licenseKey}`} className="text-gray-400 hover:text-white">
              ← Back to Dashboard
            </Link>
          </div>
          <span className="text-xl font-bold">
            <span className="text-cyan-400">Accounting</span>
            <span className="text-blue-500">QB</span>
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Account Settings</h1>
            <p className="text-gray-400 mt-1">
              Manage your subscription and account details
            </p>
          </div>

          {/* Account Info */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">
              Account Information
            </h3>
            <dl className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b border-white/5">
                <dt className="text-gray-400">Email</dt>
                <dd className="text-white">{profile.email}</dd>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-white/5">
                <dt className="text-gray-400">Plan</dt>
                <dd className="text-white">{tierName}</dd>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-white/5">
                <dt className="text-gray-400">Status</dt>
                <dd>
                  <StatusBadge status={profile.status} />
                </dd>
              </div>
              <div className="flex justify-between items-center py-2">
                <dt className="text-gray-400">License Key</dt>
                <dd className="text-gray-300 font-mono text-sm">
                  {profile.licenseKey.substring(0, 16)}...
                </dd>
              </div>
            </dl>
          </div>

          {/* Billing Info */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Billing</h3>
            <dl className="space-y-4">
              {profile.status === "trialing" && profile.trialEndsAt ? (
                <div className="flex justify-between items-center py-2 border-b border-white/5">
                  <dt className="text-gray-400">Trial Ends</dt>
                  <dd className="text-yellow-400">
                    {formatDate(profile.trialEndsAt)}
                  </dd>
                </div>
              ) : null}
              <div className="flex justify-between items-center py-2 border-b border-white/5">
                <dt className="text-gray-400">Payment Method</dt>
                <dd className="text-white">
                  {profile.cardLastFour
                    ? `${profile.cardBrand || "Card"} •••• ${profile.cardLastFour}`
                    : "Not on file"}
                </dd>
              </div>
              {profile.billingAmountCents && (
                <div className="flex justify-between items-center py-2 border-b border-white/5">
                  <dt className="text-gray-400">Monthly Amount</dt>
                  <dd className="text-white">
                    ${(profile.billingAmountCents / 100).toFixed(2)}/month
                  </dd>
                </div>
              )}
              {profile.nextBillingDate && (
                <div className="flex justify-between items-center py-2">
                  <dt className="text-gray-400">Next Billing Date</dt>
                  <dd className="text-white">
                    {formatDate(profile.nextBillingDate)}
                  </dd>
                </div>
              )}
            </dl>
            <div className="mt-6 flex gap-3">
              <button
                onClick={handleManageBilling}
                className="px-4 py-2 bg-cyan-500/10 text-cyan-400 rounded-lg hover:bg-cyan-500/20 transition"
              >
                Manage Billing
              </button>
              {profile.status !== "canceled" && (
                <button
                  onClick={() => setShowCancelModal(true)}
                  className="px-4 py-2 bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 transition"
                >
                  Cancel Subscription
                </button>
              )}
            </div>
          </div>

          {/* Connected Companies */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">
              Connected QuickBooks Companies
            </h3>
            {profile.qbConnections.length === 0 ? (
              <p className="text-gray-400">No companies connected</p>
            ) : (
              <ul className="space-y-3">
                {profile.qbConnections.map((conn) => (
                  <li
                    key={conn.realmId}
                    className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center">
                        <svg
                          className="w-4 h-4 text-green-400"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      </div>
                      <span className="text-white">
                        {conn.companyName || conn.realmId}
                      </span>
                    </div>
                    <span className="text-gray-500 text-sm font-mono">
                      {conn.realmId}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Support */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">
              Need Help?
            </h3>
            <p className="text-gray-400 mb-4">
              Our support team is here to help. Use the chat widget or email us
              directly.
            </p>
            <a
              href="mailto:support@vasperacapital.com"
              className="inline-block px-4 py-2 bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition"
            >
              Email Support
            </a>
          </div>
        </div>
      </main>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-white mb-4">
              Cancel Subscription?
            </h3>
            <p className="text-gray-400 mb-6">
              Are you sure you want to cancel your subscription? You'll retain
              access until the end of your current billing period.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowCancelModal(false)}
                className="flex-1 py-2 rounded-lg bg-white/5 text-gray-300 hover:bg-white/10"
              >
                Keep Subscription
              </button>
              <button
                onClick={handleCancelSubscription}
                disabled={cancelLoading}
                className="flex-1 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
              >
                {cancelLoading ? "Cancelling..." : "Yes, Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    trialing: { bg: "bg-blue-500/10", text: "text-blue-400", label: "Trial" },
    active: { bg: "bg-green-500/10", text: "text-green-400", label: "Active" },
    canceled: { bg: "bg-red-500/10", text: "text-red-400", label: "Canceled" },
    expired: { bg: "bg-gray-500/10", text: "text-gray-400", label: "Expired" },
  };

  const c = config[status] || config.expired;

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}
