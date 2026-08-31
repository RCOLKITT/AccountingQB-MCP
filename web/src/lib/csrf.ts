import { NextResponse } from "next/server";
import crypto from "crypto";

export const CSRF_COOKIE_NAME = "qb_oauth_state";
const CSRF_COOKIE_MAX_AGE = 600; // 10 minutes

export interface StatePayload {
  state: string;
  licenseKey: string;
}

/**
 * Generates a cryptographically secure state token.
 */
export function generateState(): string {
  return crypto.randomBytes(32).toString("hex");
}

/**
 * Encodes state and license key into URL-safe base64.
 */
export function encodeStatePayload(state: string, licenseKey: string): string {
  return Buffer.from(JSON.stringify({ state, licenseKey })).toString(
    "base64url",
  );
}

/**
 * Decodes state payload from URL parameter.
 * Returns null if decoding fails or payload is invalid.
 */
export function decodeStatePayload(encoded: string): StatePayload | null {
  try {
    const decoded = JSON.parse(Buffer.from(encoded, "base64url").toString());
    if (
      typeof decoded.state === "string" &&
      typeof decoded.licenseKey === "string"
    ) {
      return decoded as StatePayload;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Creates a redirect response with the CSRF state cookie set.
 */
export function redirectWithStateCookie(
  url: string,
  state: string,
): NextResponse {
  const response = NextResponse.redirect(url, 303);

  response.cookies.set(CSRF_COOKIE_NAME, state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax", // Allows cookie to be sent on OAuth redirects
    maxAge: CSRF_COOKIE_MAX_AGE,
    path: "/",
  });

  return response;
}

/**
 * Validates that the state from cookie matches state from URL.
 * Returns the decoded payload if valid, null if invalid.
 *
 * Uses constant-time comparison to prevent timing attacks.
 */
export function validateState(
  cookieState: string | undefined,
  urlStateEncoded: string | undefined,
): StatePayload | null {
  if (!cookieState || !urlStateEncoded) {
    return null;
  }

  const payload = decodeStatePayload(urlStateEncoded);
  if (!payload) {
    return null;
  }

  // Constant-time comparison to prevent timing attacks
  try {
    const cookieBuffer = Buffer.from(cookieState);
    const payloadBuffer = Buffer.from(payload.state);

    // Buffers must be same length for timingSafeEqual
    if (cookieBuffer.length !== payloadBuffer.length) {
      return null;
    }

    if (!crypto.timingSafeEqual(cookieBuffer, payloadBuffer)) {
      return null;
    }
  } catch {
    return null;
  }

  return payload;
}

/**
 * Clears the CSRF cookie (call after successful validation).
 */
export function clearStateCookie(response: NextResponse): void {
  response.cookies.delete(CSRF_COOKIE_NAME);
}
