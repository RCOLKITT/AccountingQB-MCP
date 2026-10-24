import { test, expect } from "@playwright/test";

// Guards the download→trial funnel in a real browser — the regression class that
// silently produced "N downloads, 0 trials" for weeks (an email wall before the
// file + a client flow nothing exercised). The request-level gate (redirects)
// lives in smoke.spec.ts; this covers the CLIENT flow on /download:
//   1. the app file downloads immediately (download-first — no email wall)
//   2. the email → trial-key capture is wired (form → /api/trial/start → success)
//
// Needs the real Clerk DEV instance (same guard as dashboard.auth.spec): /download
// is a client page using Clerk, and the dummy smoke-instance redirects client
// navigations to its hosted sign-in. Skips cleanly when creds are absent (local /
// fork PRs). Both API calls are intercepted, so NO trial is minted and NO email
// is sent even in the authed job — signed-out visitor, no side effects.
const HAS_CREDS =
  !!process.env.E2E_CLERK_USER &&
  (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "").startsWith("pk_test_");

test.describe("download → trial funnel", () => {
  test.skip(
    !HAS_CREDS,
    "Clerk dev-instance creds absent — browser funnel e2e skipped.",
  );

  test("download-first: file auto-downloads and the trial-key capture works", async ({
    page,
  }) => {
    const downloadHits: string[] = [];
    // The auto-download navigates an <a> to /api/download/... — fulfill it as an
    // attachment (like the real endpoint) so the browser downloads it and STAYS
    // on /download (aborting would blank the page). Records that it fired.
    await page.route("**/api/download/**", (route) => {
      downloadHits.push(route.request().url());
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "application/octet-stream",
          "content-disposition": "attachment; filename=accountingqb-stub.bin",
        },
        body: "stub",
      });
    });

    let trialPayload: { email?: string; platform?: string } | null = null;
    await page.route("**/api/trial/start", (route) => {
      trialPayload = route.request().postDataJSON();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, downloadUrl: "/api/download/macos" }),
      });
    });

    // "commit" — don't wait for full load: the page kicks off the file download
    // on mount, and that sub-navigation races the default load wait.
    await page.goto("/download?platform=macos", { waitUntil: "commit" });

    // 0) The page actually rendered the download-first UI (not a redirect/blank).
    await expect(
      page.getByRole("heading", { name: /is downloading/i }),
    ).toBeVisible({ timeout: 15_000 });

    // 1) The download starts on its own — no email required to get the file.
    await expect
      .poll(() => downloadHits.some((u) => /\/api\/download\/macos/.test(u)), {
        timeout: 15_000,
      })
      .toBe(true);

    // 2) The trial-key capture fires. A signed-OUT visitor submits the form; a
    // signed-IN visitor (as the authed CI job is) has it auto-sent. Handle both:
    // wait for whichever appears, submit if it's the form.
    const submit = page.getByRole("button", {
      name: /email me my license key/i,
    });
    const success = page.getByText(/on their way to your inbox/i);
    await expect(submit.or(success).first()).toBeVisible({ timeout: 15_000 });
    if (await submit.isVisible()) {
      await page
        .getByPlaceholder("you@company.com")
        .fill("e2e+download@example.com");
      await submit.click();
    }

    // Either path calls /api/trial/start and lands on the success state — the
    // full download→trial capture the funnel depends on.
    await expect.poll(() => !!trialPayload, { timeout: 15_000 }).toBe(true);
    await expect(success).toBeVisible({ timeout: 15_000 });
  });
});
