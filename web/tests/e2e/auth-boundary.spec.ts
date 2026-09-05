import { test, expect } from "@playwright/test";

// Auth-boundary regression net (Constitution: "anonymous writes are structurally
// impossible"; protected surface must never leak). These assert the NEGATIVE path
// — an unauthenticated caller must be REJECTED (redirect / 401 / 403 / 404), never
// served protected data with a 200. No credentials needed, so this locks the
// security boundary in CI now; the authenticated happy-path e2e (dashboard renders
// for a signed-in user) is the follow-up that needs a Clerk test user.

// Protected API routes (NOT in middleware isPublicRoute → auth.protect()).
const PROTECTED_API = [
  "/api/user/licenses",
  "/api/user/profile",
  "/api/artifacts",
  "/api/stats",
];

// Admin routes: require the admin ROLE, not just any session.
const ADMIN_API = ["/api/admin/users", "/api/admin/emails"];

for (const path of [...PROTECTED_API, ...ADMIN_API]) {
  test(`protected API ${path} rejects anonymous access`, async ({ request }) => {
    const resp = await request.get(path, { maxRedirects: 0 });
    // Must NOT serve protected data to an anonymous caller.
    expect(resp.status(), `${path} returned 200 to anon`).not.toBe(200);
    // Acceptable rejections: redirect to sign-in, or an auth error.
    expect([301, 302, 303, 307, 308, 401, 403, 404]).toContain(resp.status());
  });
}

test("admin page redirects an anonymous visitor away", async ({ request }) => {
  const resp = await request.get("/admin", { maxRedirects: 0 });
  // Signed-out → redirect (to /sign-in); never render admin content at 200.
  if (resp.status() === 200) {
    const html = await resp.text();
    expect(html).not.toMatch(/Revenue|All Users|Funnel|admin dashboard/i);
  } else {
    expect([301, 302, 303, 307, 308, 404]).toContain(resp.status());
  }
});

test("a write to a protected API is refused when anonymous", async ({
  request,
}) => {
  // Constitution: no anonymous mutation. A POST to a protected route with no
  // session must not succeed.
  const resp = await request.post("/api/user/link-license", {
    data: { licenseKey: "LK-SHOULD-NOT-WORK" },
    maxRedirects: 0,
  });
  expect(resp.status(), "anonymous write was accepted").not.toBe(200);
});
