import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getLinkLimiter, getClientIP, rateLimitResponse, isRateLimitingEnabled } from "@/lib/ratelimit";

/**
 * POST /api/link/redeem  — the peer product (Coffer) redeems a link code.
 * Body: { code, identityHash } where identityHash is Coffer's own account identity
 * (sha256("aqb-coffer-link:v1:"+lower(email))). The code is released to a pairing ONLY if
 * code.identity_hash === presented identityHash — i.e. the SAME verified email owns both
 * accounts. A different user cannot redeem someone else's code. One-time, short-lived.
 * → { ok, pairingSecret, peerProduct }.
 */
export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getLinkLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }
  const body = await req.json().catch(() => ({}));
  const code = String(body?.code || "").trim();
  const presented = String(body?.identityHash || "").trim();
  if (!code || !presented) {
    return NextResponse.json({ error: "code and identityHash required" }, { status: 400 });
  }

  const supabase = getSupabase();
  const { data: row } = await supabase.from("link_codes").select("*").eq("code", code).single();
  if (!row) {
    return NextResponse.json({ error: "invalid code" }, { status: 404 });
  }
  if (row.redeemed_at) {
    return NextResponse.json({ error: "code already used" }, { status: 409 });
  }
  if (new Date(row.expires_at).getTime() < Date.now()) {
    return NextResponse.json({ error: "code expired" }, { status: 410 });
  }
  if (row.identity_hash !== presented) {
    // The same verified account email must own both apps.
    return NextResponse.json(
      { error: "identity mismatch — the same account email must own both AccountingQB and Coffer" },
      { status: 403 }
    );
  }

  // Consume the code and establish (or refresh) the pairing.
  await supabase.from("link_codes").update({ redeemed_at: new Date().toISOString() }).eq("code", code);
  const { error } = await supabase.from("account_links").upsert(
    {
      license_key: row.license_key,
      identity_hash: row.identity_hash,
      peer_product: row.peer_product,
      peer_identity: presented,
      pairing_secret: row.pairing_secret,
      revoked_at: null,
    },
    { onConflict: "license_key,peer_product" }
  );
  if (error) {
    return NextResponse.json({ error: "could not establish pairing" }, { status: 500 });
  }
  return NextResponse.json({
    ok: true,
    pairingSecret: row.pairing_secret,
    peerProduct: row.peer_product,
    aqbAccount: { product: "accountingqb" },
  });
}
