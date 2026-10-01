import { describe, it, expect, vi, beforeEach } from "vitest";

// Harness state the mocked supabase reads from.
const state: {
  license: { key: string } | null;
  existingHeartbeat: { license_key: string } | null;
  inserts: { table: string; row: Record<string, unknown> }[];
  rpcCalls: { fn: string; args: Record<string, unknown> }[];
  rpcError: { message: string } | null;
} = {
  license: null,
  existingHeartbeat: null,
  inserts: [],
  rpcCalls: [],
  rpcError: null,
};

vi.mock("@/lib/ratelimit", () => ({
  isRateLimitingEnabled: () => false,
  getUsageTrackLimiter: () => ({ limit: async () => ({ success: true }) }),
  getClientIP: () => "0.0.0.0",
  rateLimitResponse: () => new Response("rate", { status: 429 }),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => {
    let table = "";
    const builder: Record<string, unknown> = {};
    Object.assign(builder, {
      select: () => builder,
      eq: () => builder,
      maybeSingle: async () => ({
        data: table === "licenses" ? state.license : state.existingHeartbeat,
        error: null,
      }),
      insert: async (row: Record<string, unknown>) => {
        state.inserts.push({ table, row });
        return { error: null };
      },
    });
    return {
      from: (t: string) => {
        table = t;
        return builder;
      },
      rpc: async (fn: string, args: Record<string, unknown>) => {
        state.rpcCalls.push({ fn, args });
        return { error: state.rpcError };
      },
    };
  },
}));

import { POST } from "./route";

function post(body: unknown) {
  return POST({ json: async () => body } as unknown as Parameters<
    typeof POST
  >[0]);
}

beforeEach(() => {
  state.license = null;
  state.existingHeartbeat = null;
  state.inserts = [];
  state.rpcCalls = [];
  state.rpcError = null;
});

const KEY = "LK-0123456789ABCDEF0123456789ABCDEF";

describe("POST /api/app/heartbeat", () => {
  it("rejects a malformed license key", async () => {
    const res = await post({ license_key: "nope" });
    expect(res.status).toBe(400);
    expect(state.rpcCalls).toHaveLength(0);
  });

  it("is a silent no-op for an unknown license (no spoof pollution)", async () => {
    state.license = null;
    const res = await post({ license_key: KEY, version: "0.3.1" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, recorded: false });
    expect(state.rpcCalls).toHaveLength(0);
    expect(state.inserts).toHaveLength(0);
  });

  it("records a heartbeat + first-time activation milestone for a known license", async () => {
    state.license = { key: KEY };
    state.existingHeartbeat = null; // first heartbeat
    const res = await post({
      license_key: KEY,
      version: "0.3.1",
      platform: "macos",
    });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, recorded: true });
    // activation milestone on first heartbeat
    const ms = state.inserts.find((i) => i.table === "user_milestones");
    expect(ms?.row.milestone).toBe("app_activated");
    // atomic upsert RPC called with the right args
    expect(state.rpcCalls[0]).toEqual({
      fn: "record_app_heartbeat",
      args: { p_license_key: KEY, p_app_version: "0.3.1", p_platform: "macos" },
    });
  });

  it("does NOT re-insert the activation milestone on a subsequent heartbeat", async () => {
    state.license = { key: KEY };
    state.existingHeartbeat = { license_key: KEY }; // already seen
    await post({ license_key: KEY, version: "0.3.2" });
    expect(
      state.inserts.find((i) => i.table === "user_milestones"),
    ).toBeUndefined();
    expect(state.rpcCalls).toHaveLength(1); // still records the heartbeat
  });

  it("surfaces a 500 if the upsert RPC errors", async () => {
    state.license = { key: KEY };
    state.existingHeartbeat = { license_key: KEY };
    state.rpcError = { message: "db down" };
    const res = await post({ license_key: KEY });
    expect(res.status).toBe(500);
  });
});
