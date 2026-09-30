import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { ensureTrialLicenseForEmail } from "@/lib/license-issuance";
import {
  getTrialStartLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * POST /api/trial/start  { email, platform?, tier? }
 *
 * Turns a desktop-app download into a TRACKED, no-credit-card trial: captures
 * the email, mints (or reuses) a 14-day trialing license, and returns a
 * download URL tagged with the license key so app_downloads is attributable.
 *
 * Production-safety:
 *  - The lead (email) is written to event_logs FIRST, so even if license
 *    issuance fails the visitor is never fully untracked.
 *  - A download is NEVER blocked: on issuance failure we still return a
 *    (key-less) download URL and log an incident.
 *  - Kill switch: TRIAL_AT_DOWNLOAD_ENABLED="false" disables trial creation and
 *    returns a plain download URL (the client reverts to a direct download).
 */
const PLATFORMS = new Set(["macos", "windows"]);
const TIERS = new Set(["solopreneur", "business", "firm"]);
// Intentionally simple: reject obvious non-emails; real validation is the
// delivered key email. Not a security boundary.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function downloadPath(platform: string, key?: string | null): string {
  const base = `/api/download/${platform}`;
  return key ? `${base}?key=${encodeURIComponent(key)}` : base;
}

export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getTrialStartLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }

  let body: { email?: string; platform?: string; tier?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const email = (body.email || "").trim();
  const platform = PLATFORMS.has(body.platform || "")
    ? (body.platform as string)
    : "macos";
  const tier = TIERS.has(body.tier || "")
    ? (body.tier as string)
    : "solopreneur";

  if (!EMAIL_RE.test(email)) {
    return NextResponse.json({ error: "invalid_email" }, { status: 400 });
  }

  const supabase = getSupabase();
  const nowIso = new Date().toISOString();

  // Durable lead capture FIRST — this row means "we know this visitor" even if
  // license issuance below fails. Best-effort; never block the flow on it.
  try {
    await supabase.from("event_logs").insert({
      event_type: "trial",
      action: "trial_start",
      payload: {
        email: email.toLowerCase(),
        platform,
        tier,
        source: "download",
      },
      success: true,
      processed_at: nowIso,
    });
  } catch (err) {
    console.error("trial lead capture failed:", err);
  }

  // Kill switch → skip trial creation, hand back a plain download.
  if (process.env.TRIAL_AT_DOWNLOAD_ENABLED === "false") {
    return NextResponse.json({ ok: true, downloadUrl: downloadPath(platform) });
  }

  // Issue (or reuse) the trial license — one retry to ride out a transient blip.
  let result = await ensureTrialLicenseForEmail(
    supabase,
    email,
    tier,
    "download",
  );
  if (!result) {
    result = await ensureTrialLicenseForEmail(
      supabase,
      email,
      tier,
      "download",
    );
  }

  if (!result) {
    // Issuance failed twice. The lead is already captured above, so the visitor
    // is tracked; let the download proceed (key-less) and flag for follow-up.
    try {
      await supabase.from("event_logs").insert({
        event_type: "trial",
        action: "trial_start_issue_failed",
        payload: { email: email.toLowerCase(), platform, tier },
        success: false,
        error_message: "ensureTrialLicenseForEmail returned null twice",
        processed_at: nowIso,
      });
    } catch {
      /* already logged upstream */
    }
    return NextResponse.json({ ok: true, downloadUrl: downloadPath(platform) });
  }

  return NextResponse.json({
    ok: true,
    licenseKey: result.licenseKey,
    created: result.created,
    downloadUrl: downloadPath(platform, result.licenseKey),
  });
}
