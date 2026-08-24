import { createHash, randomBytes } from "crypto";

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
