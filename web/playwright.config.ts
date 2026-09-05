import { defineConfig, devices } from "@playwright/test";

// Web regression smoke suite. Boots a REAL production build (`next start`) so the
// build + prerender is itself part of the check (this is what would have caught the
// Next 16 upgrade issues). CI builds first, then Playwright starts the server.
const PORT = 3100;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
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
    // Dummy but format-valid Clerk keys — the app renders signed-out; no real auth.
    // (Publishable keys are public; the "secret" here is fake. secret-scan only
    // flags sk_live_.)
    env: {
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:
        process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
        "pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk",
      CLERK_SECRET_KEY:
        process.env.CLERK_SECRET_KEY ||
        "sk_test_ZHVtbXlfc2VjcmV0X2Zvcl9lMmVfc21va2Vfb25seQ",
    },
  },
});
