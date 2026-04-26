import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getAdminSession } from "@/lib/admin-auth";
import { scheduleEmail } from "@/lib/emails/schedule-email";
import { EmailType } from "@/lib/emails/send-email";

const VALID_EMAIL_TYPES: EmailType[] = [
  "welcome",
  "qb_connected",
  "day_3_checkin",
  "trial_warning_4day",
  "trial_warning_1day",
  "trial_expired",
  "payment_failed",
  "subscription_renewed",
];

/**
 * POST /api/admin/users/[key]/send-email
 * Manually send an email to a user.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  // Verify admin
  const admin = await getAdminSession();
  if (!admin) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { key } = await params;
  const { emailType } = await req.json();

  if (!emailType || !VALID_EMAIL_TYPES.includes(emailType as EmailType)) {
    return NextResponse.json({ error: "Invalid email type" }, { status: 400 });
  }

  const supabase = getSupabase();

  // Get license
  const { data: license, error } = await supabase
    .from("licenses")
    .select("key, email, tier, trial_ends_at")
    .eq("key", key)
    .single();

  if (error || !license) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  // Schedule the email immediately
  const result = await scheduleEmail({
    licenseKey: key,
    emailType: emailType as EmailType,
    scheduledFor: new Date(),
    metadata: {
      email: license.email,
      tier: license.tier,
      trialEndsAt: license.trial_ends_at,
      manualSend: true,
      sentBy: admin.email,
    },
  });

  if (!result.success) {
    return NextResponse.json(
      { error: result.error || "Failed to schedule email" },
      { status: 500 }
    );
  }

  console.log(
    `Email ${emailType} scheduled for ${key} by ${admin.email}`
  );

  return NextResponse.json({ success: true, scheduleId: result.scheduleId });
}
