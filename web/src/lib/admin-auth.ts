import { clerkClient } from "@clerk/nextjs/server";

// The admin `role` lives in Clerk publicMetadata, which is NOT in the default
// session token — so historically both the middleware and the admin layout had to
// call getUser()/currentUser() (a network round-trip) just to read it, i.e. TWO
// Clerk API calls per admin page.
//
// Fix: surface role (and email, for the header) as SESSION-TOKEN claims, so both
// gates read them from the already-verified JWT with zero API calls. To enable the
// fast path, add this to the Clerk session token
// (Dashboard → Configure → Sessions → Customize session token → Edit):
//
//   {
//     "metadata": "{{user.public_metadata}}",
//     "email": "{{user.primary_email_address}}"
//   }
//
// Until that is configured, resolveAdmin() FALLS BACK to a single user fetch, so
// this code is safe to deploy in either order and never locks admins out.

export interface AdminClaims {
  metadata?: { role?: string };
  email?: string;
}

/** Role straight from the session token (no API call), or undefined if absent. */
export function roleFromClaims(
  claims: AdminClaims | null | undefined,
): string | undefined {
  return claims?.metadata?.role;
}

/**
 * Resolve (role, email) for the admin gate. Reads the session token first (free);
 * only when a needed claim is missing does it fall back to one getUser() call.
 * `needEmail` is true for the layout (it renders the email), false for the
 * middleware (role check only) so the API route path never fetches.
 */
export async function resolveAdmin(
  userId: string,
  claims: AdminClaims | null | undefined,
  needEmail = false,
): Promise<{ role?: string; email?: string }> {
  let role = roleFromClaims(claims);
  let email = claims?.email;
  if (role === undefined || (needEmail && !email)) {
    const user = await (await clerkClient()).users.getUser(userId);
    role = role ?? (user.publicMetadata as { role?: string })?.role;
    email = email ?? user.emailAddresses[0]?.emailAddress;
  }
  return { role, email };
}
