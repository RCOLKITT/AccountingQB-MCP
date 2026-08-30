import { NextResponse } from "next/server";
import { createServerComponentClient } from "@/lib/supabase-server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/usage/stats
 * Returns usage statistics for the authenticated user.
 */
export async function GET() {
  try {
    const supabase = await createServerComponentClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const serviceSupabase = getSupabase();

    // Get user's licenses
    const { data: userLicenses } = await serviceSupabase
      .from("user_licenses")
      .select("license_key")
      .eq("user_id", user.id);

    if (!userLicenses?.length) {
      return NextResponse.json({
        totalCalls: 0,
        totalHoursSaved: 0,
        callsThisMonth: 0,
        topTools: [],
      });
    }

    const licenseKeys = userLicenses.map((l) => l.license_key);

    // Get total usage stats
    const { data: allUsage } = await serviceSupabase
      .from("tool_usage")
      .select("tool_name, time_saved_minutes")
      .in("license_key", licenseKeys);

    // Get this month's stats
    const startOfMonth = new Date();
    startOfMonth.setDate(1);
    startOfMonth.setHours(0, 0, 0, 0);

    const { data: monthUsage } = await serviceSupabase
      .from("tool_usage")
      .select("tool_name, time_saved_minutes")
      .in("license_key", licenseKeys)
      .gte("invoked_at", startOfMonth.toISOString());

    // Get this week's stats
    const startOfWeek = new Date();
    startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());
    startOfWeek.setHours(0, 0, 0, 0);

    const { data: weekUsage } = await serviceSupabase
      .from("tool_usage")
      .select("tool_name")
      .in("license_key", licenseKeys)
      .gte("invoked_at", startOfWeek.toISOString());

    // Calculate aggregates
    const totalCalls = allUsage?.length || 0;
    const totalMinutes =
      allUsage?.reduce((sum, r) => sum + (r.time_saved_minutes || 0), 0) || 0;
    const monthCalls = monthUsage?.length || 0;
    const monthMinutes =
      monthUsage?.reduce((sum, r) => sum + (r.time_saved_minutes || 0), 0) || 0;
    const weekCalls = weekUsage?.length || 0;

    // Calculate top tools by usage count
    const toolCounts: Record<string, number> = {};
    allUsage?.forEach((r) => {
      toolCounts[r.tool_name] = (toolCounts[r.tool_name] || 0) + 1;
    });

    const topTools = Object.entries(toolCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, count]) => ({
        name: formatToolName(name),
        rawName: name,
        count,
      }));

    return NextResponse.json({
      totalCalls,
      totalHoursSaved: Math.round((totalMinutes / 60) * 10) / 10,
      totalMinutesSaved: totalMinutes,
      callsThisMonth: monthCalls,
      monthHoursSaved: Math.round((monthMinutes / 60) * 10) / 10,
      callsThisWeek: weekCalls,
      topTools,
    });
  } catch (err) {
    console.error("Usage stats error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}

/**
 * Formats a tool name for display.
 * e.g., "qb_schedule_c" -> "Schedule C"
 */
function formatToolName(name: string): string {
  return name
    .replace(/^qb_/, "") // Remove qb_ prefix
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
