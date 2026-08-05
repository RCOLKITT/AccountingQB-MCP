import { getSupabase } from "@/lib/supabase";
import { unstable_cache } from "next/cache";
import Link from "next/link";

// Admin dashboards don't need to be real-time to the second — cache the heavy
// aggregate reads for 60s so clicking around the admin is instant instead of
// re-running every query on every navigation.
const ADMIN_CACHE_SECONDS = 60;

interface Stats {
  totalUsers: number;
  activeTrials: number;
  activeSubscriptions: number;
  canceledSubscriptions: number;
  stuckUsers: number;
  trialsEndingThisWeek: number;
  recentEscalations: number;
  support: {
    total: number;
    selfResolvedPct: number;
    escalatedPct: number;
    topTopics: { topic: string; count: number }[];
  };
}

async function getStats(): Promise<Stats> {
  const supabase = getSupabase();
  const now = new Date();
  const oneWeekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);

  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const lic = () => supabase.from("licenses").select("*", { count: "exact", head: true }).eq("is_test", false);

  // Every headline metric is an independent query — run them in ONE parallel
  // batch instead of a dozen sequential round-trips. Exclude test/demo accounts
  // (is_test) so these match the Revenue/Funnel pages.
  const [
    { count: totalUsers },
    { count: activeTrials },
    // "Paid" = an actually-billing subscription (active AND a Stripe sub) — matches Revenue.
    { count: activeSubscriptions },
    { count: canceledSubscriptions },
    { count: trialsEndingThisWeek },
    { data: oldTrials },
    { count: recentEscalations },
    { data: supportRows },
  ] = await Promise.all([
    lic(),
    lic().eq("status", "trialing"),
    lic().eq("status", "active").not("stripe_subscription_id", "is", null),
    lic().in("status", ["canceled", "expired"]),
    lic().eq("status", "trialing")
      .lte("trial_ends_at", oneWeekFromNow.toISOString())
      .gte("trial_ends_at", now.toISOString()),
    // Stuck-user candidates: trialing, signed up > 3 days ago.
    supabase.from("licenses").select("key").eq("is_test", false)
      .eq("status", "trialing").lt("created_at", threeDaysAgo.toISOString()),
    supabase.from("support_conversations").select("*", { count: "exact", head: true })
      .eq("status", "escalated").gte("updated_at", sevenDaysAgo.toISOString()),
    // Support health (last 30 days): self-resolution + escalation + top topics.
    supabase.from("support_analytics")
      .select("topic, resolved_self, escalated, created_at")
      .gte("created_at", thirtyDaysAgo.toISOString()).limit(50000),
  ]);

  // Stuck users: of the old trials, how many have NOT hit qb_connected. ONE query
  // over all candidate keys (was N+1: a query per trial), then a set difference.
  let stuckUsers = 0;
  const oldKeys = (oldTrials || []).map((l) => l.key as string);
  if (oldKeys.length) {
    const { data: connectedRows } = await supabase
      .from("user_milestones")
      .select("license_key")
      .eq("milestone", "qb_connected")
      .in("license_key", oldKeys);
    const connected = new Set((connectedRows || []).map((m) => m.license_key));
    stuckUsers = oldKeys.filter((k) => !connected.has(k)).length;
  }
  const sup = (supportRows || []) as {
    topic: string;
    resolved_self: boolean;
    escalated: boolean;
  }[];
  const supTotal = sup.length;
  const supSelf = sup.filter((r) => r.resolved_self && !r.escalated).length;
  const supEsc = sup.filter((r) => r.escalated).length;
  const topicCounts: Record<string, number> = {};
  for (const r of sup) topicCounts[r.topic] = (topicCounts[r.topic] || 0) + 1;
  const topTopics = Object.entries(topicCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([topic, count]) => ({ topic, count }));

  return {
    totalUsers: totalUsers || 0,
    activeTrials: activeTrials || 0,
    activeSubscriptions: activeSubscriptions || 0,
    canceledSubscriptions: canceledSubscriptions || 0,
    stuckUsers,
    trialsEndingThisWeek: trialsEndingThisWeek || 0,
    recentEscalations: recentEscalations || 0,
    support: {
      total: supTotal,
      selfResolvedPct: supTotal ? Math.round((supSelf / supTotal) * 100) : 0,
      escalatedPct: supTotal ? Math.round((supEsc / supTotal) * 100) : 0,
      topTopics,
    },
  };
}

interface RecentUser {
  key: string;
  email: string;
  tier: string;
  status: string;
  created_at: string;
  trial_ends_at: string | null;
}

async function getRecentUsers(): Promise<RecentUser[]> {
  const supabase = getSupabase();

  const { data } = await supabase
    .from("licenses")
    .select("key, email, tier, status, created_at, trial_ends_at")
    .eq("is_test", false)
    .order("created_at", { ascending: false })
    .limit(10);

  return (data || []) as RecentUser[];
}

const getDashboardData = unstable_cache(
  async () => Promise.all([getStats(), getRecentUsers()]),
  ["admin-dashboard"],
  { revalidate: ADMIN_CACHE_SECONDS }
);

export default async function AdminDashboard() {
  const [stats, recentUsers] = await getDashboardData();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your AccountingQB users</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Users"
          value={stats.totalUsers}
          color="cyan"
        />
        <StatCard
          label="Active Trials"
          value={stats.activeTrials}
          color="blue"
        />
        <StatCard
          label="Paid Subscriptions"
          value={stats.activeSubscriptions}
          color="green"
        />
        <StatCard
          label="Canceled"
          value={stats.canceledSubscriptions}
          color="gray"
        />
      </div>

      {/* Alert Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AlertCard
          label="Stuck Users"
          value={stats.stuckUsers}
          description="Signed up > 3 days, no QB connected"
          href="/admin/users?filter=stuck"
          color="yellow"
        />
        <AlertCard
          label="Trials Ending This Week"
          value={stats.trialsEndingThisWeek}
          description="May need outreach"
          href="/admin/users?filter=trial_ending"
          color="orange"
        />
        <AlertCard
          label="Support Escalations"
          value={stats.recentEscalations}
          description="Last 7 days"
          href="/admin/emails?filter=escalated"
          color="red"
        />
      </div>

      {/* Support health (30d) */}
      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Support health · 30d</h2>
          <span className="text-xs text-gray-500">{stats.support.total} contacts</span>
        </div>
        {stats.support.total === 0 ? (
          <p className="text-sm text-gray-500">No support activity in the last 30 days.</p>
        ) : (
          <div className="flex flex-wrap items-start gap-8">
            <div>
              <p className="text-2xl font-bold text-emerald-400">
                {stats.support.selfResolvedPct}%
              </p>
              <p className="text-xs text-gray-400">self-resolved</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-300">
                {stats.support.escalatedPct}%
              </p>
              <p className="text-xs text-gray-400">escalated to human</p>
            </div>
            {stats.support.topTopics.length > 0 && (
              <div className="min-w-[12rem]">
                <p className="mb-1 text-xs text-gray-400">Top topics</p>
                <div className="flex flex-wrap gap-2">
                  {stats.support.topTopics.map((t) => (
                    <span
                      key={t.topic}
                      className="rounded bg-white/5 px-2 py-0.5 text-xs text-gray-300"
                    >
                      {t.topic} · {t.count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent Users */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Recent Signups</h2>
          <Link
            href="/admin/users"
            className="text-sm text-cyan-400 hover:text-cyan-300"
          >
            View all →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-400 border-b border-white/5">
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">Tier</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Created</th>
                <th className="px-6 py-3 font-medium">Trial Ends</th>
                <th className="px-6 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {recentUsers.map((user) => (
                <tr
                  key={user.key}
                  className="border-b border-white/5 hover:bg-white/5"
                >
                  <td className="px-6 py-4 text-sm text-white">{user.email}</td>
                  <td className="px-6 py-4">
                    <TierBadge tier={user.tier} />
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={user.status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {user.trial_ends_at ? formatDate(user.trial_ends_at) : "—"}
                  </td>
                  <td className="px-6 py-4">
                    <Link
                      href={`/admin/users/${user.key}`}
                      className="text-sm text-cyan-400 hover:text-cyan-300"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    cyan: "text-cyan-400",
    blue: "text-blue-400",
    green: "text-green-400",
    gray: "text-gray-400",
  };

  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
      <p className="text-sm text-gray-400">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${colorClasses[color]}`}>
        {value}
      </p>
    </div>
  );
}

function AlertCard({
  label,
  value,
  description,
  href,
  color,
}: {
  label: string;
  value: number;
  description: string;
  href: string;
  color: string;
}) {
  const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
    yellow: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/20" },
    orange: { bg: "bg-orange-500/10", text: "text-orange-400", border: "border-orange-500/20" },
    red: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/20" },
  };

  const c = colorClasses[color];

  return (
    <Link
      href={href}
      className={`${c.bg} rounded-xl border ${c.border} p-6 hover:border-white/20 transition block`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-sm ${c.text}`}>{label}</p>
          <p className={`text-2xl font-bold mt-1 ${c.text}`}>{value}</p>
          <p className="text-xs text-gray-500 mt-1">{description}</p>
        </div>
        <span className={`text-2xl ${c.text}`}>→</span>
      </div>
    </Link>
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
