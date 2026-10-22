import { NextRequest, NextResponse } from "next/server";
import { logEvent } from "@/lib/event-logger";
import { sendAlert } from "@/lib/alerts";
import {
  getCheckoutLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * POST /api/privacy/request  { email, type, message? }
 *
 * Data-subject request intake (GDPR / CCPA / PIPEDA): access, deletion,
 * correction, export, or other. We record the request to the audit trail
 * (event_logs) and alert ops so it is actioned within our stated SLA. This is
 * the intake — fulfillment is handled by a human within 30 days; it is NOT an
 * automated self-serve delete (that is a tracked follow-up).
 */
const TYPES = new Set(["access", "delete", "correction", "export", "other"]);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getCheckoutLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }

  let body: { email?: string; type?: string; message?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const email = (body.email || "").trim().toLowerCase();
  const type = TYPES.has(body.type || "") ? (body.type as string) : "other";
  const message = (body.message || "").slice(0, 2000);

  if (!EMAIL_RE.test(email)) {
    return NextResponse.json({ error: "invalid_email" }, { status: 400 });
  }

  // Durable record on the audit trail (logEvent swallows its own errors).
  await logEvent({
    eventType: "privacy_request",
    action: `dsar:${type}`,
    payload: { email, type, message: message || null },
    success: true,
  });

  // Notify ops so the request is actioned within the stated 30-day SLA.
  await sendAlert("🔒 Data-subject request", [
    `Type: ${type}`,
    `Email: ${email}`,
    message ? `Message: ${message}` : "No message provided.",
    "Action within 30 days; log the fulfillment in event_logs.",
  ]);

  return NextResponse.json({ ok: true });
}
