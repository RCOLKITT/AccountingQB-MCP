import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  bulletList,
  infoBox,
} from "./base";

interface QbConnectedEmailParams {
  email: string;
  licenseKey: string;
  companyName: string;
}

export function qbConnectedEmail(params: QbConnectedEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;

  const content = `
    ${heading("QuickBooks Connected!")}

    ${paragraph(`Great news! <strong>${params.companyName}</strong> is now connected to AccountingQB. You're ready to start using AI-powered accounting.`)}

    ${infoBox("Your connection is secure and we never store your books. Run locally and Claude accesses QuickBooks directly from your machine; use our hosted connector and data passes through with zero retention.", "success")}

    ${paragraph("Here are some things to try in Claude:")}

    ${bulletList([
      '"Show me my P&L for last month"',
      '"What were my top 10 expenses this quarter?"',
      '"Reconcile my bank account"',
      '"Help me categorize these transactions"',
      '"Generate a Schedule C summary for taxes"',
      '"Prepare my GST/HST return workpaper for last quarter"',
    ])}

    ${primaryButton("View Dashboard", dashboardUrl)}

    ${paragraph("Just open Claude Desktop and start asking questions about your books. AccountingQB gives Claude 136 tools to help with everything from reports to reconciliation.")}

    ${paragraph("Questions? Reply to this email anytime.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  return {
    subject: `${params.companyName} connected to AccountingQB`,
    html: emailWrapper(
      content,
      `Your QuickBooks company is now connected and ready to use`,
    ),
  };
}
