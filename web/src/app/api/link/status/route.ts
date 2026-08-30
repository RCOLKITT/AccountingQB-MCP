import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import {
  getLinkLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * GET /api/link/status?key=<license>  — the AccountingQB desktop app fetches its account's
 * pairing (secret + peer) and hands it to its local shim (POST /pair). The license key is the
 * bearer credential (only the holder can read the secret). → { paired, pairingSecret?, peerProduct? }.
 */
export async function GET(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getLinkLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }
  const key = String(req.nextUrl.searchParams.get("key") || "").trim();
  if (!key) {
    return NextResponse.json(
      { error: "license key required" },
      { status: 400 },
    );
  }
  const supabase = getSupabase();
  const { data: lic } = await supabase
    .from("licenses")
    .select("key, status")
    .eq("key", key)
    .single();
  if (!lic || lic.status === "canceled" || lic.status === "expired") {
    return NextResponse.json(
      { error: "invalid or inactive license" },
      { status: 401 },
    );
  }
  const { data: link } = await supabase
    .from("account_links")
    .select("pairing_secret, peer_product, peer_identity, created_at")
    .eq("license_key", key)
    .eq("peer_product", "coffer")
    .is("revoked_at", null)
    .single();
  if (!link) {
    return NextResponse.json({ paired: false });
  }
  return NextResponse.json({
    paired: true,
    pairingSecret: link.pairing_secret,
    peerProduct: link.peer_product,
    peerIdentity: link.peer_identity,
    createdAt: link.created_at,
  });
}
