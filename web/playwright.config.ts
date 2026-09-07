import { defineConfig, devices } from "@playwright/test";

// Web regression smoke suite. Boots a REAL production build (`next start`) so the
// build + prerender is itself part of the check (this is what would have caught the
// Next 16 upgrade issues). CI builds first, then Playwright starts the server.
const PORT = 3100;

// Pass a runtime env var through to `next start` only when it is actually set —
// so the authed job (real dev-instance Clerk + Supabase from GitHub secrets) runs
// against real auth, while the plain smoke run keeps the dummy fallbacks below.
const passthrough = (name: string): Record<string, string> =>
  process.env[name] ? { [name]: process.env[name] as string } : {};

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  // Acquire a Clerk Testing Token once, before workers fork (no-op without creds).
  globalSetup: "./tests/e2e/global.setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next start -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: {
      // Dummy but format-valid Clerk keys — the app renders signed-out; no real
      // auth. (Publishable keys are public; the "secret" here is fake. secret-scan
      // only flags sk_live_.) Overridden by the real dev-instance keys when the
      // authed job sets them, so the signed-in session the test creates is valid.
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:
        process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
        "pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk",
      CLERK_SECRET_KEY:
        process.env.CLERK_SECRET_KEY ||
        "sk_test_ZHVtbXlfc2VjcmV0X2Zvcl9lMmVfc21va2Vfb25seQ",
      // Supabase (dashboard data path) — only forwarded when present; the authed
      // API routes need the service role at runtime. Absent → routes 5xx and the
      // dashboard shows empty states, which the authed spec tolerates.
      ...passthrough("SUPABASE_URL"),
      ...passthrough("SUPABASE_SERVICE_ROLE_KEY"),
      ...passthrough("NEXT_PUBLIC_SUPABASE_URL"),
      ...passthrough("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    },
  },
});
