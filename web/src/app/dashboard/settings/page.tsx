"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
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

function SettingsContent() {
  const searchParams = useSearchParams();
  const licenseKey = searchParams.get("key");

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [showRotateModal, setShowRotateModal] = useState(false);
  const [rotateLoading, setRotateLoading] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);

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
          "Your subscription has been cancelled. You'll retain access until the end of your billing period.",
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

  const handleRotateKey = async () => {
    setRotateLoading(true);
    try {
      const res = await fetch("/api/license/rotate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          license_key: licenseKey,
          reason: "user_requested",
        }),
      });

      const data = await res.json();
      if (res.ok && data.new_key) {
        setNewKey(data.new_key);
      } else {
        alert(data.error || "Failed to rotate key");
        setShowRotateModal(false);
      }
    } catch {
      alert("Network error");
      setShowRotateModal(false);
    } finally {
      setRotateLoading(false);
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
            <Link
              href={`/dashboard?key=${licenseKey}`}
              className="text-gray-400 hover:text-white"
            >
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

          {/* Security */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Security</h3>
            <p className="text-gray-400 mb-4">
              If you believe your license key has been compromised, you can
              rotate it to generate a new one. Your old key will be immediately
              invalidated.
            </p>
            <div className="flex items-center justify-between py-3 border-t border-white/5">
              <div>
                <div className="text-white font-medium">Rotate License Key</div>
                <div className="text-gray-500 text-sm">
                  Generate a new key and invalidate the current one
                </div>
              </div>
              <button
                onClick={() => setShowRotateModal(true)}
                className="px-4 py-2 bg-yellow-500/10 text-yellow-400 rounded-lg hover:bg-yellow-500/20 transition"
              >
                Rotate Key
              </button>
            </div>
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

      {/* Rotate Key Modal */}
      {showRotateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 w-full max-w-md mx-4">
            {newKey ? (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-green-400"
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
                  <h3 className="text-lg font-semibold text-white">
                    Key Rotated Successfully
                  </h3>
                </div>
                <p className="text-gray-400 mb-4">
                  Your new license key is below. Copy it and update your local
                  config:
                </p>
                <div className="bg-black/30 rounded-lg p-4 mb-4">
                  <code className="text-cyan-400 font-mono text-sm break-all select-all">
                    {newKey}
                  </code>
                </div>
                <p className="text-yellow-400 text-sm mb-6">
                  Run{" "}
                  <code className="bg-yellow-500/10 px-1 rounded">
                    accountingqb setup
                  </code>{" "}
                  to update your local configuration with the new key.
                </p>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(newKey);
                    window.location.href = `/dashboard/settings?key=${newKey}`;
                  }}
                  className="w-full py-2 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600"
                >
                  Copy Key & Continue
                </button>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-yellow-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-white">
                    Rotate License Key?
                  </h3>
                </div>
                <p className="text-gray-400 mb-6">
                  This will generate a new license key and immediately
                  invalidate your current one. You'll need to update your local
                  configuration with the new key.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowRotateModal(false)}
                    className="flex-1 py-2 rounded-lg bg-white/5 text-gray-300 hover:bg-white/10"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleRotateKey}
                    disabled={rotateLoading}
                    className="flex-1 py-2 rounded-lg bg-yellow-500 text-black font-medium hover:bg-yellow-400 disabled:opacity-50"
                  >
                    {rotateLoading ? "Rotating..." : "Rotate Key"}
                  </button>
                </div>
              </>
            )}
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

export default function SettingsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#0a0e1a] flex items-center justify-center">
          <div className="text-gray-400">Loading...</div>
        </div>
      }
    >
      <SettingsContent />
    </Suspense>
  );
}
