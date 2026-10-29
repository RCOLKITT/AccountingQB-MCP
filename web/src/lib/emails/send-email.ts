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
  // Marketing only: the recipient's unsubscribe URL. When present we attach the
  // RFC 8058 one-click headers (List-Unsubscribe + List-Unsubscribe-Post) that
  // Gmail/Yahoo bulk-sender rules expect. Omit for transactional mail.
  listUnsubscribeUrl?: string;
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
      // One-click unsubscribe for marketing mail (the body already carries a
      // visible unsubscribe link + postal address). /api/unsubscribe handles the
      // POST that providers send for List-Unsubscribe-Post.
      ...(data.listUnsubscribeUrl
        ? {
            headers: {
              "List-Unsubscribe": `<${data.listUnsubscribeUrl}>`,
              "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
          }
        : {}),
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
 * Format date for display in emails.
 *
 * timeZone pinned to UTC: every surface (email, dashboard, settings) must
 * render the SAME calendar date for the same instant. A trial ending
 * 2026-11-05T01:28Z once showed "November 5" in the email (server renders in
 * UTC) but "November 4" on the settings page (browser renders in the user's
 * local zone) — a user wrote in asking which date was real.
 */
export function formatDate(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
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
