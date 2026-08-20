import type { NextConfig } from "next";

// Security headers applied to every response (vaspera cert: clickjacking +
// defense-in-depth). frame-ancestors 'none' + X-Frame-Options DENY stop the
// app being framed; HSTS/nosniff/referrer/permissions harden the rest. The
// CSP is intentionally limited to frame-ancestors so it can't break the
// inline JSON-LD, Clerk, or Vercel Analytics scripts the app already ships.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

const nextConfig: NextConfig = {
  // Vercel deploys automatically
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // HeyCatch short links: single-character paths (/a–/z, /0–/9) are reserved for
  // campaign attribution and 302 to the homepage with UTM params. No real route
  // uses a single-character path, so this only affects attribution links.
  async redirects() {
    return [
      {
        source: "/:l([a-z0-9])",
        destination: "/?utm_source=heycatch&utm_campaign=:l",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
