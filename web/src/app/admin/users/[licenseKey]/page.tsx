"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface UserDetail {
  key: string;
  email: string;
  tier: string;
  status: string;
  created_at: string;
  trial_ends_at: string | null;
  card_last_four: string | null;
  card_brand: string | null;
  next_billing_date: string | null;
  billing_amount_cents: number | null;
  milestones: { milestone: string; completed_at: string; metadata: Record<string, unknown> }[];
  qb_connections: { realm_id: string; company_name: string | null; created_at: string }[];
  emails: { id: string; email_type: string; scheduled_for: string; sent_at: string | null; cancelled: boolean }[];
  trial_extensions: { extension_days: number; extended_by: string; created_at: string; reason: string | null }[];
}

export default function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ licenseKey: string }>;
}) {
  const { licenseKey } = use(params);
  const router = useRouter();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showExtendModal, setShowExtendModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);

  useEffect(() => {
    fetchUser();
  }, [licenseKey]);

  const fetchUser = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/users/${licenseKey}`);
      const data = await res.json();
      if (res.ok) {
        setUser(data.user);
      }
    } catch (err) {
      console.error("Failed to fetch user:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleExtendTrial = async (days: number, reason: string) => {
    setActionLoading(true);
    try {
      const res = await fetch(`/api/admin/users/${licenseKey}/extend-trial`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days, reason }),
      });

      if (res.ok) {
        setShowExtendModal(false);
        fetchUser();
      } else {
        const data = await res.json();
        alert(data.error || "Failed to extend trial");
      }
    } catch {
      alert("Network error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendEmail = async (emailType: string) => {
    setActionLoading(true);
    try {
      const res = await fetch(`/api/admin/users/${licenseKey}/send-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emailType }),
      });

      if (res.ok) {
        setShowEmailModal(false);
        fetchUser();
        alert("Email scheduled successfully");
      } else {
        const data = await res.json();
        alert(data.error || "Failed to send email");
      }
    } catch {
      alert("Network error");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl text-white mb-2">User not found</h2>
        <Link href="/admin/users" className="text-cyan-400 hover:text-cyan-300">
          Back to users
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/admin/users"
            className="text-sm text-gray-400 hover:text-white mb-2 inline-block"
          >
            ← Back to users
          </Link>
          <h1 className="text-2xl font-bold text-white">{user.email}</h1>
          <p className="text-gray-400 font-mono text-sm mt-1">{user.key}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowExtendModal(true)}
            className="px-4 py-2 bg-cyan-500/10 text-cyan-400 rounded-lg hover:bg-cyan-500/20 transition"
          >
            Extend Trial
          </button>
          <button
            onClick={() => setShowEmailModal(true)}
            className="px-4 py-2 bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition"
          >
            Send Email
          </button>
        </div>
      </div>

      {/* User Info Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Account Info */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Account Info</h3>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-400">Tier</dt>
              <dd className="text-white capitalize">{user.tier}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Status</dt>
              <dd>
                <StatusBadge status={user.status} />
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Created</dt>
              <dd className="text-white">{formatDate(user.created_at)}</dd>
            </div>
            {user.trial_ends_at && (
              <div className="flex justify-between">
                <dt className="text-gray-400">Trial Ends</dt>
                <dd className="text-white">{formatDate(user.trial_ends_at)}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Billing Info */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Billing Info</h3>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-400">Card</dt>
              <dd className="text-white">
                {user.card_last_four
                  ? `${user.card_brand || "Card"} •••• ${user.card_last_four}`
                  : "Not on file"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Monthly Amount</dt>
              <dd className="text-white">
                {user.billing_amount_cents
                  ? `$${(user.billing_amount_cents / 100).toFixed(2)}`
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Next Billing</dt>
              <dd className="text-white">
                {user.next_billing_date
                  ? formatDate(user.next_billing_date)
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Milestones Timeline */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Milestones</h3>
        {user.milestones.length === 0 ? (
          <p className="text-gray-400">No milestones yet</p>
        ) : (
          <div className="space-y-3">
            {user.milestones.map((m, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <div className="flex-1">
                  <p className="text-white capitalize">
                    {m.milestone.replace(/_/g, " ")}
                  </p>
                  <p className="text-gray-400 text-sm">
                    {formatDateTime(m.completed_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* QB Connections */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          QuickBooks Connections
        </h3>
        {user.qb_connections.length === 0 ? (
          <p className="text-gray-400">No QuickBooks connections</p>
        ) : (
          <div className="space-y-3">
            {user.qb_connections.map((c, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
              >
                <div>
                  <p className="text-white">{c.company_name || c.realm_id}</p>
                  <p className="text-gray-400 text-sm font-mono">{c.realm_id}</p>
                </div>
                <p className="text-gray-400 text-sm">
                  {formatDate(c.created_at)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Trial Extensions */}
      {user.trial_extensions.length > 0 && (
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            Trial Extensions
          </h3>
          <div className="space-y-3">
            {user.trial_extensions.map((ext, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
              >
                <div>
                  <p className="text-white">+{ext.extension_days} days</p>
                  {ext.reason && (
                    <p className="text-gray-400 text-sm">{ext.reason}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-gray-400 text-sm">{ext.extended_by}</p>
                  <p className="text-gray-500 text-xs">
                    {formatDateTime(ext.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Email History */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Email History</h3>
        {user.emails.length === 0 ? (
          <p className="text-gray-400">No emails scheduled or sent</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-400 border-b border-white/5">
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Scheduled</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {user.emails.map((e) => (
                  <tr key={e.id} className="border-b border-white/5">
                    <td className="py-2 text-white capitalize">
                      {e.email_type.replace(/_/g, " ")}
                    </td>
                    <td className="py-2 text-gray-400 text-sm">
                      {formatDateTime(e.scheduled_for)}
                    </td>
                    <td className="py-2">
                      {e.cancelled ? (
                        <span className="text-gray-500">Cancelled</span>
                      ) : e.sent_at ? (
                        <span className="text-green-400">Sent</span>
                      ) : (
                        <span className="text-yellow-400">Pending</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Extend Trial Modal */}
      {showExtendModal && (
        <ExtendTrialModal
          onClose={() => setShowExtendModal(false)}
          onSubmit={handleExtendTrial}
          loading={actionLoading}
        />
      )}

      {/* Send Email Modal */}
      {showEmailModal && (
        <SendEmailModal
          onClose={() => setShowEmailModal(false)}
          onSubmit={handleSendEmail}
          loading={actionLoading}
        />
      )}
    </div>
  );
}

function ExtendTrialModal({
  onClose,
  onSubmit,
  loading,
}: {
  onClose: () => void;
  onSubmit: (days: number, reason: string) => void;
  loading: boolean;
}) {
  const [days, setDays] = useState(7);
  const [reason, setReason] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-white mb-4">Extend Trial</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Extension Period
            </label>
            <div className="flex gap-2">
              {[7, 14, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`flex-1 py-2 rounded-lg text-sm ${
                    days === d
                      ? "bg-cyan-500 text-white"
                      : "bg-white/5 text-gray-300 hover:bg-white/10"
                  }`}
                >
                  {d} days
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Reason (optional)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Setup issues, onboarding call"
              className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500/50 focus:outline-none"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded-lg bg-white/5 text-gray-300 hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              onClick={() => onSubmit(days, reason)}
              disabled={loading}
              className="flex-1 py-2 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 disabled:opacity-50"
            >
              {loading ? "Extending..." : "Extend Trial"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SendEmailModal({
  onClose,
  onSubmit,
  loading,
}: {
  onClose: () => void;
  onSubmit: (emailType: string) => void;
  loading: boolean;
}) {
  const [emailType, setEmailType] = useState("day_3_checkin");

  const emailTypes = [
    { value: "welcome", label: "Welcome Email" },
    { value: "day_3_checkin", label: "Day 3 Check-in" },
    { value: "trial_warning_4day", label: "Trial Warning (4 days)" },
    { value: "trial_warning_1day", label: "Trial Warning (1 day)" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-white mb-4">Send Email</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Email Type
            </label>
            <select
              value={emailType}
              onChange={(e) => setEmailType(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
            >
              {emailTypes.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded-lg bg-white/5 text-gray-300 hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              onClick={() => onSubmit(emailType)}
              disabled={loading}
              className="flex-1 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
            >
              {loading ? "Sending..." : "Send Email"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    trialing: "bg-blue-500/10 text-blue-400",
    active: "bg-green-500/10 text-green-400",
    canceled: "bg-red-500/10 text-red-400",
    expired: "bg-gray-500/10 text-gray-400",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.trialing}`}>
      {status}
    </span>
  );
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateTime(date: string): string {
  return new Date(date).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
