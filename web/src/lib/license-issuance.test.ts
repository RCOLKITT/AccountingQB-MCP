import { describe, it, expect, vi, beforeEach } from "vitest";

// Email side-effects are best-effort — mock them so tests never touch network,
// and so we can assert a send failure does NOT roll back the license.
const sendLicenseEmail = vi.fn();
const scheduleOnboardingEmails = vi.fn();
vi.mock("@/lib/resend", () => ({
  sendLicenseEmail: (...a: unknown[]) => sendLicenseEmail(...a),
}));
vi.mock("@/lib/emails/schedule-email", () => ({
  scheduleOnboardingEmails: (...a: unknown[]) => scheduleOnboardingEmails(...a),
}));

import { ensureTrialLicenseForEmail } from "./license-issuance";

// Minimal chainable Supabase stub. select/ilike/in/order/limit/eq return the
// builder; maybeSingle yields `existing`; insert records the row and honors an
// injected error only for the licenses table.
function mockSupabase(
  opts: {
    existing?: { key: string; email: string; tier: string } | null;
    licenseInsertError?: { message: string } | null;
  } = {},
) {
  const inserts: { table: string; row: Record<string, unknown> }[] = [];
  let table = "";
  const builder: Record<string, unknown> = {};
  Object.assign(builder, {
    select: () => builder,
    ilike: () => builder,
    in: () => builder,
    order: () => builder,
    limit: () => builder,
    eq: () => builder,
    maybeSingle: async () => ({ data: opts.existing ?? null, error: null }),
    insert: async (row: Record<string, unknown>) => {
      inserts.push({ table, row });
      if (table === "licenses" && opts.licenseInsertError)
        return { error: opts.licenseInsertError };
      return { error: null };
    },
  });
  const supa = {
    from: (t: string) => {
      table = t;
      return builder;
    },
  };
  return {
    supa: supa as unknown as Parameters<typeof ensureTrialLicenseForEmail>[0],
    inserts,
  };
}

beforeEach(() => {
  sendLicenseEmail.mockReset().mockResolvedValue(undefined);
  scheduleOnboardingEmails.mockReset().mockResolvedValue(undefined);
});

describe("ensureTrialLicenseForEmail", () => {
  it("creates a no-Stripe trialing license + signup milestone for a new email", async () => {
    const { supa, inserts } = mockSupabase({ existing: null });
    const r = await ensureTrialLicenseForEmail(supa, "New@Example.com");
    expect(r?.created).toBe(true);
    expect(r?.licenseKey).toMatch(/^LK-[0-9A-F]{32}$/);
    expect(r?.email).toBe("new@example.com"); // normalized

    const lic = inserts.find((i) => i.table === "licenses")!;
    expect(lic.row.status).toBe("trialing");
    expect(lic.row.email).toBe("new@example.com");
    expect(lic.row.trial_ends_at).toBeTruthy();
    expect(lic.row.stripe_subscription_id).toBeUndefined();
    expect(lic.row.stripe_customer_id).toBeUndefined();

    const ms = inserts.find((i) => i.table === "user_milestones")!;
    expect(ms.row.milestone).toBe("signup");
    expect((ms.row.metadata as { source: string }).source).toBe("download");

    expect(sendLicenseEmail).toHaveBeenCalledOnce();
    expect(scheduleOnboardingEmails).toHaveBeenCalledOnce();
  });

  it("is idempotent — reuses an existing live license and inserts nothing", async () => {
    const { supa, inserts } = mockSupabase({
      existing: { key: "LK-EXISTING", email: "a@b.com", tier: "business" },
    });
    const r = await ensureTrialLicenseForEmail(supa, "a@b.com");
    expect(r).toEqual({
      licenseKey: "LK-EXISTING",
      email: "a@b.com",
      tier: "business",
      created: false,
    });
    expect(inserts).toHaveLength(0);
    expect(sendLicenseEmail).not.toHaveBeenCalled();
  });

  it("does NOT roll back the license when the key email fails to send", async () => {
    sendLicenseEmail.mockRejectedValueOnce(new Error("resend down"));
    const { supa, inserts } = mockSupabase({ existing: null });
    const r = await ensureTrialLicenseForEmail(supa, "c@d.com");
    expect(r?.created).toBe(true); // license still issued
    expect(inserts.some((i) => i.table === "licenses")).toBe(true);
  });

  it("returns null when the license insert fails and there is no race winner", async () => {
    const { supa } = mockSupabase({
      existing: null,
      licenseInsertError: { message: "db down" },
    });
    const r = await ensureTrialLicenseForEmail(supa, "e@f.com");
    expect(r).toBeNull();
  });

  it("rejects an empty email", async () => {
    const { supa } = mockSupabase();
    expect(await ensureTrialLicenseForEmail(supa, "   ")).toBeNull();
  });
});
