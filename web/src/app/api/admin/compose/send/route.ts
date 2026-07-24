import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import { sendEmail } from "@/lib/emails/send-email";
import { campaignEmail, type CampaignContent } from "@/lib/emails/templates/campaign";
import { filterSuppressed } from "@/lib/emails/unsubscribe";

// Send a composed marketing email. mode:
//   'test'   -> render + send once to the admin's own inbox
//   'dryRun' -> resolve the cohort and return the recipient count only
//   'send'   -> schedule a throttled campaign into email_schedules (the cron
//               sends them, spread over time). Excludes test accounts +
//               unsubscribers. Marketing footer/unsubscribe attached per-recipient.

const COHORTS = ["active", "trialing", "stuck", "canceled", "all"];

async function resolveCohort(cohort: string): Promise<{ key: string; email: string }[]> {
  const supabase = getSupabase();
  let q = supabase
    .from("licenses")
    .select("key, email, status")
    .eq("is_test", false)
    .not("email", "is", null)
    .limit(5000);

  if (cohort === "active") q = q.eq("status", "active");
  else if (cohort === "trialing") q = q.eq("status", "trialing");
  else if (cohort === "canceled") q = q.eq("status", "canceled");
  else if (cohort === "stuck") q = q.eq("status", "trialing");
  // 'all' → no status filter

  const { data } = await q;
  let rows = (data || []).filter((r) => r.email);

  if (cohort === "stuck") {
    // trialing AND no qb_connected milestone
    const { data: connected } = await supabase
      .from("user_milestones")
      .select("license_key")
      .eq("milestone", "qb_connected");
    const connectedKeys = new Set((connected || []).map((m) => m.license_key));
    rows = rows.filter((r) => !connectedKeys.has(r.key));
  }

  // De-dupe by email (a person may hold multiple licenses)
  const seen = new Set<string>();
  const out: { key: string; email: string }[] = [];
  for (const r of rows) {
    const e = r.email.trim().toLowerCase();
    if (seen.has(e)) continue;
    seen.add(e);
    out.push({ key: r.key, email: e });
  }
  return out;
}

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if ((user.publicMetadata as { role?: string })?.role !== "admin")
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const adminEmail = user.emailAddresses[0]?.emailAddress || "";

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const content = body.content as CampaignContent;
  const cohort = String(body.cohort || "all");
  const mode = String(body.mode || "dryRun");
  const perHour = Math.max(1, Math.min(500, Number(body.perHour) || 60));

  if (!content?.subject || !(content.paragraphs?.length))
    return NextResponse.json({ error: "Draft needs a subject and body" }, { status: 400 });
  if (!COHORTS.includes(cohort))
    return NextResponse.json({ error: "Invalid cohort" }, { status: 400 });

  // Test send → admin's own inbox, immediately.
  if (mode === "test") {
    if (!adminEmail)
      return NextResponse.json({ error: "No admin email on file" }, { status: 400 });
    const { subject, html } = campaignEmail(content, adminEmail);
    const r = await sendEmail({ to: adminEmail, subject: `[TEST] ${subject}`, html });
    return NextResponse.json({ test: true, to: adminEmail, ok: r.success });
  }

  // Resolve cohort, drop unsubscribed.
  const recipients = await resolveCohort(cohort);
  const suppressed = await filterSuppressed(recipients.map((r) => r.email));
  const eligible = recipients.filter((r) => !suppressed.has(r.email));

  if (mode === "dryRun") {
    return NextResponse.json({
      dryRun: true,
      cohort,
      total: recipients.length,
      suppressed: suppressed.size,
      eligible: eligible.length,
    });
  }

  if (mode !== "send")
    return NextResponse.json({ error: "Invalid mode" }, { status: 400 });
  if (!eligible.length)
    return NextResponse.json({ error: "No eligible recipients" }, { status: 400 });

  // Schedule throttled: spread scheduled_for so the cron sends ~perHour/hour.
  const supabase = getSupabase();
  const now = Date.now();
  const gapMs = (60 * 60 * 1000) / perHour;
  const rows = eligible.map((r, i) => ({
    license_key: r.key,
    email_type: "campaign",
    scheduled_for: new Date(now + i * gapMs).toISOString(),
    metadata: { ...content, campaign: true, cohort, sentBy: adminEmail },
  }));

  // Insert in chunks to stay under payload limits.
  let scheduled = 0;
  for (let i = 0; i < rows.length; i += 200) {
    const chunk = rows.slice(i, i + 200);
    const { error } = await supabase.from("email_schedules").insert(chunk);
    if (error) {
      console.error("Campaign schedule insert failed:", error);
      return NextResponse.json(
        { error: "Failed to schedule", scheduled },
        { status: 500 }
      );
    }
    scheduled += chunk.length;
  }

  console.log(`Campaign scheduled: ${scheduled} to '${cohort}' by ${adminEmail}`);
  return NextResponse.json({
    sent: true,
    scheduled,
    cohort,
    perHour,
    approxHours: Math.ceil(scheduled / perHour),
  });
}
