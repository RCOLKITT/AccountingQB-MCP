import { clerkMiddleware, createRouteMatcher, clerkClient } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/pricing",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks(.*)",
  "/api/stripe(.*)",
  "/api/clerk(.*)",
  "/api/health",
  "/api/auth(.*)",
  "/api/debug(.*)",
  "/api/license(.*)",
  "/api/oauth(.*)",
  "/api/setup(.*)",
  "/setup-wizard(.*)",
  "/setup(.*)",
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
