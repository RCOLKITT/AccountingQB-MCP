import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getUsageTrackLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * POST /api/app/heartbeat  { license_key, version?, platform? }
 *
 * The local desktop app pings this on launch (and periodically) so we can see
 * WHO is running it and that an install is alive — the download crowd was
 * otherwise completely invisible. Activation + heartbeat ONLY: license key, app
 * version, platform, last-seen. No per-tool usage and NO financial data — those
 * never leave the user's machine (the privacy promise is unchanged).
 *
 * Authenticated by the license key in the body (validated against licenses),
 * not a Clerk session — the route is public in middleware, same as /api/usage.
 * Unknown keys are a silent no-op so a spoofed key can't pollute the table.
 */
const LICENSE_RE = /^LK-[0-9A-F]{32}$/i;

export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getUsageTrackLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }

  let body: { license_key?: string; version?: string; platform?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const licenseKey = (body.license_key || "").trim();
  if (!LICENSE_RE.test(licenseKey)) {
    return NextResponse.json({ error: "invalid_license_key" }, { status: 400 });
  }
  const version = (body.version || "").slice(0, 32) || null;
  const platform = (body.platform || "").slice(0, 32) || null;

  const supabase = getSupabase();

  // Only record heartbeats for a real license — no spoofed-key rows.
  const { data: license } = await supabase
    .from("licenses")
    .select("key")
    .eq("key", licenseKey)
    .maybeSingle();
  if (!license) {
    // 200 no-op: the app shouldn't retry-storm on an unknown/expired key.
    return NextResponse.json({ ok: true, recorded: false });
  }

  // First heartbeat for this license → record an activation milestone (the
  // funnel/admin can then see local installs coming online). Best-effort.
  const { data: existing } = await supabase
    .from("app_heartbeats")
    .select("license_key")
    .eq("license_key", licenseKey)
    .maybeSingle();
  if (!existing) {
    await supabase.from("user_milestones").insert({
      license_key: licenseKey,
      milestone: "app_activated",
      metadata: { version, platform, source: "desktop_app" },
    });
  }

  // Atomic upsert (race-free count increment) via the SQL function.
  const { error } = await supabase.rpc("record_app_heartbeat", {
    p_license_key: licenseKey,
    p_app_version: version,
    p_platform: platform,
  });
  if (error) {
    console.error("record_app_heartbeat failed:", error);
    return NextResponse.json({ error: "server_error" }, { status: 500 });
  }

  return NextResponse.json({ ok: true, recorded: true });
}
