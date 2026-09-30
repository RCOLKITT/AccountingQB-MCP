import { getSupabase } from "@/lib/supabase";
import { unstable_cache } from "next/cache";
import Link from "next/link";

const CACHE_SECONDS = 60;

interface DownloadStats {
  total: number;
  macos: number;
  windows: number;
  macosPercent: number;
  trend: { date: string; macos: number; windows: number; total: number }[];
}

async function getDownloads(days: number): Promise<DownloadStats> {
  const empty: DownloadStats = {
    total: 0,
    macos: 0,
    windows: 0,
    macosPercent: 0,
    trend: [],
  };
  try {
    const since = new Date(Date.now() - days * 86400000).toISOString();
    const { data, error } = await getSupabase()
      .from("app_downloads")
      .select("platform, downloaded_at")
      .gte("downloaded_at", since)
      .order("downloaded_at", { ascending: false })
      .limit(20000);
    if (error || !data) return empty;

    const rows = data as { platform: string; downloaded_at: string }[];
    const daily: Record<string, { macos: number; windows: number }> = {};
    let macos = 0;
    let windows = 0;
    for (const r of rows) {
      if (r.platform === "macos") macos++;
      else if (r.platform === "windows") windows++;
      const d = r.downloaded_at.slice(0, 10);
      (daily[d] ||= { macos: 0, windows: 0 })[
        r.platform as "macos" | "windows"
      ]++;
    }
    const trend = Object.keys(daily)
      .sort()
      .map((date) => ({
        date,
        ...daily[date],
        total: daily[date].macos + daily[date].windows,
      }));
    const total = macos + windows;
    return {
      total,
      macos,
      windows,
      macosPercent: total ? Math.round((macos / total) * 100) : 0,
      trend,
    };
  } catch {
    return empty;
  }
}

const getData = unstable_cache(
  (days: number) => getDownloads(days),
  ["admin-downloads"],
  {
    revalidate: CACHE_SECONDS,
  },
);

interface InstallStats {
  total: number;
  activeInWindow: number;
  byPlatform: { platform: string; count: number }[];
  recent: {
    license_key: string;
    app_version: string | null;
    platform: string | null;
    last_seen_at: string;
  }[];
}

// Local desktop installs that have phoned home (activation heartbeat). This is
// the ONLY visibility we have into who runs the free local app — downloads
// alone are anonymous.
async function getInstalls(days: number): Promise<InstallStats> {
  const empty: InstallStats = {
    total: 0,
    activeInWindow: 0,
    byPlatform: [],
    recent: [],
  };
  try {
    const since = new Date(Date.now() - days * 86400000).toISOString();
    const { data, error } = await getSupabase()
      .from("app_heartbeats")
      .select("license_key, app_version, platform, last_seen_at")
      .order("last_seen_at", { ascending: false })
      .limit(5000);
    if (error || !data) return empty;
    const rows = data as InstallStats["recent"][number][];
    const byPlat: Record<string, number> = {};
    let active = 0;
    for (const r of rows) {
      byPlat[r.platform || "unknown"] =
        (byPlat[r.platform || "unknown"] || 0) + 1;
      if (r.last_seen_at >= since) active++;
    }
    return {
      total: rows.length,
      activeInWindow: active,
      byPlatform: Object.entries(byPlat)
        .map(([platform, count]) => ({ platform, count }))
        .sort((a, b) => b.count - a.count),
      recent: rows.slice(0, 15),
    };
  } catch {
    return empty;
  }
}

const getInstallData = unstable_cache(
  (days: number) => getInstalls(days),
  ["admin-installs"],
  { revalidate: CACHE_SECONDS },
);

function Metric({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-5 ${accent ? "border-cyan-500/30 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}
    >
      <p className="text-xs text-gray-400">{label}</p>
      <p
        className={`mt-1 text-2xl font-bold ${accent ? "text-cyan-300" : "text-white"}`}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

export default async function DownloadsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const sp = await searchParams;
  const days = sp.days === "7" ? 7 : sp.days === "90" ? 90 : 30;
  const [data, installs] = await Promise.all([
    getData(days),
    getInstallData(days),
  ]);
  const maxTotal = Math.max(1, ...data.trend.map((t) => t.total));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Desktop app downloads
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            Clicks through <code className="text-gray-300">/api/download</code>{" "}
            → the signed GitHub release. Direct GitHub downloads aren&rsquo;t
            counted here.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
          {[7, 30, 90].map((d) => (
            <Link
              key={d}
              href={`/admin/downloads?days=${d}`}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                days === d
                  ? "bg-cyan-500/20 text-cyan-300"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {d} days
            </Link>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label={`Total · ${days}d`} value={data.total} accent />
        <Metric
          label="macOS"
          value={data.macos}
          sub={`${data.macosPercent}%`}
        />
        <Metric
          label="Windows"
          value={data.windows}
          sub={`${data.total ? 100 - data.macosPercent : 0}%`}
        />
        <Metric label="Avg / day" value={Math.round(data.total / days)} />
      </div>

      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <h2 className="mb-4 text-sm font-semibold text-white">
          Daily downloads · {days}d
        </h2>
        {data.trend.length === 0 ? (
          <p className="text-sm text-gray-500">
            No downloads recorded yet in this window.
          </p>
        ) : (
          <>
            <div className="space-y-2">
              {data.trend.map((d) => (
                <div key={d.date} className="flex items-center gap-3 text-sm">
                  <span className="w-24 text-gray-400">{d.date}</span>
                  <div className="flex h-5 flex-1 gap-0.5">
                    <div
                      className="rounded-sm bg-cyan-500/50"
                      style={{ width: `${(d.macos / maxTotal) * 100}%` }}
                      title={`macOS: ${d.macos}`}
                    />
                    <div
                      className="rounded-sm bg-blue-600/50"
                      style={{ width: `${(d.windows / maxTotal) * 100}%` }}
                      title={`Windows: ${d.windows}`}
                    />
                  </div>
                  <span className="w-10 text-right font-semibold text-gray-300">
                    {d.total}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-6 text-sm text-gray-300">
              <span>
                <span className="text-cyan-400">●</span> macOS
              </span>
              <span>
                <span className="text-blue-400">●</span> Windows
              </span>
            </div>
          </>
        )}
      </div>

      {/* Local installs (activation heartbeats) — who is actually RUNNING the
          free local app. Downloads alone are anonymous; this is the only signal
          we have into local usage. */}
      <div>
        <h2 className="mb-1 text-lg font-bold text-white">Local installs</h2>
        <p className="mb-4 text-sm text-gray-400">
          Desktop apps that activated a license and phoned home (activation +
          version only — no usage or financial data). Installs that never
          activate stay invisible.
        </p>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Metric label="Activated installs" value={installs.total} accent />
          <Metric
            label={`Active · ${days}d`}
            value={installs.activeInWindow}
            sub="seen in window"
          />
          <Metric
            label="Platforms"
            value={
              installs.byPlatform
                .map((p) => `${p.platform}:${p.count}`)
                .join("  ") || "—"
            }
          />
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-[#131a2e]">
          <div className="border-b border-white/5 px-6 py-3">
            <h3 className="text-sm font-semibold text-white">
              Most recently active
            </h3>
          </div>
          {installs.recent.length === 0 ? (
            <p className="px-6 py-4 text-sm text-gray-500">
              No local installs have activated yet.
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs text-gray-400">
                  <th className="px-6 py-2 font-medium">License</th>
                  <th className="px-6 py-2 font-medium">Version</th>
                  <th className="px-6 py-2 font-medium">Platform</th>
                  <th className="px-6 py-2 font-medium">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {installs.recent.map((r) => (
                  <tr key={r.license_key} className="border-b border-white/5">
                    <td className="px-6 py-3 font-mono text-xs text-cyan-400">
                      {r.license_key}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-300">
                      {r.app_version || "—"}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-300">
                      {r.platform || "—"}
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-400">
                      {r.last_seen_at.slice(0, 16).replace("T", " ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
