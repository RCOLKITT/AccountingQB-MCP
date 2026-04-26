import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  secondaryButton,
  bulletList,
  infoBox,
} from "./base";

interface Day3CheckinEmailParams {
  email: string;
  licenseKey: string;
  hasQbConnected: boolean;
}

export function day3CheckinEmail(params: Day3CheckinEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const setupUrl = `${appUrl}/setup-wizard?key=${params.licenseKey}`;
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;

  // Different content based on whether they've connected QB
  if (params.hasQbConnected) {
    const content = `
      ${heading("How's it going with AccountingQB?")}

      ${paragraph("It's been a few days since you connected QuickBooks — just checking in to see how things are going!")}

      ${paragraph("Have you tried asking Claude:")}

      ${bulletList([
        '"What were my biggest expenses last month?"',
        '"Show me unpaid invoices over 30 days"',
        '"Help me reconcile my checking account"',
        '"Generate a cash flow summary"',
      ])}

      ${primaryButton("Open Dashboard", dashboardUrl)}

      ${paragraph("If you're running into any issues or have questions, just reply to this email. We're here to help.")}

      ${paragraph("— The AccountingQB Team")}
    `;

    return {
      subject: `How's AccountingQB working for you?`,
      html: emailWrapper(content, `Quick check-in on your AccountingQB trial`),
    };
  }

  // They haven't connected QB yet
  const content = `
    ${heading("Need help getting set up?")}

    ${paragraph("I noticed you haven't connected QuickBooks yet — no worries, I wanted to check in and see if you need any help.")}

    ${infoBox("Setup usually takes about 5 minutes. Most issues are quick fixes — just reply if you're stuck!", "info")}

    ${paragraph("Common setup questions:")}

    ${bulletList([
      "<strong>Where is Claude Desktop?</strong> — Download it at claude.ai/download",
      "<strong>uvx not found?</strong> — Run: <code>curl -LsSf https://astral.sh/uv/install.sh | sh</code>",
      "<strong>JSON config error?</strong> — Our wizard validates your config automatically",
      "<strong>OAuth not working?</strong> — Make sure you're logged into QuickBooks in your browser first",
    ])}

    ${primaryButton("Complete Setup", setupUrl)}

    ${secondaryButton("Schedule a Call", "mailto:support@vasperacapital.com?subject=AccountingQB Setup Help")}

    ${paragraph("Seriously, just reply to this email if something isn't working. I'm happy to hop on a quick call to help you get set up.")}

    ${paragraph("— Ryan @ AccountingQB")}
  `;

  return {
    subject: `Need help setting up AccountingQB?`,
    html: emailWrapper(
      content,
      `I noticed you haven't connected QuickBooks yet — can I help?`
    ),
  };
}
