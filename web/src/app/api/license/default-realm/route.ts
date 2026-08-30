import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getDefaultRealmLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * Default QuickBooks realm for a license — consumed by the remote MCP
 * service (accountingqb.remote) on each request (with a ~45-min TTL cache)
 * and, later, written by qb_switch_company in remote mode.
 *
 * GET  /api/license/default-realm?license_key=LK-...  -> { realmId: string | null }
 * POST /api/license/default-realm { license_key, realmId } -> { ok: true }
 *
 * Public (the remote service authenticates users via JWT before it ever
 * calls this) but rate-limited by IP like the other /api/license routes.
 * Requires migrations/2026-07-mcp-oauth.sql (licenses.default_realm_id).
 */

async function rateLimit(req: NextRequest): Promise<NextResponse | null> {
  if (!isRateLimitingEnabled()) return null;
  const { success, reset } = await getDefaultRealmLimiter().limit(
    getClientIP(req),
  );
  return success ? null : rateLimitResponse(reset);
}

export async function GET(req: NextRequest) {
  const limited = await rateLimit(req);
  if (limited) return limited;

  const licenseKey = req.nextUrl.searchParams.get("license_key");
  if (!licenseKey) {
    return NextResponse.json(
      { error: "license_key is required" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();
  const { data: license } = await supabase
    .from("licenses")
    .select("key, default_realm_id")
    .eq("key", licenseKey)
    .maybeSingle();

  if (!license) {
    return NextResponse.json({ error: "License not found" }, { status: 404 });
  }

  return NextResponse.json(
    { realmId: license.default_realm_id || null },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST(req: NextRequest) {
  const limited = await rateLimit(req);
  if (limited) return limited;

  let body: { license_key?: string; realmId?: string | null };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Body must be JSON" }, { status: 400 });
  }

  const { license_key: licenseKey, realmId } = body;
  if (!licenseKey) {
    return NextResponse.json(
      { error: "license_key is required" },
      { status: 400 },
    );
  }
  if (realmId != null && typeof realmId !== "string") {
    return NextResponse.json(
      { error: "realmId must be a string or null" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();
  const { data: license } = await supabase
    .from("licenses")
    .select("key")
    .eq("key", licenseKey)
    .maybeSingle();

  if (!license) {
    return NextResponse.json({ error: "License not found" }, { status: 404 });
  }

  // If a realm is given, it must be one of the license's connected companies.
  if (realmId) {
    const { data: tokenRow } = await supabase
      .from("oauth_tokens")
      .select("realm_id")
      .eq("license_key", licenseKey)
      .eq("realm_id", realmId)
      .maybeSingle();
    if (!tokenRow) {
      return NextResponse.json(
        { error: "realmId is not a connected company for this license" },
        { status: 400 },
      );
    }
  }

  const { error } = await supabase
    .from("licenses")
    .update({ default_realm_id: realmId || null })
    .eq("key", licenseKey);

  if (error) {
    console.error("Failed to set default realm:", error);
    return NextResponse.json({ error: "Failed to update" }, { status: 500 });
  }

  return NextResponse.json({ ok: true, realmId: realmId || null });
}
