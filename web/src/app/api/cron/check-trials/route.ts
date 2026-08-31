import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { scheduleEmail } from "@/lib/emails/schedule-email";

// Verify cron secret to prevent unauthorized access
const CRON_SECRET = process.env.CRON_SECRET;

interface TrialingLicense {
  key: string;
  email: string;
  tier: string;
  trial_ends_at: string;
}

/**
 * GET /api/cron/check-trials
 * Check for trials ending soon and schedule warning emails.
 * Called by Vercel Cron daily at 9am.
 */
export async function GET(req: NextRequest) {
  // Verify cron secret
  const authHeader = req.headers.get("authorization");
  if (CRON_SECRET && authHeader !== `Bearer ${CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabase();
  const now = new Date();

  // Find trials ending in exactly 4 days (for 4-day warning)
  const fourDaysFromNow = new Date(now);
  fourDaysFromNow.setDate(fourDaysFromNow.getDate() + 4);
  fourDaysFromNow.setHours(23, 59, 59, 999);

  const fourDaysStart = new Date(now);
  fourDaysStart.setDate(fourDaysStart.getDate() + 4);
  fourDaysStart.setHours(0, 0, 0, 0);

  // Find trials ending in exactly 1 day (for 1-day warning)
  const oneDayFromNow = new Date(now);
  oneDayFromNow.setDate(oneDayFromNow.getDate() + 1);
  oneDayFromNow.setHours(23, 59, 59, 999);

  const oneDayStart = new Date(now);
  oneDayStart.setDate(oneDayStart.getDate() + 1);
  oneDayStart.setHours(0, 0, 0, 0);

  // Find trials that have just expired
  const justExpiredEnd = new Date(now);
  const justExpiredStart = new Date(now);
  justExpiredStart.setDate(justExpiredStart.getDate() - 1);

  const results = {
    fourDayWarnings: 0,
    oneDayWarnings: 0,
    expiredNotices: 0,
    errors: [] as string[],
  };

  // Process 4-day warnings
  const { data: fourDayTrials } = await supabase
    .from("licenses")
    .select("key, email, tier, trial_ends_at")
    .eq("status", "trialing")
    .gte("trial_ends_at", fourDaysStart.toISOString())
    .lte("trial_ends_at", fourDaysFromNow.toISOString());

  if (fourDayTrials) {
    for (const license of fourDayTrials as TrialingLicense[]) {
      // Check if we already scheduled this email
      const { data: existing } = await supabase
        .from("email_schedules")
        .select("id")
        .eq("license_key", license.key)
        .eq("email_type", "trial_warning_4day")
        .gte(
          "created_at",
          new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(),
        )
        .single();

      if (!existing) {
        const result = await scheduleEmail({
          licenseKey: license.key,
          emailType: "trial_warning_4day",
          scheduledFor: new Date(), // Send now
          metadata: {
            email: license.email,
            tier: license.tier,
            trialEndsAt: license.trial_ends_at,
          },
        });

        if (result.success) {
          results.fourDayWarnings++;
        } else {
          results.errors.push(
            `4-day warning for ${license.key}: ${result.error}`,
          );
        }
      }
    }
  }

  // Process 1-day warnings
  const { data: oneDayTrials } = await supabase
    .from("licenses")
    .select("key, email, tier, trial_ends_at")
    .eq("status", "trialing")
    .gte("trial_ends_at", oneDayStart.toISOString())
    .lte("trial_ends_at", oneDayFromNow.toISOString());

  if (oneDayTrials) {
    for (const license of oneDayTrials as TrialingLicense[]) {
      const { data: existing } = await supabase
        .from("email_schedules")
        .select("id")
        .eq("license_key", license.key)
        .eq("email_type", "trial_warning_1day")
        .gte(
          "created_at",
          new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(),
        )
        .single();

      if (!existing) {
        const result = await scheduleEmail({
          licenseKey: license.key,
          emailType: "trial_warning_1day",
          scheduledFor: new Date(),
          metadata: {
            email: license.email,
            tier: license.tier,
            trialEndsAt: license.trial_ends_at,
          },
        });

        if (result.success) {
          results.oneDayWarnings++;
        } else {
          results.errors.push(
            `1-day warning for ${license.key}: ${result.error}`,
          );
        }
      }
    }
  }

  // Process expired trials
  const { data: expiredTrials } = await supabase
    .from("licenses")
    .select("key, email, tier, trial_ends_at")
    .eq("status", "trialing")
    .lt("trial_ends_at", justExpiredEnd.toISOString())
    .gte("trial_ends_at", justExpiredStart.toISOString());

  if (expiredTrials) {
    for (const license of expiredTrials as TrialingLicense[]) {
      // Update status to expired
      await supabase
        .from("licenses")
        .update({ status: "expired" })
        .eq("key", license.key);

      // Check if we already sent expired notice
      const { data: existing } = await supabase
        .from("email_schedules")
        .select("id")
        .eq("license_key", license.key)
        .eq("email_type", "trial_expired")
        .single();

      if (!existing) {
        const result = await scheduleEmail({
          licenseKey: license.key,
          emailType: "trial_expired",
          scheduledFor: new Date(),
          metadata: {
            email: license.email,
            tier: license.tier,
          },
        });

        if (result.success) {
          results.expiredNotices++;
        } else {
          results.errors.push(
            `Expired notice for ${license.key}: ${result.error}`,
          );
        }
      }
    }
  }

  console.log("Trial check results:", results);

  return NextResponse.json({
    success: true,
    ...results,
  });
}
