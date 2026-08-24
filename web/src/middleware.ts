import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveAdmin, type AdminClaims } from "@/lib/admin-auth";

const isPublicRoute = createRouteMatcher([
  "/",
  "/about",
  "/demo",
  "/pricing(.*)",
  "/canada",
  "/changelog",
  "/privacy",
  "/terms",
  "/security",
  "/faq",
  "/login",
  // Stripe redirects new purchasers here before they have an account
  "/success",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks(.*)",
  "/api/stripe(.*)",
  "/api/clerk(.*)",
  "/api/health",
  "/api/auth(.*)",
  "/api/debug(.*)",
  "/api/license(.*)",
  "/api/cron(.*)",
  // MCP server telemetry: usage tracking + setup verification. The server
  // authenticates by license key in the body, not a Clerk session — without
  // this, Clerk bounced these POSTs to sign-in and tool_usage stayed empty.
  "/api/usage(.*)",
  // Desktop-app download redirect: records the click then 302s to the GitHub asset.
  "/api/download(.*)",
  // Cross-app pairing: issue (Clerk-or-license), redeem (peer product), status (license).
  "/api/link(.*)",
  // Allocation-profile broker: the MCP connector authenticates by license key in
  // the body/query (validated server-side), not a Clerk session — same as /api/usage.
  "/api/allocations(.*)",
  "/api/unsubscribe(.*)",
  "/api/oauth(.*)",
  // Remote MCP connector OAuth 2.1 AS: RFC 8414 metadata, DCR/token/client-info
  // endpoints, and the consent page (which handles Clerk auth client-side).
  "/.well-known(.*)",
  "/api/oauth2(.*)",
  "/oauth(.*)",
  "/api/setup(.*)",
  "/setup-wizard(.*)",
  "/setup(.*)",
  // Dashboard supports a signed-out "legacy license key" mode (?key=LK-...);
  // the page itself renders sign-in prompts for visitors without a key.
  "/dashboard(.*)",
]);

const isAdminRoute = createRouteMatcher([
  "/admin(.*)",
  "/api/admin(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  // Admin routes require admin role
  if (isAdminRoute(req)) {
    const { userId, sessionClaims } = await auth();

    if (!userId) {
      return NextResponse.redirect(new URL("/sign-in", req.url));
    }

    // Read the role from the SESSION TOKEN (no Clerk API call) — see
    // resolveAdmin(); falls back to one getUser() only if the token isn't
    // configured with the metadata claim yet. needEmail=false: the gate never
    // fetches on /api/admin routes once the token is configured.
    const { role } = await resolveAdmin(userId, sessionClaims as AdminClaims, false);

    if (role !== "admin") {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
  }
  // Other protected routes just need authentication
  else if (!isPublicRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: ["/((?!.*\\..*|_next).*)", "/", "/(api|trpc)(.*)"],
};
