import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  infoBox,
} from "./base";
import { formatCurrency, getTierPriceCents } from "../send-email";

interface PaymentFailedEmailParams {
  email: string;
  licenseKey: string;
  tier: string;
  cardLastFour?: string;
  cardBrand?: string;
  attemptCount?: number;
}

export function paymentFailedEmail(params: PaymentFailedEmailParams): {
  subject: string;
  html: string;
} {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://accountingqb.com";
  const billingUrl = `${appUrl}/dashboard/settings?key=${params.licenseKey}`;

  const price = formatCurrency(getTierPriceCents(params.tier));
  const cardInfo = params.cardLastFour
    ? `${params.cardBrand || "Card"} ending in ${params.cardLastFour}`
    : "Your payment method";

  const isFirstAttempt = !params.attemptCount || params.attemptCount <= 1;

  const content = `
    ${heading("Payment failed")}

    ${paragraph(`We couldn't process your ${price} payment for AccountingQB.`)}

    ${infoBox(
      `<strong>${cardInfo}</strong> was declined.<br>
      This could be due to insufficient funds, an expired card, or your bank blocking the charge.`,
      "warning",
    )}

    ${paragraph("Please update your payment method to keep your subscription active:")}

    ${primaryButton("Update Payment Method", billingUrl)}

    ${paragraph(
      isFirstAttempt
        ? "We'll automatically retry the payment in a few days. To avoid any interruption, please update your card as soon as possible."
        : "This is a follow-up notice. Your subscription may be paused if we can't process payment soon.",
    )}

    ${paragraph("If you're having trouble or want to cancel, just reply to this email.")}

    ${paragraph("— The AccountingQB Team")}
  `;

  return {
    subject: `⚠️ Payment failed for AccountingQB`,
    html: emailWrapper(
      content,
      `We couldn't process your ${price} payment — please update your card`,
    ),
  };
}
