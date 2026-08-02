import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { currentUser } from "@clerk/nextjs/server";

interface LicenseRow {
  key: string;
  email: string;
  tier: string;
  status: string;
  created_at: string;
  trial_ends_at: string | null;
}

/**
 * GET /api/admin/users
 * List users with optional filters and search.
 */
export async function GET(req: NextRequest) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const supabase = getSupabase();
  const { searchParams } = req.nextUrl;

  const filter = searchParams.get("filter") || "all";
  const search = searchParams.get("search") || "";

  let query = supabase
    .from("licenses")
    .select("key, email, tier, status, created_at, trial_ends_at")
    .order("created_at", { ascending: false });

  // Apply status filter
  if (filter === "trialing") {
    query = query.eq("status", "trialing");
  } else if (filter === "active") {
    query = query.eq("status", "active");
  } else if (filter === "canceled") {
    query = query.eq("status", "canceled");
  } else if (filter === "expired") {
    query = query.eq("status", "expired");
  } else if (filter === "trial_ending") {
    const now = new Date();
    const oneWeekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    query = query
      .eq("status", "trialing")
      .lte("trial_ends_at", oneWeekFromNow.toISOString())
      .gte("trial_ends_at", now.toISOString());
  }

  // Apply search
  if (search) {
    query = query.or(`email.ilike.%${search}%,key.ilike.%${search}%`);
  }

  // Cap high enough to avoid silently hiding users (the 'stuck' filter runs in
  // JS after this fetch). TODO: true cursor pagination when the list outgrows this.
  const { data: licenses, error } = await query.limit(1000);

  if (error) {
    console.error("Failed to fetch users:", error);
    return NextResponse.json({ error: "Failed to fetch users" }, { status: 500 });
  }

  const keys = (licenses as LicenseRow[] || []).map((l) => l.key);

  // Last-active per license: most recent of tool_usage or oauth activity.
  // Bounded by the current page's license keys (<=100) so this stays cheap.
  const lastActive = new Map<string, string>();
  const noteActivity = (key: string, ts: string | null) => {
    if (!ts) return;
    const cur = lastActive.get(key);
    if (!cur || ts > cur) lastActive.set(key, ts);
  };
  if (keys.length > 0) {
    const [{ data: usageRows }, { data: eventRows }] = await Promise.all([
      supabase
        .from("tool_usage")
        .select("license_key, invoked_at")
        .in("license_key", keys)
        .order("invoked_at", { ascending: false }),
      supabase
        .from("event_logs")
        .select("license_key, created_at")
        .in("license_key", keys)
        .in("event_type", ["oauth_connect", "oauth_refresh"])
        .order("created_at", { ascending: false }),
    ]);
    for (const r of (usageRows as { license_key: string; invoked_at: string }[]) || [])
      noteActivity(r.license_key, r.invoked_at);
    for (const r of (eventRows as { license_key: string; created_at: string }[]) || [])
      noteActivity(r.license_key, r.created_at);
  }

  // Get milestone data for each user
  const users = await Promise.all(
    (licenses as LicenseRow[] || []).map(async (license) => {
      const { data: milestone } = await supabase
        .from("user_milestones")
        .select("id")
        .eq("license_key", license.key)
        .eq("milestone", "qb_connected")
        .maybeSingle();

      return {
        ...license,
        qb_connected: !!milestone,
        last_active: lastActive.get(license.key) || null,
      };
    })
  );

  // Filter stuck users (trialing > 3 days, no QB connected)
  if (filter === "stuck") {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);
    const stuckUsers = users.filter(
      (u) =>
        u.status === "trialing" &&
        new Date(u.created_at) < threeDaysAgo &&
        !u.qb_connected
    );
    return NextResponse.json({ users: stuckUsers });
  }

  return NextResponse.json({ users });
}
