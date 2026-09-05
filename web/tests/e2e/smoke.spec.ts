import { test, expect } from "@playwright/test";

// Regression smoke net: every public page must return < 400 and render real
// server HTML (not a 500 / error shell). The fast tripwire for "a deploy broke a
// page" — the silent breakage a framework upgrade or refactor can cause. We check
// the SERVER response (SSR/prerender output), which is what matters for these
// marketing/SEO pages and is stable regardless of client auth state. Runs against
// a real production build, so the build + prerender is checked too.
//
// Authenticated flows (dashboard/admin) are Clerk-gated and need real test
// credentials — a follow-up (SPINE-STATUS G11).

const PUBLIC_PAGES: Array<[path: string, mustContain: RegExp]> = [
  ["/", /AccountingQB/i],
  ["/pricing", /pric/i],
  ["/faq", /question|faq/i],
  ["/security", /security/i],
  ["/about", /about|founder|story|vaspera/i],
  ["/canada", /canad|GST|HST/i],
  ["/terms", /terms/i],
  ["/privacy", /privacy/i],
  ["/changelog", /change|release|version|v\d/i],
  ["/demo", /demo/i],
  ["/sign-in", /sign|log ?in|clerk/i],
];

for (const [path, mustContain] of PUBLIC_PAGES) {
  test(`public page ${path} serves real content`, async ({ request }) => {
    // A real error page returns 4xx/5xx — the status check IS the error tripwire.
    // (App Router inlines its error/not-found boundary markup into every document,
    // so a text-match on "error"/"not found" would false-positive on every page.)
    const resp = await request.get(path);
    expect(resp.status(), `${path} status`).toBeLessThan(400);
    const html = await resp.text();
    expect(html.length, `${path} body too small`).toBeGreaterThan(1000);
    expect(html, `${path} missing expected content`).toMatch(mustContain);
  });
}

test("security headers are applied (next.config)", async ({ request }) => {
  const resp = await request.get("/");
  expect(resp.headers()["x-frame-options"]).toBe("DENY");
  expect(resp.headers()["strict-transport-security"]).toContain("max-age=");
});

test("robots.txt and sitemap.xml serve", async ({ request }) => {
  expect((await request.get("/robots.txt")).status()).toBeLessThan(400);
  expect((await request.get("/sitemap.xml")).status()).toBeLessThan(400);
});

test("download endpoint redirects to a signed release asset", async ({
  request,
}) => {
  // Core conversion path: /api/download/macos → 3xx to the GitHub release.
  const resp = await request.get("/api/download/macos", { maxRedirects: 0 });
  expect([301, 302, 307, 308]).toContain(resp.status());
  expect(resp.headers()["location"]).toMatch(/github\.com|releases/i);
});

test("protected dashboard is not publicly readable", async ({ request }) => {
  // Signed-out access must NOT return dashboard content (Clerk gates it). Accept a
  // redirect, or a page that lacks the authenticated-only markers.
  const resp = await request.get("/dashboard", { maxRedirects: 0 });
  if (resp.status() >= 300 && resp.status() < 400) return; // redirected to sign-in
  expect(resp.status()).toBeLessThan(500);
  const html = await resp.text();
  expect(html).not.toContain("Your Licenses");
});
