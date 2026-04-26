import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getAdminSession } from "@/lib/admin-auth";

/**
 * GET /api/admin/users/[key]
 * Get detailed user info including milestones, connections, and email history.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  // Verify admin
  const admin = await getAdminSession();
  if (!admin) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
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

  return NextResponse.json({
    user: {
      ...license,
      milestones: milestones || [],
      qb_connections: qbConnections || [],
      emails: emails || [],
      trial_extensions: trialExtensions || [],
    },
  });
}
