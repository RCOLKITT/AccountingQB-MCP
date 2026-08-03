import crypto from "crypto";

// Application-level field encryption for QuickBooks OAuth tokens stored in
// oauth_tokens. AES-256-GCM (authenticated). Format: "enc:v1:<iv>:<tag>:<ct>"
// (all base64). decryptToken() passes non-prefixed values through unchanged, so
// legacy plaintext rows keep working until re-written — zero-downtime migration.

const PREFIX = "enc:v1:";

function key(): Buffer | null {
  const k = process.env.TOKEN_ENCRYPTION_KEY;
  if (!k) return null;
  const buf = Buffer.from(k, "base64");
  return buf.length === 32 ? buf : null;
}

export function isEncrypted(value: string | null | undefined): boolean {
  return typeof value === "string" && value.startsWith(PREFIX);
}

function isProduction(): boolean {
  return (
    process.env.VERCEL_ENV === "production" ||
    process.env.NODE_ENV === "production"
  );
}

/** Encrypt a token for storage. Fails CLOSED in production: if
 *  TOKEN_ENCRYPTION_KEY is missing or malformed we throw rather than silently
 *  writing a plaintext OAuth token to the database. Only dev/preview may fall
 *  back to plaintext. */
export function encryptToken(plain: string): string {
  const k = key();
  if (!k) {
    if (isProduction()) {
      throw new Error(
        "TOKEN_ENCRYPTION_KEY is missing or not a 32-byte base64 key — " +
          "refusing to store an OAuth token in plaintext in production."
      );
    }
    return plain; // dev/preview only
  }
  if (!plain || isEncrypted(plain)) return plain;
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", k, iv);
  const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return (
    PREFIX +
    [iv, tag, ct].map((b) => b.toString("base64")).join(":")
  );
}

/** Decrypt a stored token. Plaintext (legacy) values are returned unchanged. */
export function decryptToken(stored: string): string {
  if (!isEncrypted(stored)) return stored;
  const k = key();
  if (!k) return stored;
  try {
    const [ivB, tagB, ctB] = stored.slice(PREFIX.length).split(":");
    const iv = Buffer.from(ivB, "base64");
    const tag = Buffer.from(tagB, "base64");
    const ct = Buffer.from(ctB, "base64");
    const decipher = crypto.createDecipheriv("aes-256-gcm", k, iv);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(ct), decipher.final()]).toString("utf8");
  } catch {
    return stored;
  }
}
