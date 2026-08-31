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
 * Records the download (platform + salted hashes, non-blocking) then 302s to the
 * signed GitHub "latest" release asset. Site download buttons point here so we can
 * track macOS vs Windows demand in /admin/downloads. The redirect always works even
 * if tracking fails — a download must never be blocked by analytics.
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

  // Record the download — privacy-preserving (salted hashes, never raw IP/UA).
  try {
    const ip = getClientIP(req);
    const ua = req.headers.get("user-agent") || "";
    const salt = process.env.IP_HASH_SALT || "";
    const sha = (s: string) => createHash("sha256").update(s).digest("hex");
    const key = req.nextUrl.searchParams.get("key");
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
