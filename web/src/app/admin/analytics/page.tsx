import Link from "next/link";
import { unstable_cache } from "next/cache";
import { getSupabase } from "@/lib/supabase";
import {
  analyticsConfigured,
  getSiteAnalytics,
  type SiteAnalytics,
  type Row2,
} from "@/lib/posthog-analytics";

// PostHog HogQL queries are the slow part here — cache per range for 5 minutes.
const getAnalytics = unstable_cache(
  (days: number) => Promise.all([getSiteAnalytics(days), getSignups(days)]),
  ["admin-analytics"],
  { revalidate: 300 }
);

async function getSignups(days: number): Promise<number> {
  const since = new Date(Date.now() - days * 86400000).toISOString();
  const { count } = await getSupabase()
    .from("licenses")
    .select("*", { count: "exact", head: true })
    .eq("is_test", false)
    .gte("created_at", since);
  return count || 0;
}

export const dynamic = "force-dynamic";

const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
];

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  if (!analyticsConfigured()) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-white">Site Analytics</h1>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-sm text-amber-200/90">
          Add a PostHog <strong>read</strong> token to Doppler as{" "}
          <code>POSTHOG_READ_TOKEN</code>, then redeploy.
        </div>
      </div>
    );
  }
  const sp = await searchParams;
  const days = sp.days === "7" ? 7 : sp.days === "90" ? 90 : 30;
  const [a, signups] = await getAnalytics(days);
  return <Dashboard a={a} days={days} signups={signups} />;
}

function pct(cur: number, prev: number): { txt: string; up: boolean | null } {
  if (!prev) return { txt: cur > 0 ? "new" : "—", up: cur > 0 ? true : null };
  const change = Math.round(((cur - prev) / prev) * 100);
  return { txt: `${change >= 0 ? "+" : ""}${change}%`, up: change >= 0 };
}

function Dashboard({ a, days, signups }: { a: SiteAnalytics; days: number; signups: number }) {
  const maxTrend = Math.max(1, ...a.trend.map((t) => t.views));
  const vCh = pct(a.current.visitors, a.previous.visitors);
  const pCh = pct(a.current.views, a.previous.views);
  const nr = a.newReturning;
  const nrTotal = Math.max(1, nr.newVisitors + nr.returning);
  const siteConv = a.current.visitors
    ? Math.round((signups / a.current.visitors) * 1000) / 10
    : 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Site Analytics</h1>
          <p className="text-gray-400 mt-1 text-sm">
            External visitors only (your team &amp; QA traffic filtered out). Tag
            campaign links with <code className="text-gray-500">?utm_source=…</code>.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
            {RANGES.map((r) => (
              <Link
                key={r.days}
                href={`/admin/analytics?days=${r.days}`}
                className={`rounded-md px-3 py-1.5 text-sm transition ${
                  days === r.days ? "bg-cyan-500/20 text-cyan-300" : "text-gray-400 hover:text-white"
                }`}
              >
                {r.label}
              </Link>
            ))}
          </div>
          <a
            href="https://us.posthog.com/project/527365"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-gray-300 hover:text-white transition"
          >
            PostHog ↗
          </a>
        </div>
      </div>

      {/* Headline with period-over-period growth */}
      <div className="grid grid-cols-2 gap-4 md:max-w-lg">
        <BigMetric label={`Visitors · ${days}d`} value={a.current.visitors} change={vCh} accent />
        <BigMetric label={`Pageviews · ${days}d`} value={a.current.views} change={pCh} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Pre-signup funnel: site visitors -> signups (marketing-site conversion) */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <h2 className="text-sm font-semibold text-white">Pre-signup funnel · {days}d</h2>
          <p className="text-xs text-gray-500 mt-1">
            Site conversion:{" "}
            <span className="text-cyan-400 font-semibold">{siteConv}%</span> of visitors sign up.
          </p>
          <div className="mt-4 space-y-3">
            <FunnelBar label="Visited site" value={a.current.visitors} top={a.current.visitors} hint="unique visitors" />
            <FunnelBar label="Signed up" value={signups} top={a.current.visitors} hint="new licenses" />
          </div>
          <p className="text-xs text-gray-600 mt-4">
            Then <Link href="/admin/funnel" className="text-cyan-400/80 hover:underline">activation → paid continues in the funnel →</Link>
          </p>
        </div>

        {/* New vs returning */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
          <h2 className="text-sm font-semibold text-white">New vs returning · {days}d</h2>
          <p className="text-xs text-gray-500 mt-1">
            Returning visitors are a sign your content &amp; retargeting are landing.
          </p>
          <div className="mt-4 flex h-6 w-full overflow-hidden rounded-lg">
            <div className="bg-cyan-500/60 flex items-center justify-center text-[10px] text-white" style={{ width: `${(nr.newVisitors / nrTotal) * 100}%` }}>
              {nr.newVisitors > 0 ? "new" : ""}
            </div>
            <div className="bg-blue-600/50 flex items-center justify-center text-[10px] text-white" style={{ width: `${(nr.returning / nrTotal) * 100}%` }}>
              {nr.returning > 0 ? "returning" : ""}
            </div>
          </div>
          <div className="mt-3 flex gap-6 text-sm">
            <span className="text-gray-300"><span className="text-cyan-400 font-semibold">{nr.newVisitors}</span> new</span>
            <span className="text-gray-300"><span className="text-blue-400 font-semibold">{nr.returning}</span> returning</span>
          </div>
        </div>
      </div>

      {/* Trend */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h2 className="text-sm font-semibold text-white mb-4">
          {days <= 30 ? "Daily" : "Weekly"} pageviews · last {days} days
        </h2>
        {a.trend.length === 0 ? (
          <p className="text-sm text-gray-500">No external pageviews yet in this window.</p>
        ) : (
          <div className="flex items-end gap-1.5 h-32">
            {a.trend.map((t) => (
              <div key={t.day} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex items-end h-full">
                  <div
                    className="w-full rounded-t bg-gradient-to-t from-cyan-500/30 to-cyan-400/70"
                    style={{ height: `${Math.max(2, (t.views / maxTrend) * 100)}%` }}
                    title={`${t.day}: ${t.views} views, ${t.visitors} visitors`}
                  />
                </div>
                <span className="text-[9px] text-gray-600">{t.day.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <BarPanel title={`Top pages · ${days}d`} rows={a.pages.map((p) => ({ label: p.path, value: p.views }))} mono />
        <BarPanel title={`Traffic sources · ${days}d`} rows={a.sources.map((s) => ({ label: s.source, value: s.views }))} />
        <BarPanel title={`Geography · ${days}d`} rows={a.geo} unit="visitors" />
        <BarPanel title={`Devices · ${days}d`} rows={a.devices} unit="visitors" />
      </div>

      {/* UTM campaigns */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
        <div className="px-6 py-3 border-b border-white/5">
          <h2 className="text-sm font-semibold text-white">Campaign sources (UTM) · {days}d</h2>
        </div>
        <div className="px-6 py-3">
          {a.utm.length === 0 ? (
            <p className="text-sm text-gray-500">
              No tagged campaigns yet. Add{" "}
              <code className="text-gray-400">?utm_source=twitter&amp;utm_campaign=launch</code>{" "}
              to your ad links and each channel&rsquo;s visitors show here.
            </p>
          ) : (
            a.utm.map((u) => (
              <div key={u.source} className="flex items-center justify-between py-1.5">
                <span className="text-sm text-cyan-300">{u.source}</span>
                <span className="text-sm text-gray-400">{u.visitors} visitors</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function BigMetric({
  label,
  value,
  change,
  accent,
}: {
  label: string;
  value: number;
  change: { txt: string; up: boolean | null };
  accent?: boolean;
}) {
  const color =
    change.up === null ? "text-gray-500" : change.up ? "text-green-400" : "text-red-400";
  return (
    <div className={`rounded-xl border p-5 ${accent ? "border-cyan-500/40 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <p className={`text-3xl font-bold ${accent ? "text-cyan-300" : "text-white"}`}>
          {value.toLocaleString("en-US")}
        </p>
        <span className={`text-sm ${color}`}>
          {change.up === true && change.txt !== "new" ? "↑ " : change.up === false ? "↓ " : ""}
          {change.txt}
        </span>
      </div>
      <p className="text-[11px] text-gray-600 mt-0.5">vs prior {label.match(/\d+/)?.[0]}d</p>
    </div>
  );
}

function FunnelBar({
  label,
  value,
  top,
  hint,
}: {
  label: string;
  value: number;
  top: number;
  hint: string;
}) {
  const w = top ? Math.max(4, (value / top) * 100) : 4;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-white">{label}</span>
        <span className="text-gray-400">
          <span className="text-white font-semibold">{value}</span>{" "}
          <span className="text-gray-500 text-xs">{hint}</span>
        </span>
      </div>
      <div className="h-7 w-full rounded-md bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-md bg-gradient-to-r from-cyan-500/40 to-blue-600/40"
          style={{ width: `${w}%` }}
        />
      </div>
    </div>
  );
}

function BarPanel({
  title,
  rows,
  mono,
  unit,
}: {
  title: string;
  rows: Row2[];
  mono?: boolean;
  unit?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
      <div className="px-6 py-3 border-b border-white/5">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="px-6 py-3">
        {rows.length === 0 ? (
          <p className="text-sm text-gray-500 py-2">No data yet.</p>
        ) : (
          rows.map((r) => (
            <div key={r.label} className="flex items-center gap-3 py-1.5">
              <span className={`text-sm text-gray-300 flex-1 truncate ${mono ? "font-mono" : ""}`}>
                {r.label}
              </span>
              <div className="w-24 h-1.5 rounded bg-white/5 overflow-hidden">
                <div className="h-full bg-cyan-500/50" style={{ width: `${(r.value / max) * 100}%` }} />
              </div>
              <span className="text-sm text-gray-400 w-14 text-right">
                {r.value}
                {unit ? "" : ""}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
