"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";

interface EmailSchedule {
  id: string;
  license_key: string;
  email_type: string;
  scheduled_for: string;
  sent_at: string | null;
  cancelled: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface SupportConversation {
  id: string;
  license_key: string | null;
  user_email: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

type Tab = "scheduled" | "sent" | "escalations";

export default function AdminEmailsPage() {
  const searchParams = useSearchParams();
  const initialFilter = searchParams.get("filter");
  const initialTab: Tab = initialFilter === "escalated" ? "escalations" : "scheduled";

  const [tab, setTab] = useState<Tab>(initialTab);
  const [emails, setEmails] = useState<EmailSchedule[]>([]);
  const [escalations, setEscalations] = useState<SupportConversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tab === "escalations") {
      fetchEscalations();
    } else {
      fetchEmails();
    }
  }, [tab]);

  const fetchEmails = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("type", tab);

      const res = await fetch(`/api/admin/emails?${params.toString()}`);
      const data = await res.json();

      if (res.ok) {
        setEmails(data.emails || []);
      }
    } catch (err) {
      console.error("Failed to fetch emails:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEscalations = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/emails?type=escalations");
      const data = await res.json();

      if (res.ok) {
        setEscalations(data.escalations || []);
      }
    } catch (err) {
      console.error("Failed to fetch escalations:", err);
    } finally {
      setLoading(false);
    }
  };

  const cancelEmail = async (id: string) => {
    if (!confirm("Cancel this scheduled email?")) return;

    try {
      const res = await fetch(`/api/admin/emails/${id}/cancel`, {
        method: "POST",
      });

      if (res.ok) {
        setEmails(emails.map((e) => (e.id === id ? { ...e, cancelled: true } : e)));
      }
    } catch (err) {
      console.error("Failed to cancel email:", err);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Emails</h1>
        <p className="text-gray-400 mt-1">View scheduled emails and support escalations</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 pb-2">
        <TabButton
          label="Scheduled"
          active={tab === "scheduled"}
          onClick={() => setTab("scheduled")}
        />
        <TabButton
          label="Sent"
          active={tab === "sent"}
          onClick={() => setTab("sent")}
        />
        <TabButton
          label="Escalations"
          active={tab === "escalations"}
          onClick={() => setTab("escalations")}
          badge={escalations.length > 0 ? escalations.length : undefined}
        />
      </div>

      {/* Content */}
      {tab === "escalations" ? (
        <EscalationsTable
          escalations={escalations}
          loading={loading}
        />
      ) : (
        <EmailsTable
          emails={emails}
          loading={loading}
          showSentAt={tab === "sent"}
          onCancel={tab === "scheduled" ? cancelEmail : undefined}
        />
      )}
    </div>
  );
}

function TabButton({
  label,
  active,
  onClick,
  badge,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition flex items-center gap-2 ${
        active
          ? "bg-cyan-500/20 text-cyan-400"
          : "text-gray-400 hover:text-white hover:bg-white/5"
      }`}
    >
      {label}
      {badge !== undefined && (
        <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
          {badge}
        </span>
      )}
    </button>
  );
}

function EmailsTable({
  emails,
  loading,
  showSentAt,
  onCancel,
}: {
  emails: EmailSchedule[];
  loading: boolean;
  showSentAt: boolean;
  onCancel?: (id: string) => void;
}) {
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-sm text-gray-400 border-b border-white/5">
              <th className="px-6 py-3 font-medium">Email Type</th>
              <th className="px-6 py-3 font-medium">Recipient</th>
              <th className="px-6 py-3 font-medium">Scheduled For</th>
              {showSentAt && <th className="px-6 py-3 font-medium">Sent At</th>}
              <th className="px-6 py-3 font-medium">Status</th>
              {onCancel && <th className="px-6 py-3 font-medium"></th>}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : emails.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-400">
                  No emails found
                </td>
              </tr>
            ) : (
              emails.map((email) => (
                <tr
                  key={email.id}
                  className="border-b border-white/5 hover:bg-white/5"
                >
                  <td className="px-6 py-4">
                    <EmailTypeBadge type={email.email_type} />
                  </td>
                  <td className="px-6 py-4 text-sm text-white">
                    {(email.metadata?.email as string) || email.license_key.substring(0, 12) + "..."}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {formatDateTime(email.scheduled_for)}
                  </td>
                  {showSentAt && (
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {email.sent_at ? formatDateTime(email.sent_at) : "—"}
                    </td>
                  )}
                  <td className="px-6 py-4">
                    <StatusBadge
                      status={
                        email.cancelled
                          ? "cancelled"
                          : email.sent_at
                          ? "sent"
                          : "pending"
                      }
                    />
                  </td>
                  {onCancel && (
                    <td className="px-6 py-4">
                      {!email.cancelled && !email.sent_at && (
                        <button
                          onClick={() => onCancel(email.id)}
                          className="text-sm text-red-400 hover:text-red-300"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EscalationsTable({
  escalations,
  loading,
}: {
  escalations: SupportConversation[];
  loading: boolean;
}) {
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-sm text-gray-400 border-b border-white/5">
              <th className="px-6 py-3 font-medium">User</th>
              <th className="px-6 py-3 font-medium">License</th>
              <th className="px-6 py-3 font-medium">Messages</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Created</th>
              <th className="px-6 py-3 font-medium">Last Update</th>
              <th className="px-6 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : escalations.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-gray-400">
                  No escalations found
                </td>
              </tr>
            ) : (
              escalations.map((esc) => (
                <tr
                  key={esc.id}
                  className="border-b border-white/5 hover:bg-white/5"
                >
                  <td className="px-6 py-4 text-sm text-white">
                    {esc.user_email || "Anonymous"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400 font-mono text-xs">
                    {esc.license_key ? esc.license_key.substring(0, 12) + "..." : "—"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {esc.message_count}
                  </td>
                  <td className="px-6 py-4">
                    <EscalationStatusBadge status={esc.status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {formatDateTime(esc.created_at)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {formatDateTime(esc.updated_at)}
                  </td>
                  <td className="px-6 py-4">
                    <a
                      href={`/admin/emails/conversation/${esc.id}`}
                      className="text-sm text-cyan-400 hover:text-cyan-300"
                    >
                      View
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EmailTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    welcome: "bg-green-500/10 text-green-400",
    qb_connected: "bg-cyan-500/10 text-cyan-400",
    day_3_checkin: "bg-blue-500/10 text-blue-400",
    trial_warning_4day: "bg-yellow-500/10 text-yellow-400",
    trial_warning_1day: "bg-orange-500/10 text-orange-400",
    trial_expired: "bg-red-500/10 text-red-400",
    payment_failed: "bg-red-500/10 text-red-400",
    subscription_renewed: "bg-green-500/10 text-green-400",
  };

  const labels: Record<string, string> = {
    welcome: "Welcome",
    qb_connected: "QB Connected",
    day_3_checkin: "Day 3 Check-in",
    trial_warning_4day: "Trial Warning (4 day)",
    trial_warning_1day: "Trial Warning (1 day)",
    trial_expired: "Trial Expired",
    payment_failed: "Payment Failed",
    subscription_renewed: "Subscription Renewed",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[type] || "bg-gray-500/10 text-gray-400"}`}>
      {labels[type] || type}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-blue-500/10 text-blue-400",
    sent: "bg-green-500/10 text-green-400",
    cancelled: "bg-gray-500/10 text-gray-400",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.pending}`}>
      {status}
    </span>
  );
}

function EscalationStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    escalated: "bg-red-500/10 text-red-400",
    resolved: "bg-green-500/10 text-green-400",
    open: "bg-yellow-500/10 text-yellow-400",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || "bg-gray-500/10 text-gray-400"}`}>
      {status}
    </span>
  );
}

function formatDateTime(date: string): string {
  return new Date(date).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
