import { describe, it, expect, vi, beforeEach } from "vitest";

// Regression suite for trial extension — the bug class a trial user's request
// surfaced (2026-11): the endpoint moved licenses.trial_ends_at and
// rescheduled emails but NEVER moved Stripe's trial_end. Stripe is what
// actually starts billing, and the reconcile job syncs our status FROM
// Stripe — so the user would be promised one date while Stripe billed (or
// killed the sub) on the old one, then overwrote our extension. Locks:
//   1. Stripe trial_end moves (seconds, prorations off) when a sub exists,
//   2. Stripe failure aborts with NO database change,
//   3. no-subscription trials skip Stripe entirely,
//   4. paying ('active') licenses can never be flipped to trialing.

const state: {
  license: Record<string, unknown> | null;
  updates: Record<string, unknown>[];
  inserts: { table: string; row: Record<string, unknown> }[];
  stripeCalls: { id: string; params: Record<string, unknown> }[];
  stripeError: Error | null;
} = {
  license: null,
  updates: [],
  inserts: [],
  stripeCalls: [],
  stripeError: null,
};

vi.mock("@clerk/nextjs/server", () => ({
  currentUser: async () => ({
    publicMetadata: { role: "admin" },
    emailAddresses: [{ emailAddress: "ryan@vasperacapital.com" }],
  }),
}));

vi.mock("@/lib/emails/schedule-email", () => ({
  rescheduleTrialEmails: async () => undefined,
}));

vi.mock("@/lib/stripe", () => ({
  getStripe: () => ({
    subscriptions: {
      update: async (id: string, params: Record<string, unknown>) => {
        if (state.stripeError) throw state.stripeError;
        state.stripeCalls.push({ id, params });
        return { id };
      },
    },
  }),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => {
    let table = "";
    const builder: Record<string, unknown> = {};
    Object.assign(builder, {
      select: () => builder,
      eq: () => builder,
      single: async () => ({
        data: state.license,
        error: state.license ? null : { message: "not found" },
      }),
      update: (row: Record<string, unknown>) => {
        state.updates.push(row);
        return builder;
      },
      insert: async (row: Record<string, unknown>) => {
        state.inserts.push({ table, row });
        return { error: null };
      },
      then: (res: (v: unknown) => void) => res({ error: null }),
    });
    return {
      from: (t: string) => {
        table = t;
        return builder;
      },
    };
  },
}));

import { POST } from "./route";

function call(days = 14) {
  const req = new Request("http://test/api/admin/users/LK-X/extend-trial", {
    method: "POST",
    body: JSON.stringify({ days, reason: "licensing bug made-good" }),
  });
  // Next.js route handlers accept a Request; params is the dynamic segment.
  return POST(req as never, { params: Promise.resolve({ key: "LK-X" }) });
}

beforeEach(() => {
  state.license = {
    key: "LK-X",
    email: "chris@example.ca",
    tier: "solopreneur",
    status: "trialing",
    trial_ends_at: "2026-11-05T01:28:01Z",
    stripe_subscription_id: "sub_123",
  };
  state.updates = [];
  state.inserts = [];
  state.stripeCalls = [];
  state.stripeError = null;
});

describe("POST /api/admin/users/[key]/extend-trial", () => {
  it("moves Stripe's trial_end (the thing that actually bills) with prorations off", async () => {
    const res = await call(14);
    const body = (await res.json()) as {
      success: boolean;
      newTrialEnd: string;
    };
    expect(body.success).toBe(true);

    expect(state.stripeCalls).toHaveLength(1);
    const { id, params } = state.stripeCalls[0];
    expect(id).toBe("sub_123");
    expect(params.proration_behavior).toBe("none");
    // Stripe gets the SAME instant as the DB (whole seconds vs ISO ms).
    expect(params.trial_end).toBe(
      Math.floor(new Date(body.newTrialEnd).getTime() / 1000),
    );
    // DB updated too.
    expect(state.updates[0].trial_ends_at).toBe(body.newTrialEnd);
  });

  it("aborts with NO database change when Stripe refuses", async () => {
    state.stripeError = new Error("No such subscription");
    const res = await call(14);
    expect(res.status).toBe(502);
    expect(state.updates).toEqual([]); // nothing changed — no false promise
    expect(state.inserts).toEqual([]);
  });

  it("skips Stripe entirely for no-card trials without a subscription", async () => {
    state.license = { ...state.license!, stripe_subscription_id: null };
    const res = await call(7);
    const body = (await res.json()) as { success: boolean };
    expect(body.success).toBe(true);
    expect(state.stripeCalls).toEqual([]);
    expect(state.updates).toHaveLength(1);
  });

  it("refuses to flip a paying license into a trial", async () => {
    state.license = { ...state.license!, status: "active" };
    const res = await call(14);
    expect(res.status).toBe(400);
    expect(state.stripeCalls).toEqual([]);
    expect(state.updates).toEqual([]);
  });
});
