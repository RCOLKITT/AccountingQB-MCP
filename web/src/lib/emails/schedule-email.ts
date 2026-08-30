import { getSupabase } from "@/lib/supabase";
import { EmailType } from "./send-email";

interface ScheduleEmailParams {
  licenseKey: string;
  emailType: EmailType;
  scheduledFor: Date;
  metadata?: Record<string, unknown>;
}

interface ScheduleResult {
  success: boolean;
  scheduleId?: string;
  error?: string;
}

/**
 * Schedule an email for future delivery
 */
export async function scheduleEmail(
  params: ScheduleEmailParams,
): Promise<ScheduleResult> {
  const supabase = getSupabase();

  const { data, error } = await supabase
    .from("email_schedules")
    .insert({
      license_key: params.licenseKey,
      email_type: params.emailType,
      scheduled_for: params.scheduledFor.toISOString(),
      metadata: params.metadata || {},
    })
    .select("id")
    .single();

  if (error) {
    console.error("Failed to schedule email:", error);
    return { success: false, error: error.message };
  }

  return { success: true, scheduleId: data.id };
}

/**
 * Cancel a scheduled email
 */
export async function cancelScheduledEmail(
  scheduleId: string,
): Promise<{ success: boolean; error?: string }> {
  const supabase = getSupabase();

  const { error } = await supabase
    .from("email_schedules")
    .update({ cancelled: true })
    .eq("id", scheduleId)
    .is("sent_at", null);

  if (error) {
    console.error("Failed to cancel email:", error);
    return { success: false, error: error.message };
  }

  return { success: true };
}

/**
 * Cancel all pending emails of a specific type for a license
 */
export async function cancelEmailsByType(
  licenseKey: string,
  emailType: EmailType,
): Promise<{ success: boolean; cancelled: number; error?: string }> {
  const supabase = getSupabase();

  const { data, error } = await supabase
    .from("email_schedules")
    .update({ cancelled: true })
    .eq("license_key", licenseKey)
    .eq("email_type", emailType)
    .is("sent_at", null)
    .eq("cancelled", false)
    .select("id");

  if (error) {
    console.error("Failed to cancel emails:", error);
    return { success: false, cancelled: 0, error: error.message };
  }

  return { success: true, cancelled: data?.length || 0 };
}

/**
 * Schedule the initial email sequence for a new signup
 */
export async function scheduleOnboardingEmails(
  licenseKey: string,
  email: string,
  tier: string,
  trialEndsAt: Date,
): Promise<void> {
  const now = new Date();

  // Welcome email - send immediately (1 minute from now to allow checkout to complete)
  await scheduleEmail({
    licenseKey,
    emailType: "welcome",
    scheduledFor: new Date(now.getTime() + 60 * 1000),
    metadata: { email, tier },
  });

  // Day 3 check-in (if QB not connected by then, cron will send)
  await scheduleEmail({
    licenseKey,
    emailType: "day_3_checkin",
    scheduledFor: new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000),
    metadata: { email, tier },
  });

  // Trial warning - 4 days before end
  const fourDaysBefore = new Date(trialEndsAt);
  fourDaysBefore.setDate(fourDaysBefore.getDate() - 4);
  fourDaysBefore.setHours(9, 0, 0, 0); // 9am

  await scheduleEmail({
    licenseKey,
    emailType: "trial_warning_4day",
    scheduledFor: fourDaysBefore,
    metadata: { email, tier, trialEndsAt: trialEndsAt.toISOString() },
  });

  // Trial warning - 1 day before end
  const oneDayBefore = new Date(trialEndsAt);
  oneDayBefore.setDate(oneDayBefore.getDate() - 1);
  oneDayBefore.setHours(9, 0, 0, 0); // 9am

  await scheduleEmail({
    licenseKey,
    emailType: "trial_warning_1day",
    scheduledFor: oneDayBefore,
    metadata: { email, tier, trialEndsAt: trialEndsAt.toISOString() },
  });
}

/**
 * Reschedule trial warning emails after trial extension
 */
export async function rescheduleTrialEmails(
  licenseKey: string,
  email: string,
  tier: string,
  newTrialEndsAt: Date,
): Promise<void> {
  // Cancel existing trial warning emails
  await cancelEmailsByType(licenseKey, "trial_warning_4day");
  await cancelEmailsByType(licenseKey, "trial_warning_1day");
  await cancelEmailsByType(licenseKey, "trial_expired");

  // Schedule new trial warning emails
  const fourDaysBefore = new Date(newTrialEndsAt);
  fourDaysBefore.setDate(fourDaysBefore.getDate() - 4);
  fourDaysBefore.setHours(9, 0, 0, 0);

  await scheduleEmail({
    licenseKey,
    emailType: "trial_warning_4day",
    scheduledFor: fourDaysBefore,
    metadata: { email, tier, trialEndsAt: newTrialEndsAt.toISOString() },
  });

  const oneDayBefore = new Date(newTrialEndsAt);
  oneDayBefore.setDate(oneDayBefore.getDate() - 1);
  oneDayBefore.setHours(9, 0, 0, 0);

  await scheduleEmail({
    licenseKey,
    emailType: "trial_warning_1day",
    scheduledFor: oneDayBefore,
    metadata: { email, tier, trialEndsAt: newTrialEndsAt.toISOString() },
  });
}
