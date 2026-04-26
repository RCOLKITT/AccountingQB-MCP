import { Resend } from "resend";

// Lazy initialization to avoid build-time errors
let resend: Resend | null = null;

function getResend(): Resend {
  if (!resend) {
    resend = new Resend(process.env.RESEND_API_KEY);
  }
  return resend;
}

interface LicenseEmailParams {
  to: string;
  licenseKey: string;
  tier: string;
  trialEndsAt: string;
}

export async function sendLicenseEmail({
  to,
  licenseKey,
  tier,
  trialEndsAt,
}: LicenseEmailParams) {
  const tierName = tier.charAt(0).toUpperCase() + tier.slice(1);
  const trialEndDate = new Date(trialEndsAt).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const { data, error } = await getResend().emails.send({
    from: "AccountingQB <noreply@accountingqb.com>",
    to,
    subject: `Your AccountingQB License Key - ${tierName} Plan`,
    html: `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0e1a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0e1a; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px;">
          <!-- Logo -->
          <tr>
            <td align="center" style="padding-bottom: 32px;">
              <span style="font-size: 28px; font-weight: 700; color: #ffffff;">Accounting<span style="background: linear-gradient(135deg, #22d3ee, #3b82f6, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">QB</span></span>
            </td>
          </tr>

          <!-- Main Card -->
          <tr>
            <td style="background: linear-gradient(145deg, #151d30 0%, #0c1222 100%); border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.2); padding: 40px;">

              <!-- Welcome -->
              <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 600; color: #ffffff;">Welcome to AccountingQB!</h1>
              <p style="margin: 0 0 32px 0; font-size: 16px; color: #9ca3af;">Your ${tierName} plan is ready. Here's your license key:</p>

              <!-- License Key Box -->
              <div style="background: rgba(34, 211, 238, 0.1); border: 1px solid rgba(34, 211, 238, 0.3); border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 32px;">
                <p style="margin: 0 0 8px 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #22d3ee;">License Key</p>
                <p style="margin: 0; font-size: 18px; font-family: 'SF Mono', Monaco, 'Courier New', monospace; font-weight: 600; color: #ffffff; word-break: break-all;">${licenseKey}</p>
              </div>

              <!-- Trial Info -->
              <div style="background: rgba(99, 102, 241, 0.1); border-radius: 8px; padding: 16px; margin-bottom: 32px;">
                <p style="margin: 0; font-size: 14px; color: #a5b4fc;">
                  <strong style="color: #ffffff;">14-day free trial</strong> — full access to all 91 tools.<br>
                  Trial ends: ${trialEndDate}
                </p>
              </div>

              <!-- Getting Started -->
              <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #ffffff;">Getting Started (3 Easy Steps)</h2>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width: 32px; height: 32px; background: linear-gradient(135deg, #22d3ee, #3b82f6); border-radius: 50%; text-align: center; vertical-align: middle; color: #ffffff; font-weight: 600; font-size: 14px;">1</td>
                        <td style="padding-left: 16px; color: #d1d5db; font-size: 15px;">
                          <strong style="color: #ffffff;">Install the extension</strong><br>
                          <span style="font-size: 13px; color: #9ca3af;">Click the button below to install in Claude Desktop (one click!)</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width: 32px; height: 32px; background: linear-gradient(135deg, #3b82f6, #6366f1); border-radius: 50%; text-align: center; vertical-align: middle; color: #ffffff; font-weight: 600; font-size: 14px;">2</td>
                        <td style="padding-left: 16px; color: #d1d5db; font-size: 15px;">
                          <strong style="color: #ffffff;">Connect QuickBooks</strong><br>
                          <span style="font-size: 13px; color: #9ca3af;">Authorize access to your QuickBooks Online company</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 12px 0;">
                    <table cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width: 32px; height: 32px; background: linear-gradient(135deg, #6366f1, #10b981); border-radius: 50%; text-align: center; vertical-align: middle; color: #ffffff; font-weight: 600; font-size: 14px;">3</td>
                        <td style="padding-left: 16px; color: #d1d5db; font-size: 15px;">
                          <strong style="color: #ffffff;">Start talking to your books!</strong><br>
                          <span style="font-size: 13px; color: #9ca3af;">Try: "Show me my P&L for last quarter"</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- CTA Buttons -->
              <div style="text-align: center; margin-top: 32px;">
                <a href="https://accountingqb.com/setup-wizard?key=${encodeURIComponent(licenseKey)}" style="display: inline-block; background: linear-gradient(135deg, #22d3ee, #3b82f6, #6366f1); color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; padding: 14px 32px; border-radius: 8px; margin-bottom: 12px;">Start Setup Guide</a>
                <br>
                <a href="https://accountingqb.com/dashboard?key=${encodeURIComponent(licenseKey)}" style="display: inline-block; color: #9ca3af; text-decoration: none; font-size: 13px; margin-top: 8px;">Already set up? Go to Dashboard →</a>
              </div>

              <!-- No Developer Account Needed -->
              <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; padding: 16px; margin-top: 24px; text-align: center;">
                <p style="margin: 0; font-size: 14px; color: #34d399;">
                  <strong>No Intuit developer account needed!</strong><br>
                  <span style="color: #6ee7b7; font-size: 13px;">We handle the OAuth setup for you.</span>
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding-top: 32px; text-align: center;">
              <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280;">Questions? Reply to this email or contact support@vasperacapital.com</p>
              <p style="margin: 0; font-size: 12px; color: #4b5563;">
                AccountingQB by Vaspera Capital<br>
                <a href="https://accountingqb.com" style="color: #3b82f6; text-decoration: none;">accountingqb.com</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
    `,
  });

  if (error) {
    console.error("Failed to send license email:", error);
    throw error;
  }

  return data;
}
