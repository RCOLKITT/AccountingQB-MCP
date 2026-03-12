import Stripe from "stripe";

let _stripe: Stripe | null = null;

export function getStripe(): Stripe {
  if (!_stripe) {
    _stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
      apiVersion: "2025-02-24.acacia" as Stripe.LatestApiVersion,
    });
  }
  return _stripe;
}

export function getTierPrice(tier: string): string {
  const prices: Record<string, string> = {
    solopreneur: process.env.STRIPE_PRICE_SOLOPRENEUR || "price_1T9x8q8gtMApOcAQLAHpDrZv",
    business: process.env.STRIPE_PRICE_BUSINESS || "price_1T9x8r8gtMApOcAQdWEsb6aB",
    firm: process.env.STRIPE_PRICE_FIRM || "price_1T9x8s8gtMApOcAQnseRO501",
  };
  const price = prices[tier];
  if (!price) throw new Error(`No price configured for tier: ${tier}`);
  return price;
}
