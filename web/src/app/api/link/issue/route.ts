import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import { identityHash, genCode, genPairingSecret, LINK_CODE_TTL_MS } from "@/lib/link";
import { getLinkLimiter, getClientIP, rateLimitResponse, isRateLimitingEnabled } from "@/lib/ratelimit";

/**
 * POST /api/link/issue  — mint a short-lived pairing code for the signed-in AccountingQB
 * account. Auth is EITHER a Clerk session (web dashboard) OR a license key (desktop app,
 * body {licenseKey} or ?key=). The code is bound server-side to the account's verified-email
 * identity hash + a fresh pairing secret; the peer (Coffer) redeems it only if it presents the
 * SAME identity hash. → { code, expiresAt }.
 */
export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getLinkLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }
  const supabase = getSupabase();
  const body = await req.json().catch(() => ({}));
  const key = String(body?.licenseKey || req.nextUrl.searchParams.get("key") || "").trim();

  let email = "";
  let licenseKey = "";
  if (key) {
    const { data: lic } = await supabase.from("licenses").select("key, email, status").eq("key", key).single();
    if (!lic || lic.status === "canceled" || lic.status === "expired") {
      return NextResponse.json({ error: "invalid or inactive license" }, { status: 401 });
    }
    email = lic.email || "";
    licenseKey = lic.key;
  } else {
    const user = await currentUser();
    email = user?.emailAddresses?.[0]?.emailAddress?.toLowerCase() || "";
    if (!email) {
      return NextResponse.json({ error: "sign in or pass a license key" }, { status: 401 });
    }
    const { data: lics } = await supabase
      .from("licenses")
      .select("key")
      .eq("email", email)
      .in("status", ["active", "trialing"])
      .limit(1);
    if (!lics || lics.length === 0) {
      return NextResponse.json({ error: "no active AccountingQB license for this account" }, { status: 403 });
    }
    licenseKey = lics[0].key;
  }

  const code = genCode();
  const expiresAt = new Date(Date.now() + LINK_CODE_TTL_MS).toISOString();
  const { error } = await supabase.from("link_codes").insert({
    code,
    identity_hash: identityHash(email),
    pairing_secret: genPairingSecret(),
    license_key: licenseKey,
    peer_product: "coffer",
    expires_at: expiresAt,
  });
  if (error) {
    return NextResponse.json({ error: "could not create link code" }, { status: 500 });
  }
  return NextResponse.json({ code, expiresAt, peerProduct: "coffer" });
}
