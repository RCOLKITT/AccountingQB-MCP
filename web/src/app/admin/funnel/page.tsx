import { getSupabase } from "@/lib/supabase";
import { getRetention } from "@/lib/retention";
import { unstable_cache } from "next/cache";
import Link from "next/link";

// Activation funnel: Signed up -> Connected QuickBooks -> Configured Claude ->
// Converted to paid. Computed from licenses + user_milestones (the data we
// already capture). Pre-signup web behavior lives in PostHog (Phase 1 #2).

export const dynamic = "force-dynamic";

type Range = "30" | "90" | "all";

interface Stage {
  label: string;
  count: number;
  hint: string;
}

interface FunnelData {
  stages: Stage[];
  signedUp: number;
  medianDaysToConnect: number | null;
  byTier: { tier: string; signups: number; converted: number }[];
  churned: number;
  activeNow: number;
  trialingNow: number;
}

function median(nums: number[]): number | null {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

async function getFunnel(
  range: Range,
  includeTest: boolean,
): Promise<FunnelData> {
  const supabase = getSupabase();
  const since =
    range === "all"
      ? null
      : new Date(
          Date.now() - Number(range) * 24 * 60 * 60 * 1000,
        ).toISOString();

  // Licenses in range (by signup date). Internal/demo accounts (is_test)
  // are excluded by default so the funnel reflects real users.
  let lq = supabase
    .from("licenses")
    .select("key, status, tier, created_at")
    .order("created_at", { ascending: false })
    .limit(5000);
  if (!includeTest) lq = lq.eq("is_test", false);
  if (since) lq = lq.gte("created_at", since);

  // The two reads are independent (milestones are filtered to these licenses in
  // JS below) — run them in parallel instead of back-to-back. NOTE:
  // user_milestones uses completed_at (not created_at) for the timestamp.
  const [{ data: licenses }, { data: ms }] = await Promise.all([
    lq,
    supabase
      .from("user_milestones")
      .select("license_key, milestone, completed_at")
      .in("milestone", [
        "signup",
        "qb_connected",
        "claude_configured",
        "trial_converted",
      ])
      .limit(20000),
  ]);
  const rows = licenses || [];
  const keys = new Set(rows.map((r) => r.key));

  const connected = new Map<string, string>(); // key -> qb_connected time
  const convertedM = new Set<string>();
  for (const m of ms || []) {
    if (!keys.has(m.license_key)) continue;
    if (m.milestone === "qb_connected" && !connected.has(m.license_key))
      connected.set(m.license_key, m.completed_at);
    else if (m.milestone === "trial_converted") convertedM.add(m.license_key);
  }

  // Converted = paid now OR ever recorded a conversion
  const convertedKeys = new Set<string>();
  const signupTime = new Map<string, string>();
  for (const r of rows) {
    signupTime.set(r.key, r.created_at);
    if (r.status === "active" || convertedM.has(r.key))
      convertedKeys.add(r.key);
  }

  const signedUp = rows.length;
  const connectedCount = [...connected.keys()].filter((k) =>
    keys.has(k),
  ).length;
  const convertedCount = convertedKeys.size;

  // Median days signup -> qb_connected
  const durations: number[] = [];
  for (const [key, t] of connected) {
    const su = signupTime.get(key);
    if (su) {
      const d = (new Date(t).getTime() - new Date(su).getTime()) / 86400000;
      if (d >= 0) durations.push(d);
    }
  }

  // Per-tier
  const tiers = ["solopreneur", "business", "firm"];
  const byTier = tiers.map((tier) => {
    const t = rows.filter((r) => r.tier === tier);
    return {
      tier,
      signups: t.length,
      converted: t.filter((r) => convertedKeys.has(r.key)).length,
    };
  });

  return {
    signedUp,
    stages: [
      { label: "Signed up", count: signedUp, hint: "license created" },
      {
        label: "Connected QuickBooks",
        count: connectedCount,
        hint: "qb_connected",
      },
      {
        label: "Converted to paid",
        count: convertedCount,
        hint: "active / trial_converted",
      },
    ],
    medianDaysToConnect: median(durations),
    byTier,
    churned: rows.filter(
      (r) => r.status === "canceled" || r.status === "expired",
    ).length,
    activeNow: rows.filter((r) => r.status === "active").length,
    trialingNow: rows.filter((r) => r.status === "trialing").length,
  };
}

function pct(n: number, d: number): string {
  if (!d) return "—";
  return `${Math.round((n / d) * 1000) / 10}%`;
}

export default async function FunnelPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string; test?: string }>;
}) {
  const sp = await searchParams;
  const range: Range =
    sp.range === "90" ? "90" : sp.range === "all" ? "all" : "30";
  const includeTest = sp.test === "1";
  // Cache per (range, includeTest) for 60s — the funnel scans licenses +
  // milestones, which doesn't change second-to-second.
  const load = unstable_cache(
    (r: Range, t: boolean) => Promise.all([getFunnel(r, t), getRetention()]),
    ["admin-funnel"],
    { revalidate: 60 },
  );
  const [f, cohorts] = await load(range, includeTest);
  const top = f.signedUp || 1;

  const ranges: { key: Range; label: string }[] = [
    { key: "30", label: "Last 30 days" },
    { key: "90", label: "Last 90 days" },
    { key: "all", label: "All time" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Activation Funnel</h1>
          <p className="text-gray-400 mt-1">
            Where signups drop off on the way to paying. Cohort by signup date.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={`/admin/funnel?range=${range}${includeTest ? "" : "&test=1"}`}
            className={`rounded-md border px-3 py-1.5 text-xs transition ${
              includeTest
                ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                : "border-white/10 bg-white/5 text-gray-400 hover:text-white"
            }`}
          >
            {includeTest ? "Including test accounts" : "Real users only"}
          </Link>
          <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
            {ranges.map((r) => (
              <Link
                key={r.key}
                href={`/admin/funnel?range=${r.key}${includeTest ? "&test=1" : ""}`}
                className={`rounded-md px-3 py-1.5 text-sm transition ${
                  range === r.key
                    ? "bg-cyan-500/20 text-cyan-300"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {r.label}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Funnel bars */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 space-y-4">
        {f.stages.map((s, i) => {
          const prev = i === 0 ? s.count : f.stages[i - 1].count;
          const stepConv = i === 0 ? null : pct(s.count, prev);
          const dropoff = i === 0 ? 0 : prev - s.count;
          const width = Math.max(4, Math.round((s.count / top) * 100));
          return (
            <div key={s.label}>
              <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="text-white font-medium">{s.label}</span>
                <span className="text-gray-400">
                  <span className="text-white font-semibold">{s.count}</span>{" "}
                  <span className="text-gray-500">
                    ({pct(s.count, top)} of signups)
                  </span>
                </span>
              </div>
              <div className="relative h-9 w-full rounded-md bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-md bg-gradient-to-r from-cyan-500/40 to-blue-600/40 border-r-2 border-cyan-400/60 flex items-center px-3"
                  style={{ width: `${width}%` }}
                >
                  <span className="text-xs text-cyan-100 font-mono">
                    {s.hint}
                  </span>
                </div>
              </div>
              {i > 0 && (
                <div className="flex items-center gap-3 mt-1 text-xs">
                  <span className="text-gray-500">
                    step conversion:{" "}
                    <span className="text-gray-300">{stepConv}</span>
                  </span>
                  {dropoff > 0 && (
                    <span className="text-amber-400/80">
                      ↓ lost {dropoff} here
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric
          label="Signup → Connected"
          value={pct(f.stages[1].count, f.signedUp)}
          sub="activation rate"
        />
        <Metric
          label="Signup → Paid"
          value={pct(f.stages[2].count, f.signedUp)}
          sub="overall conversion"
        />
        <Metric
          label="Median time to connect"
          value={
            f.medianDaysToConnect == null
              ? "—"
              : `${Math.round(f.medianDaysToConnect * 10) / 10}d`
          }
          sub="signup → QuickBooks"
        />
        <Metric
          label="Churned"
          value={String(f.churned)}
          sub="canceled + expired"
        />
      </div>

      {/* Conversion by tier */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="px-6 py-3 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">
            Conversion by tier
          </h2>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-white/5">
              <th className="px-6 py-2 font-medium">Tier</th>
              <th className="px-6 py-2 font-medium">Signups</th>
              <th className="px-6 py-2 font-medium">Converted</th>
              <th className="px-6 py-2 font-medium">Rate</th>
            </tr>
          </thead>
          <tbody>
            {f.byTier.map((t) => (
              <tr key={t.tier} className="border-b border-white/5">
                <td className="px-6 py-3 text-sm text-white capitalize">
                  {t.tier}
                </td>
                <td className="px-6 py-3 text-sm text-gray-300">{t.signups}</td>
                <td className="px-6 py-3 text-sm text-gray-300">
                  {t.converted}
                </td>
                <td className="px-6 py-3 text-sm text-cyan-400">
                  {pct(t.converted, t.signups)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Retention by signup cohort */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/5 px-6 py-3">
          <h2 className="text-sm font-semibold text-white">
            Retention by signup cohort
          </h2>
          <span className="text-xs text-gray-500">
            % of each month&rsquo;s signups paying now
          </span>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/5 text-left text-xs text-gray-400">
              <th className="px-6 py-2 font-medium">Cohort</th>
              <th className="px-6 py-2 font-medium">Signups</th>
              <th className="px-6 py-2 font-medium">Paying now</th>
              <th className="px-6 py-2 font-medium">In trial</th>
              <th className="px-6 py-2 font-medium">Churned</th>
              <th className="px-6 py-2 font-medium">Retention</th>
            </tr>
          </thead>
          <tbody>
            {cohorts
              .filter((c) => c.size > 0)
              .map((c) => (
                <tr key={c.month} className="border-b border-white/5">
                  <td className="px-6 py-3 text-sm text-white">{c.month}</td>
                  <td className="px-6 py-3 text-sm text-gray-300">{c.size}</td>
                  <td className="px-6 py-3 text-sm text-emerald-400">
                    {c.paying}
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-400">
                    {c.trialing}
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-400">
                    {c.churned}
                  </td>
                  <td className="px-6 py-3 text-sm text-cyan-400">
                    {Math.round(c.retentionPct)}%
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        <p className="px-6 py-3 text-xs text-gray-600">
          Newer cohorts show more &ldquo;in trial&rdquo; — they haven&rsquo;t
          settled yet. Read the older rows for a true retention signal.
        </p>
      </div>

      <p className="text-xs text-gray-600">
        Post-signup funnel from{" "}
        <code className="text-gray-500">user_milestones</code> (test/demo
        accounts excluded). Tool-usage telemetry was blocked by an auth rule and
        is now fixed — an &ldquo;activated (ran a tool)&rdquo; step will
        populate going forward and can be added here. Pre-signup web behavior
        (traffic, page clicks, checkout starts) lands in PostHog once the key is
        set — that becomes the top of this funnel.
      </p>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 p-5">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-white mt-1">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{sub}</p>
    </div>
  );
}
