import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getStripe } from "@/lib/stripe";
import { toMonthly } from "@/lib/stripe-revenue";

// Captures one MRR-by-account row for the current month, so NRR / expansion /
// MRR-over-time become computable (we otherwise only store current state).
// Real billed MRR from Stripe (annual normalized to monthly), keyed by license.
// Idempotent: upsert on (month, license_key) — safe to re-run within a month.

const CRON_SECRET = process.env.CRON_SECRET;

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  if (CRON_SECRET && authHeader !== `Bearer ${CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!process.env.STRIPE_SECRET_KEY) {
    return NextResponse.json(
      { error: "Stripe not configured" },
      { status: 200 },
    );
  }

  const stripe = getStripe();
  // Active subscriptions -> per-subscription monthly MRR (dollars).
  const subs = await stripe.subscriptions
    .list({ status: "active", limit: 100, expand: ["data.items.data.price"] })
    .autoPagingToArray({ limit: 10000 });
  const mrrBySub = new Map<string, number>();
  for (const sub of subs) {
    const mrr =
      sub.items.data.reduce(
        (t, it) =>
          t +
          toMonthly(
            it.price.unit_amount || 0,
            it.price.recurring?.interval,
            it.quantity ?? 1,
          ),
        0,
      ) / 100;
    mrrBySub.set(sub.id, mrr);
  }

  // Map each active subscription to its license and snapshot it.
  const sb = getSupabase();
  const { data: lics } = await sb
    .from("licenses")
    .select("key, tier, status, stripe_subscription_id")
    .eq("is_test", false)
    .not("stripe_subscription_id", "is", null)
    .limit(50000);

  const month = new Date().toISOString().slice(0, 7); // YYYY-MM
  const now = new Date().toISOString();
  const rows: {
    month: string;
    license_key: string;
    mrr_cents: number;
    tier: string | null;
    status: string | null;
    captured_at: string;
  }[] = [];
  for (const l of lics || []) {
    const mrr = mrrBySub.get(l.stripe_subscription_id as string);
    if (mrr === undefined) continue; // subscription not active in Stripe
    rows.push({
      month,
      license_key: l.key,
      mrr_cents: Math.round(mrr * 100),
      tier: l.tier,
      status: l.status,
      captured_at: now,
    });
  }

  if (rows.length) {
    const { error } = await sb
      .from("mrr_snapshots")
      .upsert(rows, { onConflict: "month,license_key" });
    if (error) {
      console.error("mrr-snapshot upsert failed:", error);
      return NextResponse.json({ error: "upsert failed" }, { status: 500 });
    }
  }
  return NextResponse.json({ month, snapshotted: rows.length });
}
