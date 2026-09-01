import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  secondaryButton,
  bulletList,
} from "./base";

interface TrialExpiredEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
}

export function trialExpiredEmail(params: TrialExpiredEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const pricingUrl = `${appUrl}/pricing`;

  const content = `
    ${heading("Your AccountingQB trial has ended")}

    ${paragraph("Your 14-day free trial has come to an end — and since you didn't add a card, you were never charged.")}

    ${paragraph("You're now on our <strong>free read-only plan</strong>: you keep 25 essential tools for reports and lookups. Your QuickBooks data stays safe and unchanged — we never store your financial information.")}

    ${paragraph("Want the full 133 tools back — writes, tax prep, and the deduction finder? Pick a plan anytime:")}

    ${primaryButton("Choose a plan", pricingUrl)}

    ${paragraph("Not ready? No worries — your license key stays valid whenever you want to come back.")}

    ${paragraph("I'd genuinely love your feedback — what could we have done better? Just reply to this email.")}

    ${paragraph("— Ryan @ AccountingQB")}
  `;

  return {
    subject: `Your AccountingQB trial has ended`,
    html: emailWrapper(
      content,
      `Your trial has ended — you're on the free plan; pick a plan anytime to unlock all 133 tools`,
    ),
  };
}
