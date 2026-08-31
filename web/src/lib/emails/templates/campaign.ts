import {
  emailWrapper,
  heading,
  paragraph,
  primaryButton,
  bulletList,
} from "./base";
import { unsubscribeUrl } from "../unsubscribe";

// A custom (AI-drafted or hand-written) marketing email. The composer supplies
// the COPY as structured fields; this renders it in the branded template and
// attaches the compliant marketing footer (unsubscribe + address). Keeping copy
// and styling separate guarantees on-brand output regardless of who wrote it.

export interface CampaignContent {
  subject: string;
  preheader?: string;
  headline?: string;
  paragraphs?: string[];
  bullets?: string[];
  ctaText?: string;
  ctaUrl?: string;
  signoff?: string; // e.g. "— Ryan, AccountingQB"
}

export function renderCampaignBody(c: CampaignContent): string {
  const parts: string[] = [];
  if (c.headline) parts.push(heading(c.headline));
  for (const p of c.paragraphs || []) parts.push(paragraph(p));
  if (c.bullets && c.bullets.length) parts.push(bulletList(c.bullets));
  if (c.ctaText && c.ctaUrl) parts.push(primaryButton(c.ctaText, c.ctaUrl));
  if (c.signoff) parts.push(paragraph(c.signoff));
  return parts.join("\n");
}

/** Full branded HTML for a campaign email to a specific recipient. */
export function campaignEmail(
  c: CampaignContent,
  recipientEmail: string,
): { subject: string; html: string } {
  return {
    subject: c.subject,
    html: emailWrapper(renderCampaignBody(c), c.preheader, {
      unsubscribeUrl: unsubscribeUrl(recipientEmail),
    }),
  };
}
