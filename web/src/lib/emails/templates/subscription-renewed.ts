import { emailWrapper, heading, paragraph, primaryButton } from "./base";
import { formatDate, formatCurrency, getTierDisplayName } from "../send-email";

interface SubscriptionRenewedEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
  amountCents: number;
  cardLastFour?: string;
  cardBrand?: string;
  nextBillingDate: string;
  invoiceUrl?: string;
}

export function subscriptionRenewedEmail(
  params: SubscriptionRenewedEmailParams,
): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const dashboardUrl = `${appUrl}/dashboard?key=${params.licenseKey}`;

  const amount = formatCurrency(params.amountCents);
  const tierName = getTierDisplayName(params.tier);
  const nextDate = formatDate(params.nextBillingDate);
  const cardInfo = params.cardLastFour
    ? `${params.cardBrand || "Card"} ending in ${params.cardLastFour}`
    : "your payment method";

  const content = `
    ${heading("Payment received — thank you!")}

    ${paragraph(`Your AccountingQB ${tierName} subscription has been renewed.`)}

    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 24px 0; background-color: rgba(255,255,255,0.03); border-radius: 8px;">
      <tr>
        <td style="padding: 20px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="color: #9ca3af; font-size: 14px;">Amount</span>
              </td>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: right;">
                <span style="color: #ffffff; font-size: 14px; font-weight: 600;">${amount}</span>
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="color: #9ca3af; font-size: 14px;">Plan</span>
              </td>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: right;">
                <span style="color: #ffffff; font-size: 14px;">${tierName}</span>
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="color: #9ca3af; font-size: 14px;">Payment method</span>
              </td>
              <td style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: right;">
                <span style="color: #ffffff; font-size: 14px;">${cardInfo}</span>
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 0;">
                <span style="color: #9ca3af; font-size: 14px;">Next billing date</span>
              </td>
              <td style="padding: 8px 0; text-align: right;">
                <span style="color: #ffffff; font-size: 14px;">${nextDate}</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    ${
      params.invoiceUrl
        ? `<p style="margin: 0 0 24px 0;"><a href="${params.invoiceUrl}" style="color: #22d3ee; font-size: 14px; text-decoration: none;">View invoice →</a></p>`
        : ""
    }

    ${primaryButton("Open Dashboard", dashboardUrl)}

    ${paragraph("Thanks for using AccountingQB! If you have any questions, just reply to this email.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  return {
    subject: `Receipt: AccountingQB ${tierName} — ${amount}`,
    html: emailWrapper(
      content,
      `Your AccountingQB subscription has been renewed for ${amount}`,
    ),
  };
}
