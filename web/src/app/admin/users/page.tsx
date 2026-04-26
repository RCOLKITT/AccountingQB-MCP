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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Users</h1>
          <p className="text-gray-400 mt-1">Manage all AccountingQB users</p>
        </div>
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
