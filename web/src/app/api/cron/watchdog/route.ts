import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { sendEmail } from "@/lib/emails/send-email";

/**
 * GET /api/cron/watchdog  (VASPERA-SPINE G2)
 *
 * Independent liveness check that pages by email on failure — beyond each service's
 * own /healthz. Probes the hosted MCP connector and the marketing site every few
 * minutes (Vercel Cron) and alerts ryan@vasperacapital.com on STATE TRANSITIONS,
 * tracked in the watchdog_state table:
 *   - DOWN alert once a check has failed FAIL_THRESHOLD consecutive times (rides out
 *     a single transient blip), then a re-alert at most every RE_ALERT_COOLDOWN,
 *   - a RECOVERED alert when it comes back.
 * So real outages page; healthy ticks are silent.
 *
 * NOTE: this runs ON Vercel, so it cannot detect a full Vercel/platform outage of the
 * web app itself — that needs an EXTERNAL dead-man switch (e.g. healthchecks.io),
 * which is the remaining half of G6. This covers connector-down (the revenue-critical
 * path: MCP tool calls) and app-level site breakage.
 *
 * Protected by CRON_SECRET.
 */

const FAIL_THRESHOLD = 2; // consecutive failures before the first page (anti-flap)
const RE_ALERT_COOLDOWN_MS = 6 * 60 * 60 * 1000; // re-page every 6h while still down
const PROBE_TIMEOUT_MS = 10_000;

interface Check {
  name: string;
  url: string;
  label: string;
}

interface StateRow {
  check_name: string;
  healthy: boolean;
  consecutive_failures: number;
  last_status: string | null;
  last_change: string | null;
  last_alert_at: string | null;
}

async function probe(url: string): Promise<{ ok: boolean; status: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      redirect: "manual",
      headers: { "user-agent": "AccountingQB-Watchdog/1" },
    });
    // <400 (incl. 3xx redirects) = reachable + serving; 4xx/5xx = unhealthy.
    return { ok: res.status < 400, status: `HTTP ${res.status}` };
  } catch (e) {
    return {
      ok: false,
      status: (e as Error).name === "AbortError" ? "timeout" : "unreachable",
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(req: NextRequest) {
  const cronSecret = process.env.CRON_SECRET;
  if (
    cronSecret &&
    req.headers.get("authorization") !== `Bearer ${cronSecret}`
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const alertTo = process.env.WATCHDOG_ALERT_EMAIL || "ryan@vasperacapital.com";
  const connectorHealth =
    process.env.CONNECTOR_HEALTH_URL || "https://mcp.accountingqb.com/healthz";
  const siteUrl = process.env.SITE_URL || "https://accountingqb.com";

  const checks: Check[] = [
    { name: "connector", url: connectorHealth, label: "MCP connector" },
    { name: "site", url: siteUrl, label: "Marketing site" },
  ];

  const supabase = getSupabase();
  const nowMs = Date.now();
  const nowIso = new Date().toISOString();
  const results: Array<{
    check: string;
    ok: boolean;
    status: string;
    alerted: boolean;
  }> = [];

  const { data: stateRows } = await supabase
    .from("watchdog_state")
    .select(
      "check_name, healthy, consecutive_failures, last_status, last_change, last_alert_at",
    );
  const stateByName = new Map<string, StateRow>();
  for (const r of (stateRows as StateRow[]) || [])
    stateByName.set(r.check_name, r);

  for (const check of checks) {
    const { ok, status } = await probe(check.url);
    const prev = stateByName.get(check.name);
    const wasHealthy = prev ? prev.healthy : true;
    const prevFailures = prev ? prev.consecutive_failures : 0;
    const lastAlertMs = prev?.last_alert_at
      ? new Date(prev.last_alert_at).getTime()
      : 0;

    // last_change only moves on an actual healthy↔down transition (informational).
    const transition = ok !== wasHealthy;
    const lastChange = transition ? nowIso : (prev?.last_change ?? nowIso);

    let alerted = false;

    if (!ok) {
      const failures = prevFailures + 1;
      // Page once failures cross the threshold, then re-page at most every cooldown.
      const shouldAlert =
        failures >= FAIL_THRESHOLD &&
        (wasHealthy ||
          !prev?.last_alert_at ||
          nowMs - lastAlertMs >= RE_ALERT_COOLDOWN_MS);
      if (shouldAlert) {
        await sendEmail({
          to: alertTo,
          subject: `🔴 [AccountingQB] ${check.label} is DOWN (${status})`,
          html: alertHtml(check, status, failures, nowIso),
        });
        alerted = true;
      }
      await supabase.from("watchdog_state").upsert(
        {
          check_name: check.name,
          healthy: false,
          consecutive_failures: failures,
          last_status: status,
          last_change: lastChange,
          last_alert_at: alerted ? nowIso : (prev?.last_alert_at ?? null),
          updated_at: nowIso,
        },
        { onConflict: "check_name" },
      );
    } else {
      // Recovered → notify once.
      if (prev && !wasHealthy) {
        await sendEmail({
          to: alertTo,
          subject: `🟢 [AccountingQB] ${check.label} RECOVERED (${status})`,
          html: recoveredHtml(check, status, nowIso),
        });
        alerted = true;
      }
      await supabase.from("watchdog_state").upsert(
        {
          check_name: check.name,
          healthy: true,
          consecutive_failures: 0,
          last_status: status,
          last_change: lastChange,
          last_alert_at: null,
          updated_at: nowIso,
        },
        { onConflict: "check_name" },
      );
    }

    results.push({ check: check.name, ok, status, alerted });
  }

  const allHealthy = results.every((r) => r.ok);
  return NextResponse.json({ ok: allHealthy, checks: results, at: nowIso });
}

function alertHtml(
  check: Check,
  status: string,
  failures: number,
  at: string,
): string {
  return `<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;color:#111">
    <h2 style="margin:0 0 8px">🔴 ${check.label} is DOWN</h2>
    <p style="margin:0 0 12px;color:#444">The watchdog could not reach a healthy response.</p>
    <table style="border-collapse:collapse;font-size:14px">
      <tr><td style="padding:4px 12px 4px 0;color:#666">Check</td><td><code>${check.name}</code></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">URL</td><td><code>${check.url}</code></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">Status</td><td><b>${status}</b></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">Consecutive failures</td><td>${failures}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">Detected</td><td>${at}</td></tr>
    </table>
    <p style="margin:12px 0 0;color:#888;font-size:12px">You'll get one more alert at most every 6h while it stays down, and a recovery notice when it's back.</p>
  </div>`;
}

function recoveredHtml(check: Check, status: string, at: string): string {
  return `<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;color:#111">
    <h2 style="margin:0 0 8px">🟢 ${check.label} recovered</h2>
    <table style="border-collapse:collapse;font-size:14px">
      <tr><td style="padding:4px 12px 4px 0;color:#666">Check</td><td><code>${check.name}</code></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">Status</td><td><b>${status}</b></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#666">Recovered</td><td>${at}</td></tr>
    </table>
  </div>`;
}
