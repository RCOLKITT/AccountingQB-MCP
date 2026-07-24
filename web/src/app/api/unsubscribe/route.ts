import { NextRequest, NextResponse } from "next/server";
import { verifyUnsubscribe, suppress } from "@/lib/emails/unsubscribe";

// One-click unsubscribe (CAN-SPAM / CASL). GET renders a confirmation page;
// POST supports RFC 8058 one-click (List-Unsubscribe-Post) from mail clients.
// Token is an HMAC of the email, so no login and no tampering.

async function handle(email: string, token: string): Promise<boolean> {
  if (!email || !token || !verifyUnsubscribe(email, token)) return false;
  await suppress(email, "link");
  return true;
}

function page(ok: boolean, email: string): string {
  const msg = ok
    ? `<strong>${email}</strong> has been unsubscribed from AccountingQB marketing emails. You'll still receive essential account emails (receipts, security, trial status).`
    : `We couldn't process this unsubscribe link. Please email <a href="mailto:support@vasperacapital.com">support@vasperacapital.com</a> and we'll remove you right away.`;
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Unsubscribe · AccountingQB</title></head>
<body style="margin:0;background:#0a0e1a;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#e5e7eb">
<div style="max-width:520px;margin:80px auto;padding:40px;background:#131a2e;border:1px solid rgba(255,255,255,.1);border-radius:16px;text-align:center">
<div style="font-size:24px;font-weight:700;margin-bottom:24px">Accounting<span style="color:#22d3ee">QB</span></div>
<p style="font-size:15px;line-height:1.6;color:#d1d5db">${msg}</p>
<a href="https://accountingqb.com" style="display:inline-block;margin-top:24px;color:#22d3ee;font-size:14px;text-decoration:none">Return to accountingqb.com →</a>
</div></body></html>`;
}

export async function GET(req: NextRequest) {
  const email = (req.nextUrl.searchParams.get("e") || "").trim().toLowerCase();
  const token = req.nextUrl.searchParams.get("t") || "";
  const ok = await handle(email, token);
  return new NextResponse(page(ok, email), {
    status: ok ? 200 : 400,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

export async function POST(req: NextRequest) {
  // RFC 8058 one-click: mail clients POST here directly.
  const email = (req.nextUrl.searchParams.get("e") || "").trim().toLowerCase();
  const token = req.nextUrl.searchParams.get("t") || "";
  const ok = await handle(email, token);
  return NextResponse.json({ unsubscribed: ok });
}
