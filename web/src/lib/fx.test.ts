import { describe, it, expect } from "vitest";
import { blendToUsd } from "./fx";

describe("blendToUsd", () => {
  it("blends CAD into USD at the given rate (the ARR estimate case)", () => {
    // 2 USD + 2 CAD active subs annualized: US$1,656 + CA$1,656.
    // CA$1,656 × 0.70 = $1,159.20 → total ≈ $2,815.20.
    const { usd, missing } = blendToUsd(
      [
        { currency: "USD", amount: 1656 },
        { currency: "CAD", amount: 1656 },
      ],
      { USD: 1, CAD: 0.7 },
    );
    expect(usd).toBeCloseTo(2815.2, 2);
    expect(missing).toEqual([]);
  });

  it("passes USD through unchanged", () => {
    const { usd } = blendToUsd([{ currency: "USD", amount: 5000 }], { USD: 1 });
    expect(usd).toBe(5000);
  });

  it("falls back to 1:1 and discloses a currency with no rate", () => {
    const { usd, missing } = blendToUsd([{ currency: "GBP", amount: 100 }], {
      USD: 1,
    });
    expect(usd).toBe(100); // 1:1 fallback
    expect(missing).toEqual(["GBP"]); // disclosed, never silent
  });

  it("is case-insensitive on currency codes", () => {
    const { usd } = blendToUsd([{ currency: "cad", amount: 100 }], {
      USD: 1,
      CAD: 0.7,
    });
    expect(usd).toBeCloseTo(70, 5);
  });

  it("returns zero for no amounts", () => {
    expect(blendToUsd([], { USD: 1 })).toEqual({ usd: 0, missing: [] });
  });
});
