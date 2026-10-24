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
    // The auto-download navigates an <a> to /api/download/...; abort it so the
    // page stays put, and record that it fired (that's the "download-first" bit).
    await page.route("**/api/download/**", (route) => {
      downloadHits.push(route.request().url());
      return route.abort();
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

    await page.goto("/download?platform=macos");

    // 1) The download starts on its own — no email required to get the file.
    await expect
      .poll(() => downloadHits.some((u) => /\/api\/download\/macos/.test(u)), {
        timeout: 15_000,
      })
      .toBe(true);

    // 2) The trial-key capture is present (what humans need to convert).
    const submit = page.getByRole("button", {
      name: /email me my license key/i,
    });
    await expect(submit).toBeVisible();

    await page
      .getByPlaceholder("you@company.com")
      .fill("e2e+download@example.com");
    await submit.click();

    // The capture calls /api/trial/start with the email, and the success state
    // renders — the full path a download→trial conversion depends on.
    await expect
      .poll(() => trialPayload?.email, { timeout: 15_000 })
      .toBe("e2e+download@example.com");
    await expect(page.getByText(/on their way to your inbox/i)).toBeVisible();
  });
});
