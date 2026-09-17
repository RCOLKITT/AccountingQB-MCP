import { describe, it, expect, vi, beforeEach } from "vitest";

// Shared harness state the mocked libs read from (set per test).
const state: {
  license: Record<string, unknown> | null;
  stripeStatus: string;
  stripeError: { code?: string } | null;
  updated: Record<string, unknown> | null;
} = { license: null, stripeStatus: "active", stripeError: null, updated: null };

const logEvent = vi.fn();

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => {
    const builder: Record<string, unknown> = {};
    Object.assign(builder, {
      select: () => builder,
      eq: () => builder,
      update: (vals: Record<string, unknown>) => {
        state.updated = vals;
        return builder;
      },
      single: async () => ({
        data: state.license,
        error: state.license ? null : { message: "not found" },
      }),
    });
    return { from: () => builder };
  },
}));

vi.mock("@/lib/stripe", () => ({
  getStripe: () => ({
    subscriptions: {
      retrieve: async () => {
        if (state.stripeError) throw state.stripeError;
        return { status: state.stripeStatus };
      },
    },
  }),
}));

vi.mock("@/lib/event-logger", () => ({
  logEvent: (...args: unknown[]) => logEvent(...args),
}));

import { mapStripeStatus, reconcileSubscriptionStatus } from "./subscription";

beforeEach(() => {
  state.license = null;
  state.stripeStatus = "active";
  state.stripeError = null;
  state.updated = null;
  logEvent.mockClear();
});

describe("mapStripeStatus", () => {
  it("maps active/past_due → active (dunning keeps access)", () => {
    expect(mapStripeStatus("active")).toBe("active");
    expect(mapStripeStatus("past_due")).toBe("active");
  });
  it("maps trialing → trialing, canceled → canceled", () => {
    expect(mapStripeStatus("trialing")).toBe("trialing");
    expect(mapStripeStatus("canceled")).toBe("canceled");
  });
  it("maps unpaid/incomplete/unknown → expired", () => {
    expect(mapStripeStatus("unpaid")).toBe("expired");
    expect(mapStripeStatus("incomplete")).toBe("expired");
    expect(mapStripeStatus("incomplete_expired")).toBe("expired");
    expect(mapStripeStatus("whatever")).toBe("expired");
  });
});

describe("reconcileSubscriptionStatus", () => {
  it("returns null when the license doesn't exist", async () => {
    state.license = null;
    expect(await reconcileSubscriptionStatus("LK-NONE")).toBeNull();
  });

  it("no-ops for a no-card trial (no stripe_subscription_id)", async () => {
    state.license = {
      key: "LK-1",
      status: "trialing",
      stripe_customer_id: null,
      stripe_subscription_id: null,
    };
    const r = await reconcileSubscriptionStatus("LK-1");
    expect(r).toEqual({
      status: "trialing",
      reconciled: false,
      hasSubscription: false,
      hasBillingAccount: false,
    });
    expect(state.updated).toBeNull();
    expect(logEvent).not.toHaveBeenCalled();
  });

  it("heals drift: DB trialing but Stripe canceled → updates to canceled + logs (Chris's case)", async () => {
    state.license = {
      key: "LK-2",
      status: "trialing",
      stripe_customer_id: "cus_x",
      stripe_subscription_id: "sub_x",
    };
    state.stripeStatus = "canceled";
    const r = await reconcileSubscriptionStatus("LK-2");
    expect(r?.status).toBe("canceled");
    expect(r?.reconciled).toBe(true);
    expect(state.updated?.status).toBe("canceled");
    expect(logEvent).toHaveBeenCalledTimes(1);
  });

  it("treats a deleted Stripe sub (resource_missing) as canceled", async () => {
    state.license = {
      key: "LK-3",
      status: "trialing",
      stripe_customer_id: "cus_x",
      stripe_subscription_id: "sub_gone",
    };
    state.stripeError = { code: "resource_missing" };
    const r = await reconcileSubscriptionStatus("LK-3");
    expect(r?.status).toBe("canceled");
    expect(r?.reconciled).toBe(true);
    expect(state.updated?.status).toBe("canceled");
  });

  it("does not resurrect a locally-canceled license from a still-active sub", async () => {
    state.license = {
      key: "LK-4",
      status: "canceled",
      stripe_customer_id: "cus_x",
      stripe_subscription_id: "sub_winddown",
    };
    state.stripeStatus = "active"; // cancel_at_period_end sub still reports active
    const r = await reconcileSubscriptionStatus("LK-4");
    expect(r?.status).toBe("canceled");
    expect(r?.reconciled).toBe(false);
    expect(state.updated).toBeNull(); // no flip back to active
  });

  it("no-ops when DB already matches Stripe", async () => {
    state.license = {
      key: "LK-5",
      status: "active",
      stripe_customer_id: "cus_x",
      stripe_subscription_id: "sub_x",
    };
    state.stripeStatus = "active";
    const r = await reconcileSubscriptionStatus("LK-5");
    expect(r?.reconciled).toBe(false);
    expect(state.updated).toBeNull();
  });

  it("leaves the DB untouched on a transient Stripe error", async () => {
    state.license = {
      key: "LK-6",
      status: "trialing",
      stripe_customer_id: "cus_x",
      stripe_subscription_id: "sub_x",
    };
    state.stripeError = { code: "api_connection_error" };
    const r = await reconcileSubscriptionStatus("LK-6");
    expect(r?.status).toBe("trialing");
    expect(r?.reconciled).toBe(false);
    expect(state.updated).toBeNull();
  });
});
