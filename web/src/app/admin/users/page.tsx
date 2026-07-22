"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

interface User {
  key: string;
  email: string;
  tier: string;
  status: string;
  created_at: string;
  trial_ends_at: string | null;
  qb_connected: boolean;
}

export default function AdminUsersPage() {
  const searchParams = useSearchParams();
  const initialFilter = searchParams.get("filter") || "all";
  const initialSearch = searchParams.get("search") || "";

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(initialFilter);
  const [search, setSearch] = useState(initialSearch);
  const [campaignLoading, setCampaignLoading] = useState(false);

  // Invite-a-tester state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteTier, setInviteTier] = useState("solopreneur");
  const [inviteDays, setInviteDays] = useState(14);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteResult, setInviteResult] = useState<string | null>(null);

  // Cohorts the campaign endpoint supports
  const campaignFilter = filter === "stuck" || filter === "canceled" ? filter : null;

  useEffect(() => {
    fetchUsers();
  }, [filter, search]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter && filter !== "all") params.set("filter", filter);
      if (search) params.set("search", search);

      const res = await fetch(`/api/admin/users?${params.toString()}`);
      const data = await res.json();

      if (res.ok) {
        setUsers(data.users || []);
      }
    } catch (err) {
      console.error("Failed to fetch users:", err);
    } finally {
      setLoading(false);
    }
  };

  const inviteFriend = async () => {
    setInviteResult(null);
    if (!inviteEmail.trim()) {
      setInviteResult("Enter an email first.");
      return;
    }
    setInviteLoading(true);
    try {
      const res = await fetch("/api/admin/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: inviteEmail.trim(),
          tier: inviteTier,
          trialDays: inviteDays,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setInviteResult(data.error || "Failed to send invite.");
      } else if (data.alreadyHasLicense) {
        setInviteResult(data.message);
      } else if (data.created) {
        setInviteResult(
          data.emailSent
            ? `✓ Invited ${inviteEmail.trim()} — ${inviteDays}-day ${inviteTier} trial emailed (key ${data.licenseKey}).`
            : `License created (${data.licenseKey}) but email failed — share the key manually.`
        );
        setInviteEmail("");
        fetchUsers();
      }
    } catch {
      setInviteResult("Network error sending invite.");
    } finally {
      setInviteLoading(false);
    }
  };

  const sendCampaign = async () => {
    if (!campaignFilter) return;

    setCampaignLoading(true);
    try {
      // Dry run first to get the recipient count
      const dryRes = await fetch("/api/admin/campaign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emailType: "reengagement",
          filter: campaignFilter,
          dryRun: true,
        }),
      });
      const dryData = await dryRes.json();

      if (!dryRes.ok) {
        alert(dryData.error || "Failed to preview campaign");
        return;
      }

      if (!dryData.count) {
        alert("No eligible recipients (users who already received this email are skipped).");
        return;
      }

      const confirmed = window.confirm(
        `Send the re-engagement email to ${dryData.count} user${dryData.count === 1 ? "" : "s"} in the "${campaignFilter}" cohort?`
      );
      if (!confirmed) return;

      const res = await fetch("/api/admin/campaign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emailType: "reengagement",
          filter: campaignFilter,
        }),
      });
      const data = await res.json();

      if (res.ok) {
        alert(`Re-engagement email scheduled for ${data.scheduled} user${data.scheduled === 1 ? "" : "s"}.`);
      } else {
        alert(data.error || "Failed to send campaign");
      }
    } catch (err) {
      console.error("Failed to send campaign:", err);
      alert("Failed to send campaign");
    } finally {
      setCampaignLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Users</h1>
          <p className="text-gray-400 mt-1">Manage all AccountingQB users</p>
        </div>
        {campaignFilter && (
          <button
            onClick={sendCampaign}
            disabled={campaignLoading}
            className="rounded-lg bg-cyan-500/10 border border-cyan-500/40 px-4 py-2 text-sm font-medium text-cyan-400 hover:bg-cyan-500/20 transition disabled:opacity-50"
          >
            {campaignLoading ? "Working..." : "Send re-engagement campaign"}
          </button>
        )}
      </div>

      {/* Invite a tester */}
      <div className="bg-[#131a2e] rounded-xl border border-cyan-500/20 p-5">
        <h2 className="text-sm font-semibold text-white">Invite a tester</h2>
        <p className="text-xs text-gray-400 mt-1">
          Issues a time-limited trial (no card) and emails them the key + setup
          steps. When the trial ends they drop to the free read-only tools and
          must subscribe for full access.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 mt-4">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="friend@example.com"
            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500/50 focus:outline-none"
          />
          <select
            value={inviteTier}
            onChange={(e) => setInviteTier(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
          >
            <option value="solopreneur">Solopreneur</option>
            <option value="business">Business</option>
            <option value="firm">Firm</option>
          </select>
          <select
            value={inviteDays}
            onChange={(e) => setInviteDays(Number(e.target.value))}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={21}>21 days</option>
            <option value={30}>30 days</option>
          </select>
          <button
            onClick={inviteFriend}
            disabled={inviteLoading}
            className="rounded-lg bg-cyan-500/10 border border-cyan-500/40 px-4 py-2 text-sm font-medium text-cyan-400 hover:bg-cyan-500/20 transition disabled:opacity-50"
          >
            {inviteLoading ? "Sending..." : "Send invite"}
          </button>
        </div>
        {inviteResult && (
          <p className="text-xs mt-3 text-gray-300">{inviteResult}</p>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          placeholder="Search by email or license key..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500/50 focus:outline-none"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:border-cyan-500/50 focus:outline-none"
        >
          <option value="all">All Users</option>
          <option value="trialing">Trialing</option>
          <option value="active">Active</option>
          <option value="canceled">Canceled</option>
          <option value="expired">Expired</option>
          <option value="stuck">Stuck (No QB)</option>
          <option value="trial_ending">Trial Ending Soon</option>
        </select>
      </div>

      {/* Users Table */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-400 border-b border-white/5">
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">License Key</th>
                <th className="px-6 py-3 font-medium">Tier</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">QB Connected</th>
                <th className="px-6 py-3 font-medium">Trial Ends</th>
                <th className="px-6 py-3 font-medium">Created</th>
                <th className="px-6 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-gray-400">
                    No users found
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr
                    key={user.key}
                    className="border-b border-white/5 hover:bg-white/5"
                  >
                    <td className="px-6 py-4 text-sm text-white">{user.email}</td>
                    <td className="px-6 py-4 text-sm text-gray-400 font-mono text-xs">
                      {user.key.substring(0, 12)}...
                    </td>
                    <td className="px-6 py-4">
                      <TierBadge tier={user.tier} />
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={user.status} />
                    </td>
                    <td className="px-6 py-4">
                      {user.qb_connected ? (
                        <span className="text-green-400">Yes</span>
                      ) : (
                        <span className="text-yellow-400">No</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {user.trial_ends_at ? formatDate(user.trial_ends_at) : "—"}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {formatDate(user.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/admin/users/${user.key}`}
                        className="text-sm text-cyan-400 hover:text-cyan-300"
                      >
                        Manage
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    solopreneur: "bg-cyan-500/10 text-cyan-400",
    business: "bg-blue-500/10 text-blue-400",
    firm: "bg-purple-500/10 text-purple-400",
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[tier] || colors.solopreneur}`}>
      {tier}
    </span>
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
