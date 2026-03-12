import { NextResponse } from "next/server";

/**
 * GET /api/debug-env — temporarily check which env vars are set (no values exposed)
 * DELETE THIS ROUTE before going to production.
 */
export async function GET() {
  return NextResponse.json({
    STRIPE_SECRET_KEY: !!process.env.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET: !!process.env.STRIPE_WEBHOOK_SECRET,
    STRIPE_PRICE_SOLOPRENEUR: !!process.env.STRIPE_PRICE_SOLOPRENEUR,
    STRIPE_PRICE_BUSINESS: !!process.env.STRIPE_PRICE_BUSINESS,
    STRIPE_PRICE_FIRM: !!process.env.STRIPE_PRICE_FIRM,
    SUPABASE_URL: !!process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
    NEXT_PUBLIC_BASE_URL: !!process.env.NEXT_PUBLIC_BASE_URL,
    QB_CLIENT_ID: !!process.env.QB_CLIENT_ID,
    QB_CLIENT_SECRET: !!process.env.QB_CLIENT_SECRET,
    NODE_ENV: process.env.NODE_ENV,
  });
}
