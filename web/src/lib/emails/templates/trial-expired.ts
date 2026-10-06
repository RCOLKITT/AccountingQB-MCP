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

    ${paragraph("Your reports, tax tools, and bookkeeping are paused until you pick a plan. Your QuickBooks stays connected and your data is untouched — we never store your books — so everything switches back on the moment you subscribe.")}

    ${paragraph("Want your full AccountingQB back — reports, tax prep, the deduction finder, and all 138 tools? Pick a plan anytime:")}

    ${primaryButton("Choose a plan", pricingUrl)}

    ${paragraph("Not ready? No worries — your license key stays valid whenever you want to come back.")}

    ${paragraph("I'd genuinely love your feedback — what could we have done better? Just reply to this email.")}

    ${paragraph("— Ryan @ AccountingQB")}
  `;

  return {
    subject: `Your AccountingQB trial has ended`,
    html: emailWrapper(
      content,
      `Your trial has ended — your reports & tools are paused; pick a plan anytime to switch all 138 back on`,
    ),
  };
}
