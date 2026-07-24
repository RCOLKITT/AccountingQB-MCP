import { clerkMiddleware, createRouteMatcher, clerkClient } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/pricing",
  "/canada",
  "/privacy",
  "/terms",
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
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.redirect(new URL("/sign-in", req.url));
    }

    // Fetch user to get publicMetadata (not included in session JWT by default)
    const client = await clerkClient();
    const user = await client.users.getUser(userId);
    const role = (user.publicMetadata as { role?: string })?.role;

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
