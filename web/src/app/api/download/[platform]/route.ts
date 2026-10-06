import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";
import { getSupabase } from "@/lib/supabase";
import {
  getDownloadLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * GET /api/download/macos   (or /windows)
 *
 * Trial gate (the single chokepoint for EVERY download link — footer, homepage,
 * FAQ, even a pasted URL): a request with no trial context is redirected to the
 * /download capture page, which collects an email, mints a tracked no-credit-card
 * trial via /api/trial/start, and sends the user back here with `?key=LK-…&g=1`.
 * A request that already carries a license key (or the g=1 "gated already" flag
 * from that page) is recorded and 302'd to the signed GitHub asset. This is why
 * downloads weren't becoming trials — the gate lived only on the homepage buttons
 * while the footer linked straight here. Set TRIAL_AT_DOWNLOAD_ENABLED="false" to
 * disable the gate (every request goes straight to the asset, as before).
 */
const ASSETS: Record<string, string> = {
  macos:
    "https://github.com/RCOLKITT/AccountingQB-MCP/releases/latest/download/AccountingQB-macOS-AppleSilicon.dmg",
  windows:
    "https://github.com/RCOLKITT/AccountingQB-MCP/releases/latest/download/AccountingQB-Windows-Setup.exe",
};
const RELEASES_PAGE =
  "https://github.com/RCOLKITT/AccountingQB-MCP/releases/latest";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ platform: string }> },
) {
  const { platform } = await params;
  const dest = ASSETS[platform];
  if (!dest) {
    // Unknown platform → send them to the releases page rather than 404.
    return NextResponse.redirect(RELEASES_PAGE, 302);
  }

  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getDownloadLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }

  const key = req.nextUrl.searchParams.get("key");
  const hasKey = !!(key && key.startsWith("LK-"));
  // `g=1` is set by the /download capture page after it has already run the
  // trial gate (so a user whose trial issuance hiccuped still gets their
  // download instead of bouncing back — no redirect loop).
  const gatedAlready = req.nextUrl.searchParams.get("g") === "1";
  const gateEnabled = process.env.TRIAL_AT_DOWNLOAD_ENABLED !== "false";

  if (gateEnabled && !hasKey && !gatedAlready) {
    // No trial context → send to the capture page, which mints a tracked trial
    // then returns here with the key. This gates EVERY entry point at once.
    return NextResponse.redirect(
      new URL(
        `/download?platform=${encodeURIComponent(platform)}`,
        req.nextUrl.origin,
      ),
      302,
    );
  }

  // Record the download — privacy-preserving (salted hashes, never raw IP/UA).
  try {
    const ip = getClientIP(req);
    const ua = req.headers.get("user-agent") || "";
    const salt = process.env.IP_HASH_SALT || "";
    const sha = (s: string) => createHash("sha256").update(s).digest("hex");
    await getSupabase()
      .from("app_downloads")
      .insert({
        platform,
        version: req.nextUrl.searchParams.get("v") || null,
        license_key: key && key.startsWith("LK-") ? key : null,
        ip_hash: ip ? sha(ip + salt) : null,
        user_agent_hash: ua ? sha(ua) : null,
        referrer: (req.headers.get("referer") || "").slice(0, 300) || null,
      });
  } catch (err) {
    console.error("download tracking failed:", err);
  }

  return NextResponse.redirect(dest, 302);
}
