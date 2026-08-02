import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { sendEmail, EmailType } from "@/lib/emails/send-email";
import { isSuppressed } from "@/lib/emails/unsubscribe";
import { campaignEmail, type CampaignContent } from "@/lib/emails/templates/campaign";
import {
  welcomeEmail,
  qbConnectedEmail,
  day3CheckinEmail,
  trialWarning4DayEmail,
  trialWarning1DayEmail,
  trialExpiredEmail,
  paymentFailedEmail,
  subscriptionRenewedEmail,
  reengagementEmail,
} from "@/lib/emails/templates";

// Verify cron secret to prevent unauthorized access
const CRON_SECRET = process.env.CRON_SECRET;

interface EmailSchedule {
  id: string;
  license_key: string;
  email_type: EmailType;
  metadata: Record<string, unknown>;
}

interface License {
  email: string;
  tier: string;
  card_last_four?: string;
  card_brand?: string;
  trial_ends_at?: string;
}

/**
 * GET /api/cron/process-emails
 * Process and send all pending scheduled emails.
 * Called by Vercel Cron every 15 minutes.
 */
export async function GET(req: NextRequest) {
  // Verify cron secret
  const authHeader = req.headers.get("authorization");
  if (CRON_SECRET && authHeader !== `Bearer ${CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabase();
  const now = new Date().toISOString();

  // Get all pending emails that are due
  const { data: pendingEmails, error: fetchError } = await supabase
    .from("email_schedules")
    .select("id, license_key, email_type, metadata")
    .lte("scheduled_for", now)
    .is("sent_at", null)
    .eq("cancelled", false)
    .limit(50);

  if (fetchError) {
    console.error("Failed to fetch pending emails:", fetchError);
    return NextResponse.json(
      { error: "Failed to fetch emails" },
      { status: 500 }
    );
  }

  if (!pendingEmails || pendingEmails.length === 0) {
    return NextResponse.json({ processed: 0, message: "No emails to process" });
  }

  const results: { id: string; success: boolean; error?: string }[] = [];

  for (const schedule of pendingEmails as EmailSchedule[]) {
    try {
      // Get license info
      const { data: license } = await supabase
        .from("licenses")
        .select("email, tier, card_last_four, card_brand, trial_ends_at")
        .eq("key", schedule.license_key)
        .single();

      if (!license || !license.email) {
        // Mark as sent but with error
        await supabase
          .from("email_schedules")
          .update({
            sent_at: now,
            error_message: "License not found or no email",
          })
          .eq("id", schedule.id);

        results.push({
          id: schedule.id,
          success: false,
          error: "License not found",
        });
        continue;
      }

      // Check if day_3_checkin should be skipped (if QB is connected)
      if (schedule.email_type === "day_3_checkin") {
        const { data: milestones } = await supabase
          .from("user_milestones")
          .select("id")
          .eq("license_key", schedule.license_key)
          .eq("milestone", "qb_connected")
          .single();

        if (milestones) {
          // User already connected QB, cancel this email
          await supabase
            .from("email_schedules")
            .update({ cancelled: true })
            .eq("id", schedule.id);

          results.push({
            id: schedule.id,
            success: true,
            error: "Skipped - QB already connected",
          });
          continue;
        }
      }

      // Compliance (CAN-SPAM / CASL): never send MARKETING mail to an
      // unsubscribed address, even if it was queued before they opted out.
      // Transactional/lifecycle mail (welcome, trial warnings, payment
      // failures, renewals) is exempt.
      const MARKETING_TYPES: EmailType[] = ["campaign", "reengagement"];
      if (
        MARKETING_TYPES.includes(schedule.email_type) &&
        (await isSuppressed(license.email))
      ) {
        await supabase
          .from("email_schedules")
          .update({ cancelled: true, error_message: "Suppressed (unsubscribed)" })
          .eq("id", schedule.id);
        results.push({
          id: schedule.id,
          success: true,
          error: "Skipped - unsubscribed",
        });
        continue;
      }

      // Generate email content based on type
      const emailContent = generateEmailContent(
        schedule.email_type,
        license as License,
        schedule.license_key,
        schedule.metadata
      );

      if (!emailContent) {
        await supabase
          .from("email_schedules")
          .update({
            sent_at: now,
            error_message: "Unknown email type",
          })
          .eq("id", schedule.id);

        results.push({
          id: schedule.id,
          success: false,
          error: "Unknown email type",
        });
        continue;
      }

      // Send the email
      const sendResult = await sendEmail({
        to: license.email,
        subject: emailContent.subject,
        html: emailContent.html,
      });

      if (sendResult.success) {
        await supabase
          .from("email_schedules")
          .update({ sent_at: now })
          .eq("id", schedule.id);

        results.push({ id: schedule.id, success: true });
      } else {
        await supabase
          .from("email_schedules")
          .update({
            error_message: sendResult.error || "Send failed",
          })
          .eq("id", schedule.id);

        results.push({
          id: schedule.id,
          success: false,
          error: sendResult.error,
        });
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : "Unknown error";
      console.error(`Failed to process email ${schedule.id}:`, error);

      await supabase
        .from("email_schedules")
        .update({ error_message: error })
        .eq("id", schedule.id);

      results.push({ id: schedule.id, success: false, error });
    }
  }

  const successful = results.filter((r) => r.success).length;
  const failed = results.filter((r) => !r.success).length;

  console.log(`Processed ${results.length} emails: ${successful} sent, ${failed} failed`);

  return NextResponse.json({
    processed: results.length,
    successful,
    failed,
    results,
  });
}

function generateEmailContent(
  emailType: EmailType,
  license: License,
  licenseKey: string,
  metadata: Record<string, unknown>
): { subject: string; html: string } | null {
  const baseParams = {
    email: license.email,
    licenseKey,
    tier: license.tier,
  };

  switch (emailType) {
    case "welcome":
      return welcomeEmail({
        ...baseParams,
        trialDays: 14,
      });

    case "qb_connected":
      return qbConnectedEmail({
        ...baseParams,
        companyName: (metadata.companyName as string) || "Your Company",
      });

    case "day_3_checkin":
      return day3CheckinEmail({
        ...baseParams,
        hasQbConnected: false, // If we got here, QB is not connected
      });

    case "trial_warning_4day":
      return trialWarning4DayEmail({
        ...baseParams,
        trialEndsAt:
          (metadata.trialEndsAt as string) || license.trial_ends_at || "",
        cardLastFour: license.card_last_four,
        cardBrand: license.card_brand,
      });

    case "trial_warning_1day":
      return trialWarning1DayEmail({
        ...baseParams,
        trialEndsAt:
          (metadata.trialEndsAt as string) || license.trial_ends_at || "",
        cardLastFour: license.card_last_four,
        cardBrand: license.card_brand,
      });

    case "trial_expired":
      return trialExpiredEmail(baseParams);

    case "payment_failed":
      return paymentFailedEmail({
        ...baseParams,
        cardLastFour: license.card_last_four,
        cardBrand: license.card_brand,
        attemptCount: (metadata.attemptCount as number) || 1,
      });

    case "reengagement":
      return reengagementEmail(baseParams);

    case "subscription_renewed":
      return subscriptionRenewedEmail({
        ...baseParams,
        amountCents: (metadata.amountCents as number) || 3900,
        cardLastFour: license.card_last_four,
        cardBrand: license.card_brand,
        nextBillingDate: (metadata.nextBillingDate as string) || "",
        invoiceUrl: metadata.invoiceUrl as string | undefined,
      });

    case "campaign":
      // AI-composed / hand-written marketing email; copy lives in metadata.
      return campaignEmail(
        metadata as unknown as CampaignContent,
        license.email
      );

    default:
      return null;
  }
}
