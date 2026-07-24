import { Resend } from "resend";

// Lazy initialization to avoid build-time errors
let resend: Resend | null = null;

function getResend(): Resend {
  if (!resend) {
    resend = new Resend(process.env.RESEND_API_KEY);
  }
  return resend;
}

export type EmailType =
  | "welcome"
  | "qb_connected"
  | "day_3_checkin"
  | "trial_warning_4day"
  | "trial_warning_1day"
  | "trial_expired"
  | "payment_failed"
  | "subscription_renewed"
  | "reengagement"
  | "campaign"; // custom AI-drafted / hand-written marketing send

interface EmailData {
  to: string;
  subject: string;
  html: string;
  replyTo?: string;
}

interface SendEmailResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * Send an email via Resend
 */
export async function sendEmail(data: EmailData): Promise<SendEmailResult> {
  try {
    const result = await getResend().emails.send({
      // Product-branded sender (isolates AccountingQB's sending reputation);
      // replies route to the central Vaspera support desk.
      from: "AccountingQB <hello@accountingqb.com>",
      to: data.to,
      subject: data.subject,
      html: data.html,
      replyTo: data.replyTo || "support@vasperacapital.com",
    });

    if (result.error) {
      console.error("Resend error:", result.error);
      return { success: false, error: result.error.message };
    }

    return { success: true, messageId: result.data?.id };
  } catch (err) {
    const error = err instanceof Error ? err.message : "Unknown error";
    console.error("Failed to send email:", error);
    return { success: false, error };
  }
}

/**
 * Format currency for display in emails
 */
export function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/**
 * Format date for display in emails
 */
export function formatDate(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/**
 * Get the tier display name
 */
export function getTierDisplayName(tier: string): string {
  const names: Record<string, string> = {
    solopreneur: "Solopreneur",
    business: "Business",
    firm: "Firm",
  };
  return names[tier] || tier;
}

/**
 * Get the monthly price for a tier in cents
 */
export function getTierPriceCents(tier: string): number {
  const prices: Record<string, number> = {
    solopreneur: 3900,
    business: 9900,
    firm: 29900,
  };
  return prices[tier] || 3900;
}
