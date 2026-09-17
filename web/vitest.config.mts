import { defineConfig } from "vitest/config";

// Unit tests for server-side lib logic (crypto, money math, etc.). Deliberately
// scoped to co-located src/**/*.test.ts so it never picks up the Playwright e2e
// specs in tests/e2e/*.spec.ts (those run under @playwright/test via `test:e2e`).
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
