// Honest download metrics. Raw app_downloads rows overstate demand badly: one
// automated client (single ip_hash + user_agent_hash) produced ~95% of the
// recorded "downloads" in Oct–Nov 2026, which read as customer demand on the
// admin dashboard while trial starts sat at zero. The fix is to lead with
// UNIQUE DEVICES (distinct ip_hash+user_agent_hash) and surface how
// concentrated the raw clicks are, so a hammering client can never masquerade
// as a crowd again. Raw rows are still stored untouched — this is read-time.

export interface DownloadRow {
  platform: string;
  downloaded_at: string;
  ip_hash: string | null;
  user_agent_hash: string | null;
  license_key: string | null;
}

export interface DownloadSummary {
  rawClicks: number;
  uniqueDevices: number;
  uniqueMacos: number;
  uniqueWindows: number;
  /** Share (0–100) of raw clicks from the single busiest device. */
  topDeviceSharePct: number;
  topDeviceClicks: number;
  /** Per-day unique devices (a device counts once per day it appeared). */
  trend: { date: string; macos: number; windows: number; total: number }[];
}

/** A device is an ip_hash+user_agent_hash pair; rows missing both hashes are
 * each treated as their own device (can't tell them apart, so don't collapse
 * real people into one). */
function deviceId(r: DownloadRow, index: number): string {
  if (!r.ip_hash && !r.user_agent_hash) return `anon-${index}`;
  return `${r.ip_hash ?? ""}|${r.user_agent_hash ?? ""}`;
}

export function summarizeDownloads(rows: DownloadRow[]): DownloadSummary {
  const perDevice = new Map<string, number>();
  const devicePlatform = new Map<string, string>(); // first-seen platform
  const daily = new Map<string, { macos: Set<string>; windows: Set<string> }>();

  rows.forEach((r, i) => {
    const id = deviceId(r, i);
    perDevice.set(id, (perDevice.get(id) || 0) + 1);
    if (!devicePlatform.has(id)) devicePlatform.set(id, r.platform);

    const day = r.downloaded_at.slice(0, 10);
    if (!daily.has(day))
      daily.set(day, { macos: new Set(), windows: new Set() });
    const bucket = daily.get(day)!;
    if (r.platform === "windows") bucket.windows.add(id);
    else bucket.macos.add(id);
  });

  let uniqueMacos = 0;
  let uniqueWindows = 0;
  for (const plat of devicePlatform.values()) {
    if (plat === "windows") uniqueWindows++;
    else uniqueMacos++;
  }

  const topDeviceClicks = Math.max(0, ...perDevice.values());
  const trend = [...daily.keys()].sort().map((date) => {
    const b = daily.get(date)!;
    return {
      date,
      macos: b.macos.size,
      windows: b.windows.size,
      total: b.macos.size + b.windows.size,
    };
  });

  return {
    rawClicks: rows.length,
    uniqueDevices: perDevice.size,
    uniqueMacos,
    uniqueWindows,
    topDeviceSharePct: rows.length
      ? Math.round((topDeviceClicks / rows.length) * 100)
      : 0,
    topDeviceClicks,
    trend,
  };
}

export interface ConversionSummary {
  rawTotal: number;
  preGateDevices: number;
  gatedDevices: number;
  gatedKeyedDevices: number;
}

/** All-time conversion denominators in unique devices, split at the gate date.
 * Trials-started comes from event_logs and is passed in by the caller. */
export function summarizeConversion(
  rows: DownloadRow[],
  gateDate: string,
): ConversionSummary {
  const pre = new Set<string>();
  const gated = new Set<string>();
  const keyed = new Set<string>();
  rows.forEach((r, i) => {
    const id = deviceId(r, i);
    if (r.downloaded_at < gateDate) {
      pre.add(id);
    } else {
      gated.add(id);
      if (r.license_key) keyed.add(id);
    }
  });
  return {
    rawTotal: rows.length,
    preGateDevices: pre.size,
    gatedDevices: gated.size,
    gatedKeyedDevices: keyed.size,
  };
}
