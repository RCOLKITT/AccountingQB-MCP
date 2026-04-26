/**
 * Base email template wrapper
 * All emails use this consistent layout
 */
export function emailWrapper(content: string, preheader?: string): string {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>AccountingQB</title>
  ${preheader ? `<meta name="description" content="${preheader}">` : ""}
  <!--[if mso]>
  <style type="text/css">
    body, table, td {font-family: Arial, sans-serif !important;}
  </style>
  <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #0a0e1a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  ${preheader ? `<div style="display: none; max-height: 0; overflow: hidden;">${preheader}</div>` : ""}

  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0e1a;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width: 600px;">

          <!-- Logo -->
          <tr>
            <td align="center" style="padding-bottom: 32px;">
              <span style="font-size: 24px; font-weight: 700; color: #22d3ee; letter-spacing: -0.5px;">
                Accounting<span style="color: #3b82f6;">QB</span>
              </span>
            </td>
          </tr>

          <!-- Main Content Card -->
          <tr>
            <td style="background-color: #131a2e; border-radius: 12px; border: 1px solid rgba(255,255,255,0.06);">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding: 40px;">
                    ${content}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding-top: 32px; text-align: center;">
              <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 12px;">
                AccountingQB — AI-Powered QuickBooks for Claude
              </p>
              <p style="margin: 0; color: #6b7280; font-size: 12px;">
                Questions? Reply to this email or visit
                <a href="https://accountingqb.com" style="color: #22d3ee; text-decoration: none;">accountingqb.com</a>
              </p>
              <p style="margin: 16px 0 0 0; color: #4b5563; font-size: 11px;">
                Vaspera Capital LLC · 2025
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
`.trim();
}

/**
 * Primary CTA button
 */
export function primaryButton(text: string, href: string): string {
  return `
<table role="presentation" cellspacing="0" cellpadding="0" style="margin: 24px 0;">
  <tr>
    <td style="background: linear-gradient(135deg, #22d3ee 0%, #3b82f6 100%); border-radius: 8px;">
      <a href="${href}" style="display: inline-block; padding: 14px 28px; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none;">
        ${text}
      </a>
    </td>
  </tr>
</table>
`.trim();
}

/**
 * Secondary/outline button
 */
export function secondaryButton(text: string, href: string): string {
  return `
<table role="presentation" cellspacing="0" cellpadding="0" style="margin: 16px 0;">
  <tr>
    <td style="border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;">
      <a href="${href}" style="display: inline-block; padding: 12px 24px; color: #d1d5db; font-size: 14px; font-weight: 500; text-decoration: none;">
        ${text}
      </a>
    </td>
  </tr>
</table>
`.trim();
}

/**
 * Info box for important notices
 */
export function infoBox(content: string, type: "info" | "warning" | "success" = "info"): string {
  const colors = {
    info: { bg: "rgba(34,211,238,0.1)", border: "#22d3ee", text: "#22d3ee" },
    warning: { bg: "rgba(251,191,36,0.1)", border: "#fbbf24", text: "#fbbf24" },
    success: { bg: "rgba(34,197,94,0.1)", border: "#22c55e", text: "#22c55e" },
  };
  const c = colors[type];

  return `
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 24px 0;">
  <tr>
    <td style="background-color: ${c.bg}; border-left: 3px solid ${c.border}; border-radius: 4px; padding: 16px;">
      <p style="margin: 0; color: ${c.text}; font-size: 14px; line-height: 1.5;">
        ${content}
      </p>
    </td>
  </tr>
</table>
`.trim();
}

/**
 * Heading styles
 */
export function heading(text: string): string {
  return `<h1 style="margin: 0 0 16px 0; color: #ffffff; font-size: 24px; font-weight: 600; line-height: 1.3;">${text}</h1>`;
}

export function subheading(text: string): string {
  return `<h2 style="margin: 24px 0 12px 0; color: #ffffff; font-size: 18px; font-weight: 600;">${text}</h2>`;
}

/**
 * Paragraph text
 */
export function paragraph(text: string): string {
  return `<p style="margin: 0 0 16px 0; color: #d1d5db; font-size: 15px; line-height: 1.6;">${text}</p>`;
}

/**
 * Bullet list
 */
export function bulletList(items: string[]): string {
  const listItems = items
    .map(
      (item) =>
        `<li style="margin-bottom: 8px; color: #d1d5db; font-size: 14px; line-height: 1.5;">${item}</li>`
    )
    .join("");

  return `
<ul style="margin: 16px 0; padding-left: 20px;">
  ${listItems}
</ul>
`.trim();
}
