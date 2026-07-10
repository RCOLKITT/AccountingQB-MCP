import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  bulletList,
  infoBox,
} from "./base";

interface WelcomeEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
  trialDays: number;
}

export function welcomeEmail(params: WelcomeEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const setupUrl = `${appUrl}/setup-wizard?key=${params.licenseKey}`;
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;

  const tierName =
    params.tier === "solopreneur"
      ? "Solopreneur"
      : params.tier === "business"
        ? "Business"
        : "Firm";

  const content = `
    ${heading("Welcome to AccountingQB!")}

    ${paragraph(`Thanks for starting your ${params.trialDays}-day free trial of AccountingQB ${tierName}. You're about to transform how you work with QuickBooks.`)}

    ${paragraph("Let's get you set up:")}

    ${primaryButton("Complete Setup (5 min)", setupUrl)}

    ${bulletList([
      "<strong>Fastest option:</strong> Add AccountingQB as a connector in Claude (Settings &rarr; Connectors) — no install needed",
      "<strong>Step 1:</strong> Install Claude Desktop (if you haven't already)",
      "<strong>Step 2:</strong> Run our setup wizard to configure the MCP server",
      "<strong>Step 3:</strong> Connect your QuickBooks Online company",
      "<strong>Step 4:</strong> Start asking Claude about your books!",
    ])}

    ${infoBox("Run AccountingQB locally and your books never touch our servers — or use our zero-retention connector. Either way we never store your financial data.", "info")}

    ${paragraph(`<strong>Your License Key:</strong><br><code style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-family: monospace; color: #22d3ee;">${params.licenseKey}</code>`)}

    ${paragraph("Need help? Just reply to this email or use the chat widget on our site.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  return {
    subject: `Welcome to AccountingQB — Let's get you set up`,
    html: emailWrapper(
      content,
      `Start your ${params.trialDays}-day free trial of AccountingQB`
    ),
  };
}
