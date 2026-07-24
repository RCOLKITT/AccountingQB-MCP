import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { currentUser } from "@clerk/nextjs/server";
import { scheduleEmail } from "@/lib/emails/schedule-email";
import { EmailType } from "@/lib/emails/send-email";

// Only re-engagement campaigns are supported for now
const ALLOWED_CAMPAIGN_TYPES: EmailType[] = ["reengagement"];

const VALID_FILTERS = ["stuck", "canceled", "all_never_connected"];

interface LicenseRow {
  key: string;
  email: string;
  tier: string;
  status: string;
  created_at: string;
}

/**
 * POST /api/admin/campaign
 * Schedule a bulk email campaign to a cohort of users.
 *
 * Body: { emailType: 'reengagement', filter: 'stuck' | 'canceled' | 'all_never_connected', dryRun?: boolean }
 *
 * Skips license keys that already have an email_schedules row of the same
 * email_type (never double-send a campaign email).
 * dryRun returns the recipient list without scheduling anything.
 */
export async function POST(req: NextRequest) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const adminEmail = user.emailAddresses[0]?.emailAddress || "admin";

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { emailType, filter, dryRun } = body as {
    emailType?: string;
    filter?: string;
    dryRun?: boolean;
  };

  if (!emailType || !ALLOWED_CAMPAIGN_TYPES.includes(emailType as EmailType)) {
    return NextResponse.json({ error: "Invalid email type" }, { status: 400 });
  }

  if (!filter || !VALID_FILTERS.includes(filter)) {
    return NextResponse.json({ error: "Invalid filter" }, { status: 400 });
  }

  const supabase = getSupabase();

  // Fetch the base cohort of licenses. Internal/demo accounts (is_test) are
  // never included in campaigns — so we don't email ourselves.
  let query = supabase
    .from("licenses")
    .select("key, email, tier, status, created_at")
    .eq("is_test", false)
    .order("created_at", { ascending: false });

  if (filter === "canceled") {
    query = query.eq("status", "canceled");
  } else if (filter === "stuck") {
    query = query.eq("status", "trialing");
  }
  // 'all_never_connected' starts from all licenses

  const { data: licenses, error } = await query.limit(500);

  if (error) {
    console.error("Failed to fetch campaign cohort:", error);
    return NextResponse.json({ error: "Failed to fetch cohort" }, { status: 500 });
  }

  // Determine QB connection status for each license (same milestone check
  // the admin users list uses)
  const cohort: LicenseRow[] = [];
  for (const license of (licenses as LicenseRow[]) || []) {
    if (filter === "canceled") {
      cohort.push(license);
      continue;
    }

    const { data: milestone } = await supabase
      .from("user_milestones")
      .select("id")
      .eq("license_key", license.key)
      .eq("milestone", "qb_connected")
      .maybeSingle();

    const qbConnected = !!milestone;

    if (filter === "stuck") {
      // Trialing > 3 days with no QB connected
      const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);
      if (!qbConnected && new Date(license.created_at) < threeDaysAgo) {
        cohort.push(license);
      }
    } else if (filter === "all_never_connected") {
      if (!qbConnected) {
        cohort.push(license);
      }
    }
  }

  // Dedupe: skip licenses that already have a schedule row of this email type
  const cohortKeys = cohort.map((l) => l.key);
  const alreadyScheduled = new Set<string>();

  if (cohortKeys.length > 0) {
    const { data: existing } = await supabase
      .from("email_schedules")
      .select("license_key")
      .eq("email_type", emailType)
      .in("license_key", cohortKeys);

    for (const row of existing || []) {
      alreadyScheduled.add(row.license_key);
    }
  }

  const recipients = cohort
    .filter((l) => l.email && !alreadyScheduled.has(l.key))
    .map((l) => ({ key: l.key, email: l.email, tier: l.tier }));

  if (dryRun) {
    return NextResponse.json({
      dryRun: true,
      recipients: recipients.map((r) => ({ key: r.key, email: r.email })),
      count: recipients.length,
    });
  }

  // Schedule the campaign emails for immediate delivery
  let scheduled = 0;
  const failures: string[] = [];

  for (const recipient of recipients) {
    const result = await scheduleEmail({
      licenseKey: recipient.key,
      emailType: emailType as EmailType,
      scheduledFor: new Date(),
      metadata: {
        email: recipient.email,
        tier: recipient.tier,
        campaign: true,
        filter,
        sentBy: adminEmail,
      },
    });

    if (result.success) {
      scheduled++;
    } else {
      failures.push(recipient.key);
    }
  }

  console.log(
    `Campaign ${emailType} (${filter}) scheduled for ${scheduled} users by ${adminEmail}`
  );

  return NextResponse.json({
    success: true,
    scheduled,
    failed: failures.length,
    count: scheduled,
  });
}
