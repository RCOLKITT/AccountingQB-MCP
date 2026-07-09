import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  infoBox,
} from "./base";

interface ReengagementEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
}

export function reengagementEmail(params: ReengagementEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const setupUrl = `${appUrl}/setup-wizard?key=${params.licenseKey}`;

  const content = `
    ${heading("Your license is ready — let's finish setup")}

    ${paragraph("Good news: we just fixed an issue with our account setup flow that may have stopped you from getting started. Everything is working now, and your AccountingQB license is active and waiting.")}

    ${paragraph(`<strong>Your License Key:</strong><br><code style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-family: monospace; color: #22d3ee;">${params.licenseKey}</code>`)}

    ${primaryButton("Finish Setup (2 min)", setupUrl)}

    ${infoBox(`Once connected, just ask Claude: "What's my P&L this quarter?" — and get an answer straight from your QuickBooks data.`, "info")}

    ${paragraph("Need a hand? Just reply to this email and we'll get you sorted.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  return {
    subject: `Your AccountingQB license is ready — 2 minutes to your first report`,
    html: emailWrapper(
      content,
      "Your license is active — finish setup in 2 minutes"
    ),
  };
}
