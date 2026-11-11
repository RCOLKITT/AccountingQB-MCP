import { getSupabase } from "@/lib/supabase";
import Link from "next/link";
import {
  summarizeDownloads,
  summarizeConversion,
  type DownloadRow,
  type DownloadSummary,
} from "@/lib/download-stats";

// Live on every load — these are small Supabase reads; no cached snapshot.
export const dynamic = "force-dynamic";

// The trial gate shipped at the download endpoint in PR #125. Downloads BEFORE
// this date were never gated (went straight to the file), so they can't have
// become trials — the conversion panel below separates the two eras honestly.
const DOWNLOAD_GATE_DATE = "2026-10-06";
const DOWNLOAD_ROW_CAP = 100000;

// Unique devices is the headline metric: in Oct–Nov 2026 a single automated
// client produced ~95% of raw clicks and the dashboard read it as demand.
interface DownloadStats extends DownloadSummary {
  truncated: boolean; // true if the row cap was hit (numbers would undercount)
}

interface Conversion {
  rawTotal: number;
  preGateDevices: number;
  gatedDevices: number;
  trialStarts: number;
  truncated: boolean;
}

async function fetchRows(since?: string): Promise<{
  rows: DownloadRow[];
  truncated: boolean;
}> {
  let q = getSupabase()
    .from("app_downloads")
    .select("platform, downloaded_at, ip_hash, user_agent_hash, license_key")
    .order("downloaded_at", { ascending: false })
    .limit(DOWNLOAD_ROW_CAP);
  if (since) q = q.gte("downloaded_at", since);
  const { data, error } = await q;
  if (error || !data) return { rows: [], truncated: false };
  const rows = data as DownloadRow[];
  return { rows, truncated: rows.length >= DOWNLOAD_ROW_CAP };
}

async function getConversion(): Promise<Conversion> {
  const empty: Conversion = {
    rawTotal: 0,
    preGateDevices: 0,
    gatedDevices: 0,
    trialStarts: 0,
    truncated: false,
  };
  try {
    const [{ rows, truncated }, ts] = await Promise.all([
      fetchRows(),
      getSupabase()
        .from("event_logs")
        .select("*", { count: "exact", head: true })
        .eq("event_type", "trial")
        .eq("action", "trial_start"),
    ]);
    const c = summarizeConversion(rows, DOWNLOAD_GATE_DATE);
    return {
      rawTotal: c.rawTotal,
      preGateDevices: c.preGateDevices,
      gatedDevices: c.gatedDevices,
      trialStarts: ts.count || 0,
      truncated,
    };
  } catch {
    return empty;
  }
}

async function getDownloads(days: number): Promise<DownloadStats> {
  try {
    const since = new Date(Date.now() - days * 86400000).toISOString();
    const { rows, truncated } = await fetchRows(since);
    return { ...summarizeDownloads(rows), truncated };
  } catch {
    return { ...summarizeDownloads([]), truncated: false };
  }
}

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
  const [data, installs, conv] = await Promise.all([
    getDownloads(days),
    getInstalls(days),
    getConversion(),
  ]);
  const maxTotal = Math.max(1, ...data.trend.map((t) => t.total));
  // Download-first model: the file downloads immediately and the trial is minted
  // when the visitor submits their email, so conversion = trials started per
  // gated-era unique DEVICE (raw clicks overstate — see download-stats.ts).
  const convRate = conv.gatedDevices
    ? Math.round((conv.trialStarts / conv.gatedDevices) * 1000) / 10
    : 0;
  const concentrated = data.rawClicks >= 10 && data.topDeviceSharePct >= 50;

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
        <Metric
          label={`Unique devices · ${days}d`}
          value={data.uniqueDevices}
          sub="distinct IP + browser"
          accent
        />
        <Metric
          label="Raw clicks"
          value={data.rawClicks}
          sub="repeat hits included"
        />
        <Metric label="macOS devices" value={data.uniqueMacos} />
        <Metric label="Windows devices" value={data.uniqueWindows} />
      </div>

      {concentrated && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-200/90">
          ⚠️ <strong>Phantom-download warning:</strong> one device accounts for{" "}
          {data.topDeviceClicks} of {data.rawClicks} raw clicks (
          {data.topDeviceSharePct}%) in this window. Raw clicks are NOT demand —
          trust the unique-device number. If you run an uptime monitor pointed
          at a download URL, this is probably it.
        </div>
      )}

      {data.truncated && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200/90">
          ⚠️ Showing the first {DOWNLOAD_ROW_CAP.toLocaleString()} rows — totals
          above may undercount. Move to a server-side aggregate before relying
          on them.
        </div>
      )}

      {/* Honest download → trial conversion (all-time, exact counts). */}
      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            Download → trial conversion · all time
          </h2>
          <span className="text-xs text-gray-500">
            gate live since {DOWNLOAD_GATE_DATE}
          </span>
        </div>
        <p className="mb-4 text-xs text-gray-500">
          Downloads before the gate were never asked for an email. Since the
          gate, the app downloads immediately and we offer to email a trial key
          — so conversion = trials started per gated unique device. (Bot hits
          are filtered at write time; repeat clicks are collapsed here.)
        </p>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Metric
            label="Raw clicks · all time"
            value={conv.rawTotal}
            sub="incl. repeat hits"
          />
          <Metric
            label="Pre-gate devices"
            value={conv.preGateDevices}
            sub="never had a trial"
          />
          <Metric
            label="Gated devices"
            value={conv.gatedDevices}
            sub="eligible for a trial"
          />
          <Metric
            label="Trials started → rate"
            value={`${conv.trialStarts} · ${convRate}%`}
            accent={conv.trialStarts > 0}
          />
        </div>
        {conv.gatedDevices > 0 && conv.trialStarts === 0 && (
          <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200/90">
            ⚠️ {conv.gatedDevices} gated device
            {conv.gatedDevices === 1 ? "" : "s"}, but{" "}
            <strong>0 trials started</strong>. The file downloads fine; nobody
            is submitting their email for a key — and the app won&rsquo;t run
            without one. Check the /download page copy and the in-app activation
            flow.
          </p>
        )}
      </div>

      <div className="rounded-xl border border-white/10 bg-[#131a2e] p-6">
        <h2 className="mb-4 text-sm font-semibold text-white">
          Daily unique devices · {days}d
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
