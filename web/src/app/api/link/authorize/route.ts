import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import {
  identityHash,
  genCode,
  genPairingSecret,
  LINK_CODE_TTL_MS,
  isAllowedRedirectUri,
} from "@/lib/link";
import {
  getLinkLimiter,
  getClientIP,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * POST /api/link/authorize  — the "grant" step of the OAuth-style "Connect AccountingQB" flow.
 * The signed-in AccountingQB user has just consented (on /link/authorize) to link the peer app.
 * We mint a one-time code bound to a PKCE challenge + the return redirect_uri, then hand back the
 * redirect URL the browser should follow. The peer redeems the code with its code_verifier — no
 * email match required, because logging in here already proved the user owns this account.
 *
 * Auth: a Clerk session (the consent page is behind auth). Requires an active/trialing license —
 * you can't link a product you don't have a plan for (the integration tools are license-gated).
 */
export async function POST(req: NextRequest) {
  if (isRateLimitingEnabled()) {
    const ip = getClientIP(req);
    const { success, reset } = await getLinkLimiter().limit(ip);
    if (!success) return rateLimitResponse(reset);
  }

  const body = await req.json().catch(() => ({}));
  const peer = String(body?.peer || "coffer").trim();
  const redirectUri = String(body?.redirectUri || "").trim();
  const state = String(body?.state || "").trim();
  const codeChallenge = String(body?.codeChallenge || "").trim();

  if (peer !== "coffer") {
    return NextResponse.json({ error: "unsupported peer" }, { status: 400 });
  }
  if (!isAllowedRedirectUri(redirectUri)) {
    return NextResponse.json(
      { error: "redirect_uri not allowed" },
      { status: 400 },
    );
  }
  if (!codeChallenge || codeChallenge.length < 43) {
    return NextResponse.json(
      { error: "code_challenge required (S256)" },
      { status: 400 },
    );
  }

  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress?.toLowerCase() || "";
  if (!email) {
    return NextResponse.json({ error: "sign in to link" }, { status: 401 });
  }

  const supabase = getSupabase();
  const { data: lics } = await supabase
    .from("licenses")
    .select("key")
    .eq("email", email)
    .in("status", ["active", "trialing"])
    .limit(1);
  if (!lics || lics.length === 0) {
    return NextResponse.json(
      {
        error: "no active AccountingQB plan for this account",
        needsPlan: true,
      },
      { status: 403 },
    );
  }

  const code = genCode();
  const expiresAt = new Date(Date.now() + LINK_CODE_TTL_MS).toISOString();
  const { error } = await supabase.from("link_codes").insert({
    code,
    identity_hash: identityHash(email),
    pairing_secret: genPairingSecret(),
    license_key: lics[0].key,
    peer_product: peer,
    expires_at: expiresAt,
    code_challenge: codeChallenge,
    redirect_uri: redirectUri,
  });
  if (error) {
    return NextResponse.json(
      { error: "could not create link code" },
      { status: 500 },
    );
  }

  const dest = new URL(redirectUri);
  dest.searchParams.set("code", code);
  if (state) dest.searchParams.set("state", state);
  return NextResponse.json({ redirectUrl: dest.toString(), expiresAt });
}
