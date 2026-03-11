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
  const prices: Record<string, string | undefined> = {
    solopreneur: process.env.STRIPE_PRICE_SOLOPRENEUR,
    business: process.env.STRIPE_PRICE_BUSINESS,
    firm: process.env.STRIPE_PRICE_FIRM,
  };
  const price = prices[tier];
  if (!price) throw new Error(`No price configured for tier: ${tier}`);
  return price;
}
