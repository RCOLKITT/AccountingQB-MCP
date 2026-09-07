import { NextResponse } from "next/server";
import { createServerComponentClient } from "@/lib/supabase-server";
import { getSupabase } from "@/lib/supabase";

interface ToolAgg {
  tool_name: string;
  calls: number;
  minutes: number;
}

/**
 * GET /api/usage/stats
 * Returns usage statistics for the authenticated user.
 *
 * Aggregates over the permanent `tool_usage_daily` rollup via SQL RPCs (bounded to
 * ≤#tools rows) rather than fetching every raw `tool_usage` row into Node — the old
 * approach silently capped at PostgREST's ~1000-row limit, undercounting lifetime
 * calls / hours-saved for any active account.
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

    // UTC calendar-day boundaries for the rollup's DATE grain.
    const dayString = (d: Date) => d.toISOString().slice(0, 10);
    const now = new Date();
    const startOfMonth = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1),
    );
    const startOfWeek = new Date(now);
    startOfWeek.setUTCDate(startOfWeek.getUTCDate() - startOfWeek.getUTCDay());
    startOfWeek.setUTCHours(0, 0, 0, 0);

    const sumCalls = (rows: ToolAgg[] | null) =>
      (rows || []).reduce((s, r) => s + Number(r.calls || 0), 0);
    const sumMinutes = (rows: ToolAgg[] | null) =>
      (rows || []).reduce((s, r) => s + Number(r.minutes || 0), 0);

    // All-time per-tool (for totals + top tools), plus month/week windows.
    const [{ data: allUsage }, { data: monthUsage }, { data: weekUsage }] =
      await Promise.all([
        serviceSupabase.rpc("rollup_by_tool", {
          p_keys: licenseKeys,
          p_since: null,
        }),
        serviceSupabase.rpc("rollup_by_tool", {
          p_keys: licenseKeys,
          p_since: dayString(startOfMonth),
        }),
        serviceSupabase.rpc("rollup_by_tool", {
          p_keys: licenseKeys,
          p_since: dayString(startOfWeek),
        }),
      ]);

    const totalCalls = sumCalls(allUsage);
    const totalMinutes = sumMinutes(allUsage);
    const monthCalls = sumCalls(monthUsage);
    const monthMinutes = sumMinutes(monthUsage);
    const weekCalls = sumCalls(weekUsage);

    // Top tools by all-time call count.
    const topTools = ((allUsage as ToolAgg[]) || [])
      .slice()
      .sort((a, b) => Number(b.calls) - Number(a.calls))
      .slice(0, 10)
      .map((r) => ({
        name: formatToolName(r.tool_name),
        rawName: r.tool_name,
        count: Number(r.calls),
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
