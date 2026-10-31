import { describe, it, expect, vi, beforeEach } from "vitest";

// Regression suite for the license-resolution route — the exact bug class a
// trial user hit (2026-10): he had an OLD expired license linked in
// user_licenses, started a NEW trial (issued email-keyed, no linkage row), and
// the route treated email matching as a fallback that only ran when
// user_licenses was EMPTY — so the dashboard showed only the expired license
// and the OAuth consent page said "No active license found". Locks:
//   1. linked + email-matched licenses are ALWAYS unioned,
//   2. newly discovered email matches are persisted (self-heal),
//   3. usable licenses sort before expired/canceled (UIs preselect [0]).

const state: {
  profile: { id: string; email: string } | null;
  userLicenses: { license_key: string; role: string }[];
  licensesByEmail: Record<string, unknown>[];
  licensesByKey: Record<string, Record<string, unknown>>;
  upserts: { table: string; rows: Record<string, unknown>[] }[];
} = {
  profile: null,
  userLicenses: [],
  licensesByEmail: [],
  licensesByKey: {},
  upserts: [],
};

vi.mock("@clerk/nextjs/server", () => ({
  auth: async () => ({ userId: "clerk_user_1" }),
  currentUser: async () => ({
    emailAddresses: [{ emailAddress: "chris@example.ca" }],
  }),
}));

vi.mock("@/lib/subscription", () => ({
  // Reconciliation is out of scope here — identity passthrough.
  reconcileSubscriptionStatus: async () => null,
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => {
    const makeBuilder = (table: string) => {
      let filter = "";
      let inKeys: string[] = [];
      const resolve = () => {
        if (table === "user_licenses") return { data: state.userLicenses };
        if (table === "licenses" && filter === "ilike")
          return { data: state.licensesByEmail };
        if (table === "licenses" && filter === "in")
          return {
            data: inKeys.map((k) => state.licensesByKey[k]).filter(Boolean),
          };
        return { data: null };
      };
      const builder: Record<string, unknown> = {};
      Object.assign(builder, {
        select: () => builder,
        eq: () => builder,
        ilike: () => {
          filter = "ilike";
          return builder;
        },
        in: (_col: string, keys: string[]) => {
          filter = "in";
          inKeys = keys;
          return builder;
        },
        maybeSingle: async () => ({ data: state.profile, error: null }),
        single: async () => ({ data: state.profile, error: null }),
        upsert: (rows: Record<string, unknown>[] | Record<string, unknown>) => {
          const arr = Array.isArray(rows) ? rows : [rows];
          state.upserts.push({ table, rows: arr });
          // Profile upsert chains .select().single(); user_licenses upsert is
          // awaited directly — support both.
          const chain: Record<string, unknown> = {
            select: () => chain,
            single: async () => ({ data: state.profile, error: null }),
            then: (res: (v: unknown) => void) => res({ error: null }),
          };
          return chain;
        },
        then: (res: (v: unknown) => void) => res(resolve()),
      });
      return builder;
    };
    return { from: (t: string) => makeBuilder(t) };
  },
}));

import { GET } from "./route";

const EXPIRED = {
  key: "LK-OLD-7233",
  tier: "solopreneur",
  status: "expired",
  trial_ends_at: "2026-10-21T03:42:24Z",
  stripe_subscription_id: null,
};
const TRIALING = {
  key: "LK-NEW-5CCF",
  tier: "solopreneur",
  status: "trialing",
  trial_ends_at: "2026-11-05T01:28:01Z",
  stripe_subscription_id: "sub_x",
};

beforeEach(() => {
  state.profile = { id: "profile-1", email: "chris@example.ca" };
  state.userLicenses = [];
  state.licensesByEmail = [];
  state.licensesByKey = {};
  state.upserts = [];
});

describe("GET /api/user/licenses — email matching is a union, not a fallback", () => {
  it("surfaces a new email-keyed trial even when an old license is already linked (the incident shape)", async () => {
    state.userLicenses = [{ license_key: EXPIRED.key, role: "owner" }];
    state.licensesByEmail = [EXPIRED, TRIALING]; // both carry his email
    state.licensesByKey = { [EXPIRED.key]: EXPIRED };

    const res = await GET();
    const body = (await res.json()) as {
      licenses: { key: string; status: string }[];
    };

    const keys = body.licenses.map((l) => l.key);
    expect(keys).toContain(TRIALING.key); // the bug: this was missing
    expect(keys).toContain(EXPIRED.key);
    // Usable-first: the dashboard preselects licenses[0].
    expect(body.licenses[0].key).toBe(TRIALING.key);
    expect(body.licenses[0].status).toBe("trialing");
  });

  it("persists newly discovered email matches so the linkage self-heals", async () => {
    state.userLicenses = [{ license_key: EXPIRED.key, role: "owner" }];
    state.licensesByEmail = [EXPIRED, TRIALING];
    state.licensesByKey = { [EXPIRED.key]: EXPIRED };

    await GET();

    const linkUpserts = state.upserts.filter(
      (u) => u.table === "user_licenses",
    );
    expect(linkUpserts).toHaveLength(1);
    expect(linkUpserts[0].rows).toEqual([
      { user_id: "profile-1", license_key: TRIALING.key, role: "owner" },
    ]);
  });

  it("still resolves email-only users with no linkage rows at all", async () => {
    state.userLicenses = [];
    state.licensesByEmail = [TRIALING];

    const res = await GET();
    const body = (await res.json()) as { licenses: { key: string }[] };
    expect(body.licenses.map((l) => l.key)).toEqual([TRIALING.key]);
  });

  it("includes linked licenses whose email differs from the signed-in user (shared licenses)", async () => {
    const shared = { ...TRIALING, key: "LK-SHARED", status: "active" };
    state.userLicenses = [{ license_key: "LK-SHARED", role: "member" }];
    state.licensesByEmail = []; // not under his email
    state.licensesByKey = { "LK-SHARED": shared };

    const res = await GET();
    const body = (await res.json()) as {
      licenses: { key: string; role: string }[];
    };
    expect(body.licenses.map((l) => l.key)).toEqual(["LK-SHARED"]);
    expect(body.licenses[0].role).toBe("member"); // linkage role preserved
  });

  it("returns an empty list when nothing is linked or email-matched", async () => {
    const res = await GET();
    const body = (await res.json()) as { licenses: unknown[] };
    expect(body.licenses).toEqual([]);
  });
});
