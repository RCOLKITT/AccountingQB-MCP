import { clerkSetup } from "@clerk/testing/playwright";

// Playwright globalSetup: fetch a Clerk Testing Token ONCE, in the main process,
// before any worker forks — so setupClerkTestingToken (called inside clerk.signIn)
// can read process.env.CLERK_TESTING_TOKEN in every worker. This bypasses Clerk's
// bot/anti-automation checks on the dev instance.
//
// GUARDED: only runs when real Clerk *development-instance* creds + a test user are
// present in the environment (CI injects them from GitHub secrets, sourced from
// Doppler). With no creds (local dev, or a fork PR that can't read secrets),
// clerkSetup is skipped and the authenticated spec skips itself — the public smoke
// + auth-boundary specs still run against dummy keys. Never touches the pk_live_
// production instance.
export default async function globalSetup() {
  const pk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
  const sk = process.env.CLERK_SECRET_KEY || "";
  const hasRealDevCreds =
    pk.startsWith("pk_test_") &&
    sk.startsWith("sk_test_") &&
    !!process.env.E2E_CLERK_USER;

  if (!hasRealDevCreds) {
    console.log(
      "[e2e] Clerk dev-instance creds absent — skipping clerkSetup; " +
        "authenticated spec will skip (public + auth-boundary specs still run).",
    );
    return;
  }

  await clerkSetup();
  console.log("[e2e] Clerk Testing Token acquired (dev instance).");
}
