import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/oauth/callback
 * Handles the QuickBooks OAuth 2.0 callback.
 *
 * This endpoint:
 * 1. Exchanges the authorization code for access + refresh tokens
 * 2. Returns tokens to the user's local MCP server (NOT stored on our servers)
 * 3. Redirects to a success page with instructions
 *
 * The tokens are displayed once for the user to copy into their local config.
 * We never persist QuickBooks tokens server-side — zero-knowledge architecture.
 */
export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code");
  const realmId = req.nextUrl.searchParams.get("realmId");
  const stateParam = req.nextUrl.searchParams.get("state");
  const errorParam = req.nextUrl.searchParams.get("error");

  // Handle OAuth errors
  if (errorParam) {
    const errorDesc = req.nextUrl.searchParams.get("error_description") || "Unknown error";
    return buildErrorPage(`QuickBooks authorization failed: ${errorDesc}`);
  }

  if (!code || !realmId) {
    return buildErrorPage("Missing authorization code or realm ID.");
  }

  // Decode state
  let licenseKey = "";
  if (stateParam) {
    try {
      const decoded = JSON.parse(
        Buffer.from(stateParam, "base64url").toString()
      );
      licenseKey = decoded.licenseKey || "";
    } catch {
      // State decode failed — non-critical, continue
    }
  }

  // Exchange code for tokens
  const clientId = process.env.QB_CLIENT_ID!;
  const clientSecret = process.env.QB_CLIENT_SECRET!;
  const redirectUri = process.env.QB_REDIRECT_URI!;

  const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  let tokenData;
  try {
    const tokenRes = await fetch("https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Basic ${basicAuth}`,
        "Accept": "application/json",
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code,
        redirect_uri: redirectUri,
      }),
    });

    if (!tokenRes.ok) {
      const errBody = await tokenRes.text();
      console.error("Token exchange failed:", errBody);
      return buildErrorPage("Failed to exchange authorization code for tokens.");
    }

    tokenData = await tokenRes.json();
  } catch (err) {
    console.error("Token exchange error:", err);
    return buildErrorPage("Network error during token exchange.");
  }

  // Build success page with credentials for local setup
  // IMPORTANT: We display these ONCE. We do NOT store them server-side.
  return buildSuccessPage({
    realmId,
    refreshToken: tokenData.refresh_token,
    accessToken: tokenData.access_token,
    licenseKey,
  });
}

function buildErrorPage(message: string) {
  const html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Connection Failed</title>
<style>body{font-family:system-ui,sans-serif;max-width:600px;margin:80px auto;padding:0 20px;text-align:center}
.error{background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:32px;margin-top:24px}
h1{color:#dc2626}</style></head>
<body>
<h1>Connection Failed</h1>
<div class="error"><p>${escapeHtml(message)}</p>
<p>Please close this window and try again from Claude Desktop.</p></div>
</body></html>`;
  return new NextResponse(html, {
    status: 400,
    headers: { "Content-Type": "text/html" },
  });
}

function buildSuccessPage(creds: {
  realmId: string;
  refreshToken: string;
  accessToken: string;
  licenseKey: string;
}) {
  const html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>QuickBooks Connected!</title>
<style>
body{font-family:system-ui,sans-serif;max-width:700px;margin:40px auto;padding:0 20px;color:#1e293b}
.success{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:32px;margin:24px 0}
.cred-box{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:12px 0;
font-family:monospace;font-size:13px;word-break:break-all;position:relative}
.cred-label{font-weight:600;font-family:system-ui,sans-serif;font-size:14px;margin-bottom:6px;color:#475569}
.copy-btn{position:absolute;top:8px;right:8px;background:#3b82f6;color:white;border:none;
border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer}
.copy-btn:hover{background:#2563eb}
.warning{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:16px;margin:24px 0;font-size:14px}
h1{color:#16a34a}
.step{margin:20px 0;padding-left:28px;position:relative}
.step::before{content:attr(data-step);position:absolute;left:0;font-weight:bold;color:#3b82f6}
</style>
<script>
function copyText(id){
  const el=document.getElementById(id);
  navigator.clipboard.writeText(el.textContent.trim());
  const btn=el.parentElement.querySelector('.copy-btn');
  btn.textContent='Copied!';
  setTimeout(()=>btn.textContent='Copy',1500);
}
</script>
</head>
<body>
<h1>QuickBooks Connected Successfully!</h1>

<div class="success">
<p>Your QuickBooks account has been authorized. Copy the credentials below into your Claude Desktop MCP configuration.</p>
</div>

<div class="warning">
<strong>Important:</strong> These credentials are shown <strong>once</strong> and are NOT stored on our servers.
Copy them now. If you lose them, you'll need to re-authorize.
</div>

<div class="cred-label">Company ID (Realm ID)</div>
<div class="cred-box"><button class="copy-btn" onclick="copyText('realm')">Copy</button>
<div id="realm">${escapeHtml(creds.realmId)}</div></div>

<div class="cred-label">Refresh Token</div>
<div class="cred-box"><button class="copy-btn" onclick="copyText('refresh')">Copy</button>
<div id="refresh">${escapeHtml(creds.refreshToken)}</div></div>

<h2 style="margin-top:32px">Setup Instructions</h2>

<div class="step" data-step="1.">Open Claude Desktop → Settings → MCP Servers</div>
<div class="step" data-step="2.">Find <strong>QuickBooks Accounting</strong> and click Configure</div>
<div class="step" data-step="3.">Paste the <strong>Realm ID</strong> into the Company ID field</div>
<div class="step" data-step="4.">Paste the <strong>Refresh Token</strong> into the Refresh Token field</div>
<div class="step" data-step="5.">Click Save — you're ready to go!</div>

${creds.licenseKey ? `<p style="margin-top:24px;font-size:14px;color:#64748b">License: ${escapeHtml(creds.licenseKey)}</p>` : ""}

<p style="margin-top:32px;text-align:center;color:#94a3b8;font-size:13px">
You can safely close this window after copying your credentials.
</p>
</body></html>`;

  return new NextResponse(html, {
    headers: { "Content-Type": "text/html" },
  });
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
