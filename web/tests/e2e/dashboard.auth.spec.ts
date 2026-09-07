import { test, expect } from "@playwright/test";
import { clerk } from "@clerk/testing/playwright";

// Authenticated happy-path (SPINE G11): a real signed-in Clerk user reaches the
// dashboard and sees the authenticated view render — the positive complement to
// auth-boundary.spec.ts (which proves anonymous callers are rejected). Runs against
// a real prod build with the Clerk DEVELOPMENT instance; the test user is a
// `+clerk_test` account (Doppler → GitHub secrets). Guarded: skips cleanly when
// creds are absent (local dev / fork PRs) so the suite is never red for lack of a
// secret. Never touches the pk_live_ production instance and creates no book data.

// The test account is a Clerk `+clerk_test` email, so it signs in via the
// email_code strategy with the dev-instance magic code (424242) that
// @clerk/testing applies automatically — no password provisioning required.
const HAS_CREDS =
  !!process.env.E2E_CLERK_USER &&
  (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "").startsWith("pk_test_");

test.describe("authenticated dashboard", () => {
  test.skip(
    !HAS_CREDS,
    "Clerk dev-instance test creds absent — authenticated e2e skipped.",
  );

  test("a signed-in user sees the dashboard render (not signed-out, not 500)", async ({
    page,
  }) => {
    // clerk.signIn needs a non-protected page that has loaded Clerk first.
    await page.goto("/");
    await clerk.loaded({ page });

    await clerk.signIn({
      page,
      signInParams: {
        strategy: "email_code",
        identifier: process.env.E2E_CLERK_USER!,
      },
    });

    await page.goto("/dashboard");

    // Must NOT be bounced to sign-in — we're authenticated.
    await expect(page).not.toHaveURL(/\/sign-in/);

    // Authenticated-only surface. The Clerk UserButton and the "All N Tools" nav
    // link render ONLY inside <SignedIn> (dashboard/page.tsx), so their presence
    // proves the authenticated branch mounted. These are stable regardless of
    // whether the account has a license (a licenseless test account still gets the
    // signed-in header + a "No License Found" empty state, not the signed-out view).
    await expect(
      page.getByRole("button", { name: /open user menu/i }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: /All \d+ Tools/i })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Dashboard", level: 1 }),
    ).toBeVisible();

    // The signed-OUT affordance must be gone (no "Sign in" CTA on an authed page).
    await expect(page.getByRole("button", { name: /^sign in$/i })).toHaveCount(
      0,
    );

    // No error boundary / crash text leaked into the document.
    const html = await page.content();
    expect(html).not.toMatch(/Application error|Internal Server Error/i);
  });
});
