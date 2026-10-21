import { getSupabase } from "./supabase";
import { logEvent } from "./event-logger";

// Single source of truth for the current legal-document version + date. Bump
// BOTH when Terms or Privacy change materially; the value is stamped onto every
// recorded acceptance and shown on the policy pages, so a stored acceptance
// always says exactly which text the user agreed to.
export const POLICY_VERSION = "2026-10-21";
export const POLICY_LAST_UPDATED = "October 2026";

export type LegalDoc = "tos" | "privacy";

export interface RecordAcceptanceOpts {
  email: string;
  documents?: LegalDoc[]; // default: both ToS + Privacy
  clerkId?: string | null;
  ip?: string | null;
  userAgent?: string | null;
  context?: string; // where it happened: 'checkout' | 'trial_download' | ...
}

/**
 * Record a first-party ToS/Privacy acceptance. Non-blocking and best-effort:
 * consent capture must never break the checkout/trial flow it rides on. Writes
 * one row per document to `legal_acceptances` and mirrors a single audit row to
 * `event_logs` (Constitution: every consequential action leaves a row).
 */
export async function recordAcceptance(
  opts: RecordAcceptanceOpts,
): Promise<void> {
  const email = (opts.email || "").trim().toLowerCase();
  if (!email) return;
  const documents = opts.documents ?? ["tos", "privacy"];
  const acceptedAt = new Date().toISOString();

  try {
    const supabase = getSupabase();
    const { error } = await supabase.from("legal_acceptances").insert(
      documents.map((document) => ({
        email,
        clerk_id: opts.clerkId ?? null,
        document,
        version: POLICY_VERSION,
        accepted_at: acceptedAt,
        ip: opts.ip ?? null,
        user_agent: opts.userAgent ?? null,
        context: opts.context ?? null,
      })),
    );
    if (error) console.error("recordAcceptance insert failed:", error.message);
  } catch (err) {
    console.error("recordAcceptance error:", err);
  }

  // Audit mirror (non-blocking; logEvent swallows its own errors).
  await logEvent({
    eventType: "legal_acceptance",
    action: `accepted:${documents.join("+")}`,
    payload: { email, version: POLICY_VERSION, context: opts.context ?? null },
    success: true,
  });
}
