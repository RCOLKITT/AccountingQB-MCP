import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/cron/update-stats
 * Aggregates usage statistics and updates the cache table.
 * Called by Vercel Cron every 5 minutes.
 * Protected by CRON_SECRET authorization.
 */
export async function GET(req: NextRequest) {
  // Verify cron secret (Vercel sends this automatically)
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const supabase = getSupabase();

    // Get total tool calls and time saved
    const { data: allUsage, error: allError } = await supabase
      .from("tool_usage")
      .select("time_saved_minutes");

    if (allError) {
      console.error("Failed to fetch all usage:", allError);
      throw allError;
    }

    const totalToolCalls = allUsage?.length || 0;
    const totalMinutes =
      allUsage?.reduce((sum, r) => sum + (r.time_saved_minutes || 0), 0) || 0;
    const totalHoursSaved = Math.round((totalMinutes / 60) * 10) / 10;

    // Get this week's calls
    const startOfWeek = new Date();
    startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());
    startOfWeek.setHours(0, 0, 0, 0);

    const { data: weekUsage, error: weekError } = await supabase
      .from("tool_usage")
      .select("id")
      .gte("invoked_at", startOfWeek.toISOString());

    if (weekError) {
      console.error("Failed to fetch week usage:", weekError);
      throw weekError;
    }

    const callsThisWeek = weekUsage?.length || 0;

    // Get active licenses (licenses with usage in the last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const { data: activeLicenseData, error: licenseError } = await supabase
      .from("tool_usage")
      .select("license_key")
      .gte("invoked_at", thirtyDaysAgo.toISOString());

    if (licenseError) {
      console.error("Failed to fetch active licenses:", licenseError);
      throw licenseError;
    }

    const uniqueLicenses = new Set(activeLicenseData?.map((r) => r.license_key));
    const activeLicenses = uniqueLicenses.size;

    // Upsert cache record
    const { error: upsertError } = await supabase.from("usage_stats_cache").upsert(
      {
        id: "global",
        total_tool_calls: totalToolCalls,
        total_hours_saved: totalHoursSaved,
        calls_this_week: callsThisWeek,
        active_licenses: activeLicenses,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "id" }
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
      { status: 500 }
    );
  }
}
