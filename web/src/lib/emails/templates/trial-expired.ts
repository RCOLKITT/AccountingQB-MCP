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
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;

  const content = `
    ${heading("Your AccountingQB trial has ended")}

    ${paragraph("Your 14-day free trial of AccountingQB has come to an end.")}

    ${paragraph("Your QuickBooks data remains safe and unchanged — we never store your financial information. If you connected companies during your trial, those connections have been paused.")}

    ${paragraph("If you'd like to continue using AccountingQB:")}

    ${primaryButton("Reactivate Subscription", dashboardUrl)}

    ${paragraph("Not ready to subscribe? No worries. Your license key will remain valid if you decide to come back later.")}

    ${paragraph("I'd love to hear your feedback — what could we have done better? Just reply to this email.")}

    ${paragraph("— Ryan @ AccountingQB")}
  `;

  return {
    subject: `Your AccountingQB trial has ended`,
    html: emailWrapper(
      content,
      `Your trial has ended — reactivate anytime to continue using AccountingQB`
    ),
  };
}
