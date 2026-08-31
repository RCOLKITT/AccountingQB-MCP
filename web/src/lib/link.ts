import { createHash, randomBytes, timingSafeEqual } from "crypto";

/** Cross-product identity from a verified account email. MUST match the shim + Coffer:
 *  sha256("aqb-coffer-link:v1:" + email.trim().toLowerCase()). The email never travels. */
export function identityHash(email: string): string {
  return createHash("sha256")
    .update("aqb-coffer-link:v1:" + (email || "").trim().toLowerCase())
    .digest("hex");
}

/** Short, human-pasteable one-time link code (URL-safe). */
export function genCode(): string {
  return randomBytes(9).toString("base64url"); // ~12 chars
}

/** High-entropy shared secret carried on every cross-app call. */
export function genPairingSecret(): string {
  return randomBytes(32).toString("hex");
}

export const LINK_CODE_TTL_MS = 10 * 60 * 1000; // 10 minutes

/** PKCE S256 check: does sha256(verifier) (base64url, unpadded) equal the stored challenge?
 *  This binds the redeem to the same browser session that started the authorize flow, which is
 *  why the OAuth-style path can safely drop the same-email identity match. Constant-time. */
export function verifyPkceS256(verifier: string, challenge: string): boolean {
  if (!verifier || !challenge) return false;
  const computed = createHash("sha256").update(verifier).digest("base64url");
  const a = Buffer.from(computed);
  const b = Buffer.from(challenge);
  return a.length === b.length && timingSafeEqual(a, b);
}

/** Where the authorize flow is allowed to hand the code back. STRICT: exactly the peer product's
 *  web callback (https), or a loopback callback for the peer's desktop app on its known shim port
 *  range. Anything else is rejected so a code can never be redirected to an attacker. Coffer's shim
 *  uses 4317; AccountingQB's uses 4318 — allow the small shared range both pick free ports within. */
export function isAllowedRedirectUri(uri: string): boolean {
  let u: URL;
  try {
    u = new URL(uri);
  } catch {
    return false;
  }
  if (u.pathname !== "/link/callback") return false;
  if (u.search || u.hash) return false; // params are appended by us, not pre-supplied
  // Peer web callbacks (Coffer today; add peers here as they onboard).
  if (u.protocol === "https:" && u.hostname === "coffermoney.com") return true;
  // Loopback desktop callbacks — only the real local app can receive these.
  const loopback = u.hostname === "127.0.0.1" || u.hostname === "localhost";
  const port = Number(u.port || 0);
  if (loopback && u.protocol === "http:" && port >= 4317 && port <= 4320)
    return true;
  return false;
}
