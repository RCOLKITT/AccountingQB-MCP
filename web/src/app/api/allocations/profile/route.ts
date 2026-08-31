import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getTokenLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * Taxpayer allocation profile broker — per (license_key, realm_id, tax_year).
 * Same auth model as /api/oauth/token: the license key is validated server-side,
 * the service-role Supabase client is used (RLS is deny-by-default), and there is
 * no JWT. Profiles are NOT secrets (unlike tokens) so they are stored/returned as
 * plain JSON. Both handlers are rate-limited by IP.
 *
 * GET  ?licenseKey=&realmId=&taxYear=   -> { profile }
 * POST { licenseKey, realmId, taxYear, profile } -> upsert -> { ok, profile }
 */

async function validateLicense(licenseKey: string) {
  const supabase = getSupabase();
  const { data: license, error } = await supabase
    .from("licenses")
    .select("key, status")
    .eq("key", licenseKey)
    .single();
  if (error || !license) return { error: "Invalid license key", status: 401 };
  if (license.status === "canceled" || license.status === "expired")
    return { error: "License is no longer active", status: 403 };
  return { supabase };
}

export async function GET(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const { success, reset } = await getTokenLimiter().limit(getClientIP(req));
    if (!success) return rateLimitResponse(reset);
  }
  const licenseKey = req.nextUrl.searchParams.get("licenseKey") || "";
  const realmId = req.nextUrl.searchParams.get("realmId") || "";
  const taxYear = parseInt(req.nextUrl.searchParams.get("taxYear") || "", 10);
  if (!licenseKey || !realmId || !Number.isInteger(taxYear)) {
    return NextResponse.json(
      { error: "licenseKey, realmId and taxYear are required" },
      { status: 400 },
    );
  }
  const v = await validateLicense(licenseKey);
  if ("error" in v)
    return NextResponse.json({ error: v.error }, { status: v.status });

  const { data } = await v
    .supabase!.from("allocation_profiles")
    .select("profile")
    .eq("license_key", licenseKey)
    .eq("realm_id", realmId)
    .eq("tax_year", taxYear)
    .maybeSingle();

  return NextResponse.json(
    { profile: data?.profile || null },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const { success, reset } = await getTokenLimiter().limit(getClientIP(req));
    if (!success) return rateLimitResponse(reset);
  }
  let body: {
    licenseKey?: string;
    realmId?: string;
    taxYear?: number;
    profile?: Record<string, unknown>;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const { licenseKey, realmId, taxYear, profile } = body;
  if (!licenseKey || !realmId || !Number.isInteger(taxYear)) {
    return NextResponse.json(
      { error: "licenseKey, realmId and taxYear are required" },
      { status: 400 },
    );
  }
  if (
    profile === null ||
    typeof profile !== "object" ||
    Array.isArray(profile)
  ) {
    return NextResponse.json(
      { error: "profile must be a JSON object" },
      { status: 400 },
    );
  }
  const v = await validateLicense(licenseKey);
  if ("error" in v)
    return NextResponse.json({ error: v.error }, { status: v.status });

  const { error } = await v.supabase!.from("allocation_profiles").upsert(
    {
      license_key: licenseKey,
      realm_id: realmId,
      tax_year: taxYear,
      profile,
    },
    { onConflict: "license_key,realm_id,tax_year" },
  );
  if (error) {
    console.error("allocation profile upsert failed:", error.code);
    return NextResponse.json(
      { error: "Could not save profile" },
      { status: 500 },
    );
  }
  return NextResponse.json({ ok: true, profile });
}
