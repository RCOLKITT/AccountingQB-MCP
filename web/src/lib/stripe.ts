import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-02-24.acacia",
});

// Map tier names to Stripe price IDs (configure in env vars)
export const TIER_PRICES: Record<string, string> = {
  solopreneur: process.env.STRIPE_PRICE_SOLOPRENEUR!,
  business: process.env.STRIPE_PRICE_BUSINESS!,
  firm: process.env.STRIPE_PRICE_FIRM!,
};
