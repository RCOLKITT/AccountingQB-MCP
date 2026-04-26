import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  secondaryButton,
  bulletList,
  infoBox,
} from "./base";
import { formatDate, formatCurrency, getTierPriceCents } from "../send-email";

interface TrialWarningEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
  trialEndsAt: string;
  cardLastFour?: string;
  cardBrand?: string;
  daysRemaining: 4 | 1;
}

export function trialWarningEmail(params: TrialWarningEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;
  const cancelUrl = `${appUrl}/dashboard/settings?key=${params.licenseKey}`;

  const tierName =
    params.tier === "solopreneur"
      ? "Solopreneur"
      : params.tier === "business"
        ? "Business"
        : "Firm";

  const price = formatCurrency(getTierPriceCents(params.tier));
  const trialEndDate = formatDate(params.trialEndsAt);

  const cardInfo = params.cardLastFour
    ? `${params.cardBrand || "Card"} ending in ${params.cardLastFour}`
    : "your payment method on file";

  const urgency = params.daysRemaining === 1 ? "tomorrow" : "in 4 days";
  const isUrgent = params.daysRemaining === 1;

  const content = `
    ${heading(`Your trial ends ${urgency}`)}

    ${paragraph(`Your AccountingQB ${tierName} trial ends on <strong>${trialEndDate}</strong>.`)}

    ${infoBox(
      `<strong>What happens next:</strong><br>
      • Your ${cardInfo} will be charged <strong>${price}/month</strong><br>
      • The charge will appear as "ACCOUNTINGQB" on your statement<br>
      • You can cancel anytime before ${trialEndDate} to avoid charges`,
      isUrgent ? "warning" : "info"
    )}

    ${paragraph("Want to continue? Great — no action needed. Your subscription will start automatically.")}

    ${paragraph("Need to cancel? No problem:")}

    ${secondaryButton("Cancel Subscription", cancelUrl)}

    ${paragraph("Or simply reply to this email and I'll take care of it.")}

    ${primaryButton("View Dashboard", dashboardUrl)}

    ${paragraph("Questions about billing or want to change your plan? Just reply to this email.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  const subject =
    params.daysRemaining === 1
      ? `⚠️ Your AccountingQB trial ends tomorrow`
      : `Your AccountingQB trial ends in 4 days`;

  const preheader =
    params.daysRemaining === 1
      ? `Action needed: Your card will be charged ${price} tomorrow`
      : `Your trial ends on ${trialEndDate} — here's what happens next`;

  return {
    subject,
    html: emailWrapper(content, preheader),
  };
}

export function trialWarning4DayEmail(
  params: Omit<TrialWarningEmailParams, "daysRemaining">
): { subject: string; html: string } {
  return trialWarningEmail({ ...params, daysRemaining: 4 });
}

export function trialWarning1DayEmail(
  params: Omit<TrialWarningEmailParams, "daysRemaining">
): { subject: string; html: string } {
  return trialWarningEmail({ ...params, daysRemaining: 1 });
}
