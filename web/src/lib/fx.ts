import { unstable_cache } from "next/cache";
import type { CurrencyAmount } from "./stripe-revenue";

// FX conversion to USD, used ONLY for the explicitly-labeled "estimated ARR"
// blend on the admin revenue page. The authoritative per-currency numbers are
// never blended; this is a convenience estimate that always shows the rate and
// as-of date it used, so a stale rate can never masquerade as exact.

// Dated fallback if the live rate fetch fails — better a labeled stale estimate
// than a broken page. Update occasionally; the UI shows this date when used.
const FALLBACK_USD_PER: Record<string, number> = {
  USD: 1,
  CAD: 0.71,
};
const FALLBACK_AS_OF = "2026-11-28";

export interface UsdRates {
  // USD per 1 unit of currency, e.g. { USD: 1, CAD: 0.71 }.
  rates: Record<string, number>;
  asOf: string; // date the rates are from
  live: boolean; // false => fallback constants were used
}

async function fetchUsdRates(currencies: string[]): Promise<UsdRates> {
  const needed = [...new Set(currencies.map((c) => c.toUpperCase()))].filter(
    (c) => c !== "USD",
  );
  if (needed.length === 0) {
    return { rates: { USD: 1 }, asOf: FALLBACK_AS_OF, live: true };
  }
  try {
    // Frankfurter (ECB data, keyless). base=USD → how many units of each
    // currency per 1 USD; invert to get USD per unit.
    const res = await fetch(
      `https://api.frankfurter.dev/v1/latest?base=USD&symbols=${needed.join(",")}`,
      { signal: AbortSignal.timeout(5000) },
    );
    if (!res.ok) throw new Error(`fx ${res.status}`);
    const json = (await res.json()) as {
      date: string;
      rates: Record<string, number>;
    };
    const rates: Record<string, number> = { USD: 1 };
    for (const c of needed) {
      const perUsd = json.rates?.[c];
      if (!perUsd || perUsd <= 0) throw new Error(`no rate for ${c}`);
      rates[c] = 1 / perUsd; // USD per unit of currency
    }
    return { rates, asOf: json.date, live: true };
  } catch {
    return {
      rates: { ...FALLBACK_USD_PER },
      asOf: FALLBACK_AS_OF,
      live: false,
    };
  }
}

// Cache the rate for 12h — an ARR estimate does not need intraday FX.
export const getUsdRates = unstable_cache(fetchUsdRates, ["admin-fx-usd"], {
  revalidate: 43200,
});

/**
 * Blend per-currency amounts into a single USD total using USD-per-unit rates.
 * A currency with no rate falls back to 1:1 and is reported via `missing` so
 * the caller can disclose it rather than silently mis-add. Pure + testable.
 */
export function blendToUsd(
  amounts: CurrencyAmount[],
  rates: Record<string, number>,
): { usd: number; missing: string[] } {
  let usd = 0;
  const missing: string[] = [];
  for (const a of amounts) {
    const rate = rates[a.currency.toUpperCase()];
    if (rate === undefined) {
      missing.push(a.currency);
      usd += a.amount; // 1:1 fallback, disclosed via `missing`
    } else {
      usd += a.amount * rate;
    }
  }
  return { usd, missing };
}
