import crypto from "crypto";
import { getSupabase } from "@/lib/supabase";

// Stateless, tamper-proof unsubscribe links (HMAC over the email) + the
// marketing suppression list. Transactional email never checks suppression;
// only campaigns/marketing do (CAN-SPAM / CASL).

const SECRET =
  process.env.UNSUBSCRIBE_SECRET ||
  process.env.CRON_SECRET ||
  "dev-unsub-secret";

function baseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_BASE_URL ||
    process.env.NEXT_PUBLIC_APP_URL ||
    "https://accountingqb.com"
  );
}

export function unsubscribeToken(email: string): string {
  return crypto
    .createHmac("sha256", SECRET)
    .update(email.trim().toLowerCase())
    .digest("hex")
    .slice(0, 32);
}

export function verifyUnsubscribe(email: string, token: string): boolean {
  const expected = unsubscribeToken(email);
  // constant-time compare
  const a = Buffer.from(expected);
  const b = Buffer.from(token || "");
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

export function unsubscribeUrl(email: string): string {
  const e = encodeURIComponent(email.trim().toLowerCase());
  return `${baseUrl()}/api/unsubscribe?e=${e}&t=${unsubscribeToken(email)}`;
}

/** True if the address has opted out of marketing (or everything). */
export async function isSuppressed(email: string): Promise<boolean> {
  const supabase = getSupabase();
  const { data } = await supabase
    .from("email_unsubscribes")
    .select("email")
    .eq("email", email.trim().toLowerCase())
    .maybeSingle();
  return !!data;
}

/** Filter a list of addresses down to those NOT suppressed. */
export async function filterSuppressed(emails: string[]): Promise<Set<string>> {
  const supabase = getSupabase();
  const lowered = emails.map((e) => e.trim().toLowerCase());
  const { data } = await supabase
    .from("email_unsubscribes")
    .select("email")
    .in("email", lowered);
  return new Set((data || []).map((r) => r.email));
}

export async function suppress(
  email: string,
  source: string,
  reason?: string,
): Promise<void> {
  const supabase = getSupabase();
  await supabase.from("email_unsubscribes").upsert(
    {
      email: email.trim().toLowerCase(),
      scope: "marketing",
      source,
      reason: reason || null,
    },
    { onConflict: "email" },
  );
}
