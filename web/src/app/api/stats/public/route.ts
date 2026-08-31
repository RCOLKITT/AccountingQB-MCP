import { NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/stats/public
 * Returns public usage statistics for the landing page.
 * Reads from the usage_stats_cache table (updated every 5 minutes by cron).
 * No authentication required.
 */
export async function GET() {
  try {
    const supabase = getSupabase();

    // Read from cache table
    const { data: stats, error } = await supabase
      .from("usage_stats_cache")
      .select("*")
      .eq("id", "global")
      .single();

    if (error || !stats) {
      // Return zeros if cache doesn't exist yet
      return NextResponse.json({
        totalToolCalls: 0,
        totalHoursSaved: 0,
        callsThisWeek: 0,
        activeLicenses: 0,
        updatedAt: null,
      });
    }

    return NextResponse.json({
      totalToolCalls: stats.total_tool_calls,
      totalHoursSaved: stats.total_hours_saved,
      callsThisWeek: stats.calls_this_week,
      activeLicenses: stats.active_licenses,
      updatedAt: stats.updated_at,
    });
  } catch (err) {
    console.error("Public stats error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
