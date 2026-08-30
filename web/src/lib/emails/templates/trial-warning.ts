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
  const addCardUrl = `${appUrl}/api/stripe/portal?key=${params.licenseKey}`;

  const tierName =
    params.tier === "solopreneur"
      ? "Solopreneur"
      : params.tier === "business"
        ? "Business"
        : "Firm";

  const price = formatCurrency(getTierPriceCents(params.tier));
  const trialEndDate = formatDate(params.trialEndsAt);

  const urgency = params.daysRemaining === 1 ? "tomorrow" : "in 4 days";
  const isUrgent = params.daysRemaining === 1;

  // Trials are no-card by default: unless a card was added, nothing is charged and
  // the trial simply ends. Only send the "you'll be charged automatically" version
  // when we actually have a card on file for this license.
  const hasCard = Boolean(params.cardLastFour);

  let content: string;
  let subject: string;
  let preheader: string;

  if (hasCard) {
    const cardInfo = `${params.cardBrand || "Card"} ending in ${params.cardLastFour}`;
    content = `
      ${heading(`Your trial ends ${urgency}`)}

      ${paragraph(`Your AccountingQB ${tierName} trial ends on <strong>${trialEndDate}</strong>.`)}

      ${infoBox(
        `<strong>What happens next:</strong><br>
        • Your ${cardInfo} will be charged <strong>${price}/month</strong><br>
        • The charge will appear as "ACCOUNTINGQB" on your statement<br>
        • You can cancel anytime before ${trialEndDate} to avoid charges`,
        isUrgent ? "warning" : "info",
      )}

      ${paragraph("Want to continue? Great — no action needed. Your subscription will start automatically.")}

      ${paragraph("Need to cancel? No problem:")}

      ${secondaryButton("Cancel Subscription", cancelUrl)}

      ${paragraph("Or simply reply to this email and I'll take care of it.")}

      ${primaryButton("View Dashboard", dashboardUrl)}

      ${paragraph("Questions about billing or want to change your plan? Just reply to this email.")}

      ${paragraph("— The AccountingQB Team")}
    `;
    subject =
      params.daysRemaining === 1
        ? `⚠️ Your AccountingQB trial ends tomorrow`
        : `Your AccountingQB trial ends in 4 days`;
    preheader =
      params.daysRemaining === 1
        ? `Your card will be charged ${price} tomorrow — cancel anytime before then`
        : `Your trial ends on ${trialEndDate} — here's what happens next`;
  } else {
    // No card on file → the honest no-card path. To keep the plan, add a card;
    // otherwise the trial just ends and they move to the free read-only plan.
    content = `
      ${heading(`Your trial ends ${urgency}`)}

      ${paragraph(`Your AccountingQB ${tierName} trial ends on <strong>${trialEndDate}</strong>. You started it without a card, so nothing will be charged.`)}

      ${infoBox(
        `<strong>To keep your ${tierName} plan (${price}/month):</strong> add a card before ${trialEndDate}.<br><br>
        <strong>Prefer not to?</strong> Do nothing. Your trial simply ends, you move to our free read-only plan, and you're never charged — there's nothing to cancel.`,
        isUrgent ? "warning" : "info",
      )}

      ${primaryButton("Add a card to keep your plan", addCardUrl)}

      ${paragraph("Your QuickBooks data stays safe either way — we never store your books.")}

      ${secondaryButton("View Dashboard", dashboardUrl)}

      ${paragraph("Questions, or want a hand deciding on a plan? Just reply to this email.")}

      ${paragraph("— Ryan @ AccountingQB")}
    `;
    subject =
      params.daysRemaining === 1
        ? `Your AccountingQB trial ends tomorrow — add a card to keep it`
        : `Your AccountingQB trial ends in 4 days`;
    preheader =
      params.daysRemaining === 1
        ? `Add a card before tomorrow to keep your plan — otherwise the trial just ends, no charge`
        : `Add a card to keep your plan when the trial ends on ${trialEndDate} — otherwise it ends free`;
  }

  return {
    subject,
    html: emailWrapper(content, preheader),
  };
}

export function trialWarning4DayEmail(
  params: Omit<TrialWarningEmailParams, "daysRemaining">,
): { subject: string; html: string } {
  return trialWarningEmail({ ...params, daysRemaining: 4 });
}

export function trialWarning1DayEmail(
  params: Omit<TrialWarningEmailParams, "daysRemaining">,
): { subject: string; html: string } {
  return trialWarningEmail({ ...params, daysRemaining: 1 });
}
