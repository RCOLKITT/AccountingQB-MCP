import {
  analyticsConfigured,
  getSiteAnalytics,
  type SiteAnalytics,
} from "@/lib/posthog-analytics";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  if (!analyticsConfigured()) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-white">Site Analytics</h1>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-sm text-amber-200/90">
          <p className="font-medium">Almost there — one key needed.</p>
          <p className="mt-2 text-amber-200/70">
            Add a PostHog <strong>read</strong> token to Doppler as{" "}
            <code>POSTHOG_READ_TOKEN</code> (us.posthog.com → Settings → Personal
            API keys → create with <em>read</em> scopes), then redeploy. Traffic
            will appear here automatically.
          </p>
        </div>
      </div>
    );
  }

  const a = await getSiteAnalytics();
  return <Dashboard a={a} />;
}

function Dashboard({ a }: { a: SiteAnalytics }) {
  const maxTrend = Math.max(1, ...a.trend.map((t) => t.views));
  const maxPage = Math.max(1, ...a.pages.map((p) => p.views));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Site Analytics</h1>
          <p className="text-gray-400 mt-1">
            Live from PostHog. Tag campaign links with{" "}
            <code className="text-gray-500">?utm_source=…&amp;utm_campaign=…</code>{" "}
            to see which channel drives traffic.
          </p>
        </div>
        <a
          href="https://us.posthog.com/project/527365"
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-gray-300 hover:text-white transition"
        >
          Open in PostHog ↗
        </a>
      </div>

      {/* Headline */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="Visitors · 7d" value={a.week.visitors} accent />
        <Metric label="Pageviews · 7d" value={a.week.views} />
        <Metric label="Visitors · 30d" value={a.month.visitors} />
        <Metric label="Pageviews · 30d" value={a.month.views} />
      </div>

      {/* Trend */}
      <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6">
        <h2 className="text-sm font-semibold text-white mb-4">
          Daily pageviews · last 14 days
        </h2>
        {a.trend.length === 0 ? (
          <p className="text-sm text-gray-500">No pageviews yet in this window.</p>
        ) : (
          <div className="flex items-end gap-1.5 h-32">
            {a.trend.map((t) => (
              <div key={t.day} className="flex-1 flex flex-col items-center gap-1 group">
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
        {/* Top pages */}
        <Panel title="Top pages · 30d">
          {a.pages.length === 0 ? (
            <Empty />
          ) : (
            a.pages.map((p) => (
              <div key={p.path} className="flex items-center gap-3 py-1.5">
                <span className="text-sm text-gray-300 flex-1 truncate font-mono">{p.path}</span>
                <div className="w-24 h-1.5 rounded bg-white/5 overflow-hidden">
                  <div className="h-full bg-cyan-500/50" style={{ width: `${(p.views / maxPage) * 100}%` }} />
                </div>
                <span className="text-sm text-gray-400 w-10 text-right">{p.views}</span>
              </div>
            ))
          )}
        </Panel>

        {/* Top sources */}
        <Panel title="Traffic sources · 30d">
          {a.sources.length === 0 ? (
            <Empty />
          ) : (
            a.sources.map((s) => (
              <div key={s.source} className="flex items-center justify-between py-1.5">
                <span className="text-sm text-gray-300 truncate">{s.source}</span>
                <span className="text-sm text-gray-400">{s.views}</span>
              </div>
            ))
          )}
        </Panel>
      </div>

      {/* UTM campaigns */}
      <Panel title="Campaign sources (UTM) · 30d">
        {a.utm.length === 0 ? (
          <p className="text-sm text-gray-500">
            No tagged campaigns yet. Add{" "}
            <code className="text-gray-400">?utm_source=twitter&amp;utm_campaign=launch</code>{" "}
            to your ad/marketing links, and each channel&rsquo;s visitors will show here — so you
            know exactly what&rsquo;s working.
          </p>
        ) : (
          a.utm.map((u) => (
            <div key={u.source} className="flex items-center justify-between py-1.5">
              <span className="text-sm text-cyan-300">{u.source}</span>
              <span className="text-sm text-gray-400">{u.visitors} visitors</span>
            </div>
          ))
        )}
      </Panel>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "border-cyan-500/40 bg-cyan-500/5" : "border-white/10 bg-[#131a2e]"}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent ? "text-cyan-300" : "text-white"}`}>
        {value.toLocaleString("en-US")}
      </p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#131a2e] rounded-xl border border-white/10 overflow-hidden">
      <div className="px-6 py-3 border-b border-white/5">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="px-6 py-3">{children}</div>
    </div>
  );
}

function Empty() {
  return <p className="text-sm text-gray-500 py-2">No data yet in this window.</p>;
}
