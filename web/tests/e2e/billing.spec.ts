import { test, expect } from "@playwright/test";

// Billing self-service regression (the fix for the "no subscription / no cancel
// control" dead-end a real trial user hit). Contract: a user must ALWAYS reach a
// clear, non-error outcome for cancel / manage-billing — never a 500, and never a
// bare 404 for the "nothing to cancel, you won't be charged" case.
//
// These hit the DB, so they need the service-role creds the web-e2e job injects;
// skip cleanly when absent (fork PRs) — like the authed dashboard spec.
const HAS_DB = !!(process.env.SUPABASE_URL || process.env.E2E_SUPABASE_URL);

test.describe("billing self-service", () => {
  test.skip(
    !HAS_DB,
    "Supabase creds absent — billing endpoint checks skipped.",
  );

  test("manage-billing never dead-ends: unknown license → graceful no_billing_account (not 404/500)", async ({
    request,
  }) => {
    const resp = await request.post("/api/stripe/portal", {
      data: { licenseKey: "LK-E2E-DOES-NOT-EXIST-0000000000000000" },
    });
    expect(resp.status(), "portal must not 5xx/404 dead-end").toBe(200);
    const body = await resp.json();
    // No Stripe customer for an unknown key → clear "nothing to manage" state.
    expect(body.state).toBe("no_billing_account");
    expect(typeof body.message).toBe("string");
  });

  test("cancel with no license key is a clean client error, never a 500", async ({
    request,
  }) => {
    const resp = await request.post("/api/user/subscription/cancel", {
      data: {},
    });
    // The exact 4xx (400 missing-key vs 404 not-found) isn't the contract; "never a
    // 500 dead-end" is. A user must never see a server crash on the cancel path.
    expect(resp.status(), "cancel must not 5xx").toBeGreaterThanOrEqual(400);
    expect(resp.status()).toBeLessThan(500);
  });

  test("cancel on an unknown license is a clean 404, not a 500", async ({
    request,
  }) => {
    const resp = await request.post("/api/user/subscription/cancel", {
      data: { licenseKey: "LK-E2E-DOES-NOT-EXIST-0000000000000000" },
    });
    expect(resp.status(), "unknown license → 404, never 500").toBe(404);
  });
});
