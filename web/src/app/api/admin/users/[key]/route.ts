import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { currentUser } from "@clerk/nextjs/server";

/**
 * GET /api/admin/users/[key]
 * Get detailed user info including milestones, connections, and email history.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { key } = await params;
  const supabase = getSupabase();

  // Get license
  const { data: license, error } = await supabase
    .from("licenses")
    .select("*")
    .eq("key", key)
    .single();

  if (error || !license) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  // Get milestones
  const { data: milestones } = await supabase
    .from("user_milestones")
    .select("milestone, completed_at, metadata")
    .eq("license_key", key)
    .order("completed_at", { ascending: true });

  // Get QB connections
  const { data: qbConnections } = await supabase
    .from("oauth_tokens")
    .select("realm_id, company_name, created_at")
    .eq("license_key", key)
    .order("created_at", { ascending: true });

  // Get email history
  const { data: emails } = await supabase
    .from("email_schedules")
    .select("id, email_type, scheduled_for, sent_at, cancelled")
    .eq("license_key", key)
    .order("scheduled_for", { ascending: false })
    .limit(20);

  // Get trial extensions
  const { data: trialExtensions } = await supabase
    .from("trial_extensions")
    .select("extension_days, extended_by, created_at, reason")
    .eq("license_key", key)
    .order("created_at", { ascending: false });

  // Tool usage (per-tool aggregate + totals) from the permanent rollup, aggregated
  // server-side (bounded to ≤#tools rows) — the old raw full-fetch capped at
  // PostgREST's ~1000 rows, undercounting heavy accounts. "last" is now date-grain
  // (the rollup's UTC day), which is sufficient for the admin "last used" display.
  const { data: usageRows } = await supabase.rpc("rollup_by_tool", {
    p_keys: [key],
    p_since: null,
  });

  let totalCalls = 0;
  let totalMinutes = 0;
  const toolUsage = (
    (usageRows as {
      tool_name: string;
      calls: number;
      minutes: number;
      last_day: string;
    }[]) || []
  )
    .map((r) => {
      const calls = Number(r.calls || 0);
      const minutes = Number(r.minutes || 0);
      totalCalls += calls;
      totalMinutes += minutes;
      return { tool: r.tool_name, calls, minutes, last: r.last_day };
    })
    .sort((a, b) => b.calls - a.calls);

  // Activity timeline (connect/refresh/webhook events)
  const { data: activity } = await supabase
    .from("event_logs")
    .select("event_type, success, created_at, realm_id")
    .eq("license_key", key)
    .order("created_at", { ascending: false })
    .limit(25);

  return NextResponse.json({
    user: {
      ...license,
      milestones: milestones || [],
      qb_connections: qbConnections || [],
      emails: emails || [],
      trial_extensions: trialExtensions || [],
      tool_usage: toolUsage,
      usage_totals: {
        calls: totalCalls,
        hours: Math.round(totalMinutes / 6) / 10,
      },
      activity: activity || [],
    },
  });
}
