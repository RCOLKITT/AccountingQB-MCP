import Link from "next/link";
import {
  getUsageAnalytics,
  normalizeDays,
  type UsageAnalytics,
  type ToolStat,
} from "@/lib/usage-analytics";
import { getEngagement, type Engagement } from "@/lib/engagement";
import { unstable_cache } from "next/cache";

export const dynamic = "force-dynamic";

// Cache the usage + engagement aggregates per range for 60s.
const getUsage = unstable_cache(
  (days: number) => Promise.all([getUsageAnalytics(days), getEngagement()]),
  ["admin-usage"],
  { revalidate: 60 }
);

const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
];

export default async function UsagePage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const sp = await searchParams;
  const days = normalizeDays(sp.days);
  const [u, eng] = await getUsage(days);
  return <Dashboard u={u} eng={eng} days={days} />;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function Dashboard({ u, eng, days }: { u: UsageAnalytics; eng: Engagement; days: number }) {
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Product Usage</h1>
          <p className="text-gray-400 mt-1 text-sm">
            Which MCP tools real customers actually run (test &amp; demo licenses
            filtered out). Populated by the connector after each tool call.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
          {RANGES.map((r) => (
            <Link
              key={r.days}
              href={`/admin/usage?days=${r.days}`}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                days === r.days
                  ? "bg-cyan-500/20 text-cyan-300"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {r.label}
            </Link>
          ))}
        </div>
      </div>

      {/* Engagement health — fixed 1/7/30-day windows, independent of the range above */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Engagement health</h2>
          <span className="text-xs text-gray-500">active = ran a tool</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <BigMetric label="DAU" value={eng.dau} accent sub="active today" />
          <BigMetric label="WAU" value={eng.wau} sub="last 7 days" />
          <BigMetric label="MAU" value={eng.mau} sub="last 30 days" />
          <BigMetric label="Stickiness" value={`${Math.round(eng.stickiness)}%`} sub="DAU / MAU" />
        </div>
        {eng.atRiskCount > 0 && (
          <div className="mt-6">
            <div className="mb-2 flex items-center gap-2 text-sm">
              <span className="font-semibold text-amber-300">
                ⚠️ {eng.atRiskCount} at-risk account{eng.atRiskCount === 1 ? "" : "s"}
              </span>
              <span className="text-gray-500">
                — active in the prior 30d, silent the last 7 days (churn risk)
              </span>
            </div>
            <div className="overflow-hidden rounded-lg border border-white/5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-xs text-gray-400">
                    <th className="px-4 py-2 font-medium">Account</th>
                    <th className="px-4 py-2 font-medium">Tier</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Prior calls</th>
                    <th className="px-4 py-2 font-medium">Last active</th>
                  </tr>
                </thead>
                <tbody>
                  {eng.atRisk.map((a) => (
                    <tr key={a.license_key} className="border-b border-white/5">
                      <td className="px-4 py-2 text-white">
                        <Link
                          href={`/admin/users/${a.license_key}`}
                          className="hover:text-cyan-400"
                        >
                          {a.email}
                        </Link>
                      </td>
                      <td className="px-4 py-2 capitalize text-gray-300">{a.tier}</td>
                      <td className="px-4 py-2 capitalize text-gray-400">{a.status}</td>
                      <td className="px-4 py-2 text-gray-300">{a.priorCalls}</td>
                      <td className="px-4 py-2 text-gray-400">{fmtDate(a.lastActive)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {u.empty ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-sm text-amber-200/90">
          No tool usage recorded in the last {days} days for real customers yet.
          Once a customer runs a tool through the connector, per-tool activity
          appears here. (Connection/refresh activity is on each{" "}
          <Link href="/admin/users" className="underline">user&rsquo;s page</Link>.)
        </div>
      ) : (
        <>
          {/* Headline metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <BigMetric label={`Tool calls · ${days}d`} value={u.totalCalls} accent />
            <BigMetric label="Active accounts" value={u.activeAccounts} />
            <BigMetric label="Hours saved" value={u.hoursSaved} />
            <BigMetric label="Calls / account" value={u.avgCallsPerAccount} />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Top tools */}
            <ToolPanel title={`Top tools · ${days}d`} tools={u.topTools} />

            {/* Usage by tier */}
            <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
              <h2 className="text-sm font-semibold text-white mb-4">
                Usage by tier · {days}d
              </h2>
              {u.byTier.length === 0 ? (
                <p className="text-sm text-gray-500">No usage yet.</p>
              ) : (
                <div className="space-y-3">
                  {u.byTier.map((t) => (
                    <div key={t.tier} className="flex items-center justify-between text-sm">
                      <span className="text-gray-300 capitalize">{t.tier}</span>
                      <span className="text-gray-400">
                        <span className="text-cyan-400 font-semibold">{t.calls}</span> calls ·{" "}
                        {t.activeAccounts} {t.activeAccounts === 1 ? "account" : "accounts"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Active accounts */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
            <div className="px-6 py-3 border-b border-white/5">
              <h2 className="text-sm font-semibold text-white">
                Active accounts · {days}d
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-400 border-b border-white/5">
                    <th className="px-6 py-3 font-medium">Customer</th>
                    <th className="px-6 py-3 font-medium">Company</th>
                    <th className="px-6 py-3 font-medium">Tier</th>
                    <th className="px-6 py-3 font-medium">Calls</th>
                    <th className="px-6 py-3 font-medium">Tools</th>
                    <th className="px-6 py-3 font-medium">Hrs saved</th>
                    <th className="px-6 py-3 font-medium">Last active</th>
                  </tr>
                </thead>
                <tbody>
                  {u.accounts.map((a) => (
                    <tr key={a.licenseKey} className="border-b border-white/5 last:border-0">
                      <td className="px-6 py-3">
                        <Link
                          href={`/admin/users/${a.licenseKey}`}
                          className="text-cyan-400 hover:underline"
                        >
                          {a.email}
                        </Link>
                      </td>
                      <td className="px-6 py-3 text-gray-300">{a.company || "—"}</td>
                      <td className="px-6 py-3 text-gray-400 capitalize">{a.tier}</td>
                      <td className="px-6 py-3 text-white font-semibold">{a.calls}</td>
                      <td className="px-6 py-3 text-gray-400">{a.distinctTools}</td>
                      <td className="px-6 py-3 text-gray-400">
                        {Math.round(a.minutesSaved / 6) / 10}
                      </td>
                      <td className="px-6 py-3 text-gray-400">{fmtDate(a.lastActive)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BigMetric({
  label,
  value,
  accent,
  sub,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
  sub?: string;
}) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        accent ? "border-cyan-500/30 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"
      }`}
    >
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ? "text-cyan-300" : "text-white"}`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

function ToolPanel({ title, tools }: { title: string; tools: ToolStat[] }) {
  const max = Math.max(1, ...tools.map((t) => t.calls));
  const shown = tools.slice(0, 12);
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
      <h2 className="text-sm font-semibold text-white mb-4">{title}</h2>
      {shown.length === 0 ? (
        <p className="text-sm text-gray-500">No tool usage yet.</p>
      ) : (
        <div className="space-y-2.5">
          {shown.map((t) => (
            <div key={t.tool}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-mono text-gray-300">{t.tool}</span>
                <span className="text-gray-500">
                  {t.calls} · {Math.round(t.minutesSaved / 6) / 10}h
                </span>
              </div>
              <div className="h-2 w-full rounded bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded bg-gradient-to-r from-cyan-500/40 to-cyan-400/80"
                  style={{ width: `${(t.calls / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
