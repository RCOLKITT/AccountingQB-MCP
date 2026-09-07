import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/cron/rollup-usage
 *
 * Maintains the permanent `tool_usage_daily` rollup and (once enabled) prunes raw
 * `tool_usage` rows past the retention window. Runs every 15 min (Vercel Cron) so
 * every usage read can aggregate over the rollup with ≤15 min staleness.
 *
 * - Rollup: recomputes the last 2 days (idempotent; a missed run self-heals, and the
 *   UTC day boundary is handled). Cheap — an index range-scan over recent rows.
 * - Prune: DESTRUCTIVE, so it is OFF by default and gated behind
 *   TOOL_USAGE_PRUNE_ENABLED=true. Enable it ONLY after the usage reads are sourced
 *   from the rollup in production (see migrations/2026-09-tool-usage-rollup.sql). The
 *   rollup fully backstops pruned rows, so lifetime totals never shrink.
 *   Retention window: TOOL_USAGE_RETENTION_DAYS (default 90) — the single knob.
 *
 * Protected by CRON_SECRET (Vercel sends it automatically).
 */
export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;
  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const supabase = getSupabase();

    const { data: rolledUp, error: rollupError } = await supabase.rpc(
      "rollup_tool_usage",
      { lookback_days: 2 },
    );
    if (rollupError) {
      console.error("rollup_tool_usage failed:", rollupError);
      throw rollupError;
    }

    let pruned: number | null = null;
    if (process.env.TOOL_USAGE_PRUNE_ENABLED === "true") {
      const retentionDays = Number(process.env.TOOL_USAGE_RETENTION_DAYS) || 90;
      const { data: deleted, error: pruneError } = await supabase.rpc(
        "prune_tool_usage",
        { retention_days: retentionDays },
      );
      if (pruneError) {
        console.error("prune_tool_usage failed:", pruneError);
        throw pruneError;
      }
      pruned = deleted ?? 0;
    }

    return NextResponse.json({
      success: true,
      dailyRowsWritten: rolledUp ?? 0,
      rawRowsPruned: pruned, // null when prune is disabled
    });
  } catch (err) {
    console.error("Cron rollup-usage error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
