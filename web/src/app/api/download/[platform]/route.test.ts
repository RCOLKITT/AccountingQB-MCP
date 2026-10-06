import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/lib/ratelimit", () => ({
  isRateLimitingEnabled: () => false,
  getDownloadLimiter: () => ({ limit: async () => ({ success: true }) }),
  getClientIP: () => "0.0.0.0",
  rateLimitResponse: () => new Response("rate", { status: 429 }),
}));

const inserts: Record<string, unknown>[] = [];
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({
    from: () => ({
      insert: async (row: Record<string, unknown>) => {
        inserts.push(row);
        return { error: null };
      },
    }),
  }),
}));

import { GET } from "./route";

function call(url: string, platform = "macos") {
  return GET(new NextRequest(url), {
    params: Promise.resolve({ platform }),
  });
}

beforeEach(() => {
  inserts.length = 0;
  delete process.env.TRIAL_AT_DOWNLOAD_ENABLED;
});
afterEach(() => {
  delete process.env.TRIAL_AT_DOWNLOAD_ENABLED;
});

describe("GET /api/download/[platform] — trial gate", () => {
  it("no key → redirects to the /download capture page (not the asset)", async () => {
    const res = await call("https://x.com/api/download/macos");
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toContain("/download?platform=macos");
    expect(inserts).toHaveLength(0); // not counted as a download yet
  });

  it("with a license key → records + redirects to the GitHub asset", async () => {
    const res = await call(
      "https://x.com/api/download/macos?key=LK-ABC123DEF456ABC123DEF456ABC12345",
    );
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toContain("github.com");
    expect(res.headers.get("location")).toContain(".dmg");
    expect(inserts[0].license_key).toMatch(/^LK-/);
  });

  it("g=1 (gate already passed) → serves the asset even without a key", async () => {
    const res = await call("https://x.com/api/download/windows?g=1", "windows");
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toContain(".exe");
  });

  it("gate disabled → no key still goes straight to the asset", async () => {
    process.env.TRIAL_AT_DOWNLOAD_ENABLED = "false";
    const res = await call("https://x.com/api/download/macos");
    expect(res.headers.get("location")).toContain(".dmg");
  });

  it("unknown platform → releases page", async () => {
    const res = await call("https://x.com/api/download/linux", "linux");
    expect(res.headers.get("location")).toContain("releases/latest");
  });
});
