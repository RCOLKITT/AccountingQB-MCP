import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/cron/update-stats
 * Aggregates usage statistics and updates the cache table.
 * Called by Vercel Cron every 5 minutes.
 * Protected by CRON_SECRET authorization.
 *
 * Reads the permanent `tool_usage_daily` rollup via SQL-aggregating RPCs — NOT raw
 * `tool_usage`. The old raw full-fetch (`select(...)` then `.length`) silently capped
 * at PostgREST's ~1000-row limit, undercounting all-time calls once the table grew
 * past 1000 rows. The rollup is kept ≤15 min fresh by /api/cron/rollup-usage.
 */
export async function GET(req: NextRequest) {
  // Verify cron secret (Vercel sends this automatically)
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // UTC calendar-day helpers for the rollup's DATE grain.
  const dayString = (d: Date) => d.toISOString().slice(0, 10);
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setUTCDate(startOfWeek.getUTCDate() - startOfWeek.getUTCDay());
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 86400000);

  try {
    const supabase = getSupabase();

    // All-time totals (per-tool rows, ≤#tools) → sum server-side-aggregated values.
    const { data: allTools, error: allError } = await supabase.rpc(
      "rollup_by_tool",
      { p_keys: null, p_since: null },
    );
    if (allError) throw allError;

    const totalToolCalls = (allTools || []).reduce(
      (s: number, r: { calls: number }) => s + Number(r.calls || 0),
      0,
    );
    const totalMinutes = (allTools || []).reduce(
      (s: number, r: { minutes: number }) => s + Number(r.minutes || 0),
      0,
    );
    const totalHoursSaved = Math.round((totalMinutes / 60) * 10) / 10;

    // This week's calls.
    const { data: weekTools, error: weekError } = await supabase.rpc(
      "rollup_by_tool",
      { p_keys: null, p_since: dayString(startOfWeek) },
    );
    if (weekError) throw weekError;
    const callsThisWeek = (weekTools || []).reduce(
      (s: number, r: { calls: number }) => s + Number(r.calls || 0),
      0,
    );

    // Active licenses = licenses with any rollup activity in the last 30 days
    // (one row per license from rollup_by_license).
    const { data: activeRows, error: licenseError } = await supabase.rpc(
      "rollup_by_license",
      { p_keys: null, p_since: dayString(thirtyDaysAgo) },
    );
    if (licenseError) throw licenseError;
    const activeLicenses = (activeRows || []).length;

    // Upsert cache record
    const { error: upsertError } = await supabase
      .from("usage_stats_cache")
      .upsert(
        {
          id: "global",
          total_tool_calls: totalToolCalls,
          total_hours_saved: totalHoursSaved,
          calls_this_week: callsThisWeek,
          active_licenses: activeLicenses,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "id" },
      );

    if (upsertError) {
      console.error("Failed to upsert stats cache:", upsertError);
      throw upsertError;
    }

    return NextResponse.json({
      success: true,
      stats: {
        totalToolCalls,
        totalHoursSaved,
        callsThisWeek,
        activeLicenses,
      },
    });
  } catch (err) {
    console.error("Cron update-stats error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
