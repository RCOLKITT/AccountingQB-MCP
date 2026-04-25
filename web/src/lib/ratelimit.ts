import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";

// Lazy-initialized Redis client
let _redis: Redis | null = null;

function getRedis(): Redis {
  if (!_redis) {
    const url = process.env.UPSTASH_REDIS_REST_URL;
    const token = process.env.UPSTASH_REDIS_REST_TOKEN;

    if (!url || !token) {
      throw new Error("Missing UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN");
    }

    _redis = new Redis({ url, token });
  }
  return _redis;
}

// Rate limiter for checkout: 5 requests per minute per IP
export function getCheckoutLimiter(): Ratelimit {
  return new Ratelimit({
    redis: getRedis(),
    limiter: Ratelimit.slidingWindow(5, "1 m"),
    prefix: "ratelimit:checkout",
    analytics: true,
  });
}

// Rate limiter for token endpoint: 10 requests per minute per IP
export function getTokenLimiter(): Ratelimit {
  return new Ratelimit({
    redis: getRedis(),
    limiter: Ratelimit.slidingWindow(10, "1 m"),
    prefix: "ratelimit:token",
    analytics: true,
  });
}

// Rate limiter for OAuth start: 5 requests per minute per license
export function getOAuthStartLimiter(): Ratelimit {
  return new Ratelimit({
    redis: getRedis(),
    limiter: Ratelimit.slidingWindow(5, "1 m"),
    prefix: "ratelimit:oauth-start",
    analytics: true,
  });
}

// Rate limiter for usage tracking: 100 requests per minute per license
// Higher limit since MCP server may call multiple tools in quick succession
export function getUsageTrackLimiter(): Ratelimit {
  return new Ratelimit({
    redis: getRedis(),
    limiter: Ratelimit.slidingWindow(100, "1 m"),
    prefix: "ratelimit:usage-track",
    analytics: true,
  });
}

// Rate limiter for support chat: 20 messages per minute per IP
export function getSupportLimiter(): Ratelimit {
  return new Ratelimit({
    redis: getRedis(),
    limiter: Ratelimit.slidingWindow(20, "1 m"),
    prefix: "ratelimit:support",
    analytics: true,
  });
}

/**
 * Extracts client IP from request headers.
 * Vercel sets x-forwarded-for; falls back to x-real-ip or "unknown".
 */
export function getClientIP(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0].trim();
  }
  return req.headers.get("x-real-ip") || "unknown";
}

/**
 * Returns a 429 Too Many Requests response with Retry-After header.
 */
export function rateLimitResponse(reset: number): NextResponse {
  const retryAfter = Math.ceil((reset - Date.now()) / 1000);
  return NextResponse.json(
    { error: "Too many requests. Please try again later." },
    {
      status: 429,
      headers: {
        "Retry-After": String(retryAfter),
        "X-RateLimit-Reset": String(reset),
      },
    }
  );
}

/**
 * Checks if rate limiting is enabled (env vars present).
 * Returns false if Upstash is not configured, allowing graceful degradation.
 */
export function isRateLimitingEnabled(): boolean {
  return !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);
}
