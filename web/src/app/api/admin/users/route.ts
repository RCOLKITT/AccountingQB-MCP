import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getAdminSession } from "@/lib/admin-auth";

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
  // Verify admin
  const admin = await getAdminSession();
  if (!admin) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
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

  const { data: licenses, error } = await query.limit(100);

  if (error) {
    console.error("Failed to fetch users:", error);
    return NextResponse.json({ error: "Failed to fetch users" }, { status: 500 });
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
