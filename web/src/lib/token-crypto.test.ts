import { describe, it, expect, afterEach, vi } from "vitest";
import crypto from "crypto";
import { encryptToken, decryptToken, isEncrypted } from "./token-crypto";

// Application-level encryption for QuickBooks OAuth tokens at rest (AES-256-GCM).
// The crown-jewel invariant is FAIL-CLOSED: in production, a missing/malformed key
// must throw rather than silently persist a plaintext OAuth token. These lock that
// plus round-trip correctness + the zero-downtime plaintext passthrough.

const KEY = crypto.randomBytes(32).toString("base64"); // valid 32-byte key
const KEY_B = crypto.randomBytes(32).toString("base64"); // a different valid key

afterEach(() => vi.unstubAllEnvs());

describe("token-crypto", () => {
  it("round-trips a token when a valid 32-byte key is set", () => {
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY);
    const plain = "qbo-refresh-token-abc123";
    const enc = encryptToken(plain);
    expect(enc.startsWith("enc:v1:")).toBe(true);
    expect(isEncrypted(enc)).toBe(true);
    expect(enc).not.toContain(plain); // ciphertext must not leak the plaintext
    expect(decryptToken(enc)).toBe(plain);
  });

  it("is idempotent — re-encrypting an already-encrypted value is a no-op", () => {
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY);
    const enc = encryptToken("tok");
    expect(encryptToken(enc)).toBe(enc);
  });

  it("passes empty strings through unchanged", () => {
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY);
    expect(encryptToken("")).toBe("");
  });

  it("isEncrypted is true only for the enc:v1: prefix", () => {
    expect(isEncrypted("enc:v1:whatever")).toBe(true);
    expect(isEncrypted("plaintext")).toBe(false);
    expect(isEncrypted("")).toBe(false);
    expect(isEncrypted(null)).toBe(false);
    expect(isEncrypted(undefined)).toBe(false);
  });

  it("decrypts legacy plaintext by passing it through (zero-downtime migration)", () => {
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY);
    expect(decryptToken("legacy-plaintext-token")).toBe(
      "legacy-plaintext-token",
    );
  });

  it("returns the stored value (no throw) when decrypted with the wrong key", () => {
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY);
    const enc = encryptToken("secret");
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", KEY_B);
    // GCM auth-tag mismatch → caught → returns stored ciphertext, never crashes.
    expect(decryptToken(enc)).toBe(enc);
  });

  it("FAILS CLOSED: throws in production (NODE_ENV) when the key is missing", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", "");
    expect(() => encryptToken("tok")).toThrow(/TOKEN_ENCRYPTION_KEY/);
  });

  it("FAILS CLOSED: throws in production when the key is malformed (not 32 bytes)", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv(
      "TOKEN_ENCRYPTION_KEY",
      Buffer.from("too-short").toString("base64"),
    );
    expect(() => encryptToken("tok")).toThrow(/TOKEN_ENCRYPTION_KEY/);
  });

  it("FAILS CLOSED: VERCEL_ENV=production also triggers the throw", () => {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", "");
    expect(() => encryptToken("tok")).toThrow();
  });

  it("dev/preview without a key falls back to plaintext (no throw)", () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("TOKEN_ENCRYPTION_KEY", "");
    expect(encryptToken("tok")).toBe("tok");
  });
});
