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
  const empty: DownloadStats = { total: 0, macos: 0, windows: 0, macosPercent: 0, trend: [] };
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
      (daily[d] ||= { macos: 0, windows: 0 })[r.platform as "macos" | "windows"]++;
    }
    const trend = Object.keys(daily)
      .sort()
      .map((date) => ({ date, ...daily[date], total: daily[date].macos + daily[date].windows }));
    const total = macos + windows;
    return { total, macos, windows, macosPercent: total ? Math.round((macos / total) * 100) : 0, trend };
  } catch {
    return empty;
  }
}

const getData = unstable_cache((days: number) => getDownloads(days), ["admin-downloads"], {
  revalidate: CACHE_SECONDS,
});

function Metric({ label, value, sub, accent }: { label: string; value: number | string; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "border-cyan-500/30 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ? "text-cyan-300" : "text-white"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

export default async function DownloadsPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = sp.days === "7" ? 7 : sp.days === "90" ? 90 : 30;
  const data = await getData(days);
  const maxTotal = Math.max(1, ...data.trend.map((t) => t.total));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Desktop app downloads</h1>
          <p className="mt-1 text-sm text-gray-400">
            Clicks through <code className="text-gray-300">/api/download</code> → the signed GitHub release.
            Direct GitHub downloads aren&rsquo;t counted here.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
          {[7, 30, 90].map((d) => (
            <Link
              key={d}
              href={`/admin/downloads?days=${d}`}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                days === d ? "bg-cyan-500/20 text-cyan-300" : "text-gray-400 hover:text-white"
              }`}
            >
              {d} days
            </Link>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label={`Total · ${days}d`} value={data.total} accent />
        <Metric label="macOS" value={data.macos} sub={`${data.macosPercent}%`} />
        <Metric label="Windows" value={data.windows} sub={`${data.total ? 100 - data.macosPercent : 0}%`} />
        <Metric label="Avg / day" value={Math.round(data.total / days)} />
      </div>

      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <h2 className="mb-4 text-sm font-semibold text-white">Daily downloads · {days}d</h2>
        {data.trend.length === 0 ? (
          <p className="text-sm text-gray-500">No downloads recorded yet in this window.</p>
        ) : (
          <>
            <div className="space-y-2">
              {data.trend.map((d) => (
                <div key={d.date} className="flex items-center gap-3 text-sm">
                  <span className="w-24 text-gray-400">{d.date}</span>
                  <div className="flex h-5 flex-1 gap-0.5">
                    <div className="rounded-sm bg-cyan-500/50" style={{ width: `${(d.macos / maxTotal) * 100}%` }} title={`macOS: ${d.macos}`} />
                    <div className="rounded-sm bg-blue-600/50" style={{ width: `${(d.windows / maxTotal) * 100}%` }} title={`Windows: ${d.windows}`} />
                  </div>
                  <span className="w-10 text-right font-semibold text-gray-300">{d.total}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-6 text-sm text-gray-300">
              <span><span className="text-cyan-400">●</span> macOS</span>
              <span><span className="text-blue-400">●</span> Windows</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
