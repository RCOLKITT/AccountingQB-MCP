import { describe, it, expect } from "vitest";
import { toMonthly, mrrByCurrency } from "./stripe-revenue";

// Minimal Stripe.Subscription shape for the aggregator. The real type is huge;
// we only read currency + items[].price.{unit_amount,recurring.interval}.
function sub(
  currency: string,
  unit_amount: number,
  interval = "month",
  quantity = 1,
) {
  return {
    currency,
    items: {
      data: [{ price: { unit_amount, recurring: { interval } }, quantity }],
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;
}

describe("toMonthly", () => {
  it("normalizes yearly to monthly", () => {
    expect(toMonthly(120000, "year")).toBe(10000);
  });
  it("passes monthly through", () => {
    expect(toMonthly(9900, "month")).toBe(9900);
  });
  it("multiplies by quantity", () => {
    expect(toMonthly(3900, "month", 3)).toBe(11700);
  });
});

describe("mrrByCurrency", () => {
  it("NEVER blends CAD into USD (the revenue-overstatement incident)", () => {
    // Exactly the live state that overstated MRR by ~18%: 2 USD + 2 CAD active
    // subs. A CAD sub carries subscription.currency="cad" even though its price
    // is a USD-based price (unit_amount 9900) — the amount is billed in CAD.
    const subs = [
      sub("usd", 9900), // US$99 business
      sub("usd", 3900), // US$39 solo
      sub("cad", 9900), // CA$99 business  (was counted as US$99)
      sub("cad", 3900), // CA$39 solo      (was counted as US$39)
    ];
    const result = mrrByCurrency(subs);
    expect(result).toEqual([
      { currency: "USD", amount: 138 },
      { currency: "CAD", amount: 138 },
    ]);
    // The old code returned a single 276 "USD" number. Prove we don't.
    const blended = result.reduce((s, r) => s + r.amount, 0);
    expect(blended).toBe(276); // arithmetic sum exists but is NOT labeled USD
    const usdOnly = result.find((r) => r.currency === "USD")!.amount;
    expect(usdOnly).toBe(138); // true USD MRR, not 276
  });

  it("sorts currencies by amount descending", () => {
    const result = mrrByCurrency([sub("cad", 1000), sub("usd", 5000)]);
    expect(result.map((r) => r.currency)).toEqual(["USD", "CAD"]);
  });

  it("defaults a missing currency to USD", () => {
    const result = mrrByCurrency([sub("", 9900)]);
    expect(result).toEqual([{ currency: "USD", amount: 99 }]);
  });

  it("normalizes annual subs within their own currency", () => {
    const result = mrrByCurrency([sub("cad", 118800, "year")]); // CA$1188/yr
    expect(result).toEqual([{ currency: "CAD", amount: 99 }]); // CA$99/mo
  });

  it("returns empty for no subscriptions", () => {
    expect(mrrByCurrency([])).toEqual([]);
  });
});
