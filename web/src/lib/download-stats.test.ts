import { describe, it, expect } from "vitest";
import {
  summarizeDownloads,
  summarizeConversion,
  type DownloadRow,
} from "./download-stats";

function row(over: Partial<DownloadRow>): DownloadRow {
  return {
    platform: "macos",
    downloaded_at: "2026-11-05T12:00:00Z",
    ip_hash: "ip-a",
    user_agent_hash: "ua-a",
    license_key: null,
    ...over,
  };
}

describe("summarizeDownloads", () => {
  it("collapses a hammering device into one (the phantom-download incident)", () => {
    // Incident shape: one ip+ua pair hit the endpoint 42 times in a week while
    // two real visitors downloaded once each — the dashboard read 44.
    const phantom = Array.from({ length: 42 }, (_, i) =>
      row({ downloaded_at: `2026-11-0${(i % 7) + 1}T0${i % 9}:00:00Z` }),
    );
    const humans = [
      row({ ip_hash: "ip-b", user_agent_hash: "ua-b" }),
      row({ ip_hash: "ip-c", user_agent_hash: "ua-c", platform: "windows" }),
    ];
    const s = summarizeDownloads([...phantom, ...humans]);
    expect(s.rawClicks).toBe(44);
    expect(s.uniqueDevices).toBe(3);
    expect(s.uniqueMacos).toBe(2);
    expect(s.uniqueWindows).toBe(1);
    expect(s.topDeviceClicks).toBe(42);
    expect(s.topDeviceSharePct).toBe(95); // 42/44
  });

  it("counts a device once per day in the trend, not once per click", () => {
    const s = summarizeDownloads([
      row({ downloaded_at: "2026-11-07T10:00:00Z" }),
      row({ downloaded_at: "2026-11-07T11:00:00Z" }), // same device, same day
      row({ downloaded_at: "2026-11-08T10:00:00Z" }), // same device, next day
      row({
        downloaded_at: "2026-11-07T10:30:00Z",
        ip_hash: "ip-b",
        user_agent_hash: "ua-b",
        platform: "windows",
      }),
    ]);
    expect(s.trend).toEqual([
      { date: "2026-11-07", macos: 1, windows: 1, total: 2 },
      { date: "2026-11-08", macos: 1, windows: 0, total: 1 },
    ]);
  });

  it("never collapses hashless rows into one device", () => {
    const s = summarizeDownloads([
      row({ ip_hash: null, user_agent_hash: null }),
      row({ ip_hash: null, user_agent_hash: null }),
    ]);
    expect(s.uniqueDevices).toBe(2);
  });

  it("handles empty input", () => {
    const s = summarizeDownloads([]);
    expect(s.rawClicks).toBe(0);
    expect(s.uniqueDevices).toBe(0);
    expect(s.topDeviceSharePct).toBe(0);
    expect(s.trend).toEqual([]);
  });
});

describe("summarizeConversion", () => {
  it("splits unique devices at the gate date and tracks keyed devices", () => {
    const rows = [
      row({ downloaded_at: "2026-09-01T00:00:00Z" }), // pre-gate
      row({ downloaded_at: "2026-10-07T00:00:00Z" }), // gated, same device
      row({ downloaded_at: "2026-10-08T00:00:00Z" }), // gated, same device again
      row({
        downloaded_at: "2026-10-09T00:00:00Z",
        ip_hash: "ip-b",
        user_agent_hash: "ua-b",
        license_key: "LK-TEST",
      }),
    ];
    const c = summarizeConversion(rows, "2026-10-06");
    expect(c.rawTotal).toBe(4);
    expect(c.preGateDevices).toBe(1);
    expect(c.gatedDevices).toBe(2); // device-a + device-b, not 3 rows
    expect(c.gatedKeyedDevices).toBe(1);
  });
});
