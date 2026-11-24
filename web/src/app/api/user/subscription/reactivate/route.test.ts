import { describe, it, expect, vi, beforeEach } from "vitest";

// Regression suite for expired-trial reactivation (user incident, 2026-11):
// the trial lapsed → Stripe canceled the trial subscription → the user added
// a card in the billing portal → nothing happened, because adding a payment
// method never revives a canceled subscription, and the dashboard offered no
// other path. Locks:
//   1. a saved card + a prior (canceled) sub → NEW sub on the SAME price,
//      license linked + activated in one call,
//   2. no card on file → needs_payment_method, NO Stripe subscription create,
//   3. an already-live sub is adopted, never duplicated (no double charge),
//   4. active licenses are a no-op (no charge).

const state: {
  license: Record<string, unknown> | null;
  updates: Record<string, unknown>[];
  subs: Record<string, unknown>[];
  paymentMethods: Record<string, unknown>[];
  defaultPm: string | null;
  created: Record<string, unknown>[];
} = {
  license: null,
  updates: [],
  subs: [],
  paymentMethods: [],
  defaultPm: null,
  created: [],
};

vi.mock("@/lib/stripe", () => ({
  getStripe: () => ({
    customers: {
      retrieve: async () => ({
        invoice_settings: { default_payment_method: state.defaultPm },
      }),
    },
    paymentMethods: {
      list: async () => ({ data: state.paymentMethods }),
      retrieve: async () => ({
        card: { last4: "2006", brand: "amex" },
      }),
    },
    subscriptions: {
      list: async () => ({ data: state.subs }),
      create: async (params: Record<string, unknown>) => {
        state.created.push(params);
        return {
          id: "sub_new",
          status: "active",
          created: 2,
          current_period_end: 1800000000,
          items: {
            data: [{ price: { id: "price_ca_biz", unit_amount: 9900 } }],
          },
          latest_invoice: null,
        };
      },
    },
  }),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => {
    const builder: Record<string, unknown> = {};
    Object.assign(builder, {
      select: () => builder,
      eq: () => builder,
      maybeSingle: async () => ({ data: state.license }),
      update: (row: Record<string, unknown>) => {
        state.updates.push(row);
        return builder;
      },
      insert: async () => ({ error: null }),
      from: () => builder,
    });
    return { from: () => builder };
  },
}));

vi.mock("@/lib/event-logger", () => ({
  logEvent: async () => undefined,
}));

vi.mock("@/lib/subscription", () => ({
  mapStripeStatus: (s: string) =>
    s === "active" || s === "trialing" || s === "past_due"
      ? s === "past_due"
        ? "active"
        : s
      : s === "canceled"
        ? "canceled"
        : "expired",
}));

import { POST } from "./route";

function req(body: Record<string, unknown>): Request {
  return new Request("http://test/api/user/subscription/reactivate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

const CANCELED_SUB = {
  id: "sub_old",
  status: "canceled",
  created: 1,
  items: { data: [{ price: { id: "price_ca_biz", unit_amount: 9900 } }] },
};

beforeEach(() => {
  state.license = {
    key: "LK-TEST-FICTIONAL",
    status: "expired",
    tier: "business",
    stripe_customer_id: "cus_test",
    stripe_subscription_id: null,
  };
  state.updates = [];
  state.subs = [CANCELED_SUB];
  state.paymentMethods = [];
  state.defaultPm = "pm_saved";
  state.created = [];
});

describe("POST /api/user/subscription/reactivate", () => {
  it("creates a new sub on the prior price and activates the license", async () => {
    const res = await POST(req({ licenseKey: "LK-TEST-FICTIONAL" }) as never);
    const data = await res.json();
    expect(data.state).toBe("reactivated");
    expect(state.created).toHaveLength(1);
    expect(state.created[0].items).toEqual([{ price: "price_ca_biz" }]); // SAME price → tier+currency preserved
    expect(state.created[0].default_payment_method).toBe("pm_saved");
    const upd = state.updates[0];
    expect(upd.status).toBe("active");
    expect(upd.stripe_subscription_id).toBe("sub_new");
    expect(upd.card_last_four).toBe("2006");
  });

  it("refuses to charge without a saved card (the incident's precondition)", async () => {
    state.defaultPm = null;
    state.paymentMethods = [];
    const res = await POST(req({ licenseKey: "LK-TEST-FICTIONAL" }) as never);
    const data = await res.json();
    expect(data.state).toBe("needs_payment_method");
    expect(state.created).toHaveLength(0); // nothing created, nothing charged
  });

  it("adopts an existing live sub instead of double-charging", async () => {
    state.subs = [
      CANCELED_SUB,
      {
        id: "sub_live",
        status: "active",
        created: 5,
        current_period_end: 1800000000,
        items: { data: [{ price: { id: "price_ca_biz", unit_amount: 9900 } }] },
        latest_invoice: null,
      },
    ];
    const res = await POST(req({ licenseKey: "LK-TEST-FICTIONAL" }) as never);
    const data = await res.json();
    expect(data.state).toBe("reactivated");
    expect(state.created).toHaveLength(0); // adopted, not created
    expect(state.updates[0].stripe_subscription_id).toBe("sub_live");
  });

  it("is a no-op for already-active licenses", async () => {
    state.license = { ...state.license!, status: "active" };
    const res = await POST(req({ licenseKey: "LK-TEST-FICTIONAL" }) as never);
    const data = await res.json();
    expect(data.state).toBe("already_active");
    expect(state.created).toHaveLength(0);
    expect(state.updates).toHaveLength(0);
  });
});
