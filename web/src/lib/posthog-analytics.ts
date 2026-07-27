// Server-side reader for the AccountingQB PostHog project. Powers /admin/analytics.
// Uses a read-scoped personal API key (POSTHOG_READ_TOKEN) — never exposed to
// the browser. No-ops gracefully when unconfigured.

const TOKEN = process.env.POSTHOG_READ_TOKEN;
const PID = process.env.POSTHOG_PROJECT_ID;
const HOST = process.env.POSTHOG_HOST || "https://us.posthog.com";

export function analyticsConfigured(): boolean {
  return !!(TOKEN && PID);
}

async function hog(query: string): Promise<unknown[][]> {
  try {
    const res = await fetch(`${HOST}/api/projects/${PID}/query/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: { kind: "HogQLQuery", query } }),
      cache: "no-store",
    });
    if (!res.ok) return [];
    const d = await res.json();
    return (d.results as unknown[][]) || [];
  } catch {
    return [];
  }
}

const num = (v: unknown): number => Number(v) || 0;
const str = (v: unknown): string => (v == null ? "" : String(v));

export interface SiteAnalytics {
  week: { views: number; visitors: number };
  month: { views: number; visitors: number };
  trend: { day: string; views: number; visitors: number }[];
  pages: { path: string; views: number }[];
  sources: { source: string; views: number }[];
  utm: { source: string; visitors: number }[];
}

export async function getSiteAnalytics(): Promise<SiteAnalytics> {
  const PV = "event = '$pageview'";
  const [d7, d30, trend, pages, sources, utm] = await Promise.all([
    hog(`SELECT count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND timestamp > now() - INTERVAL 7 DAY`),
    hog(`SELECT count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND timestamp > now() - INTERVAL 30 DAY`),
    hog(`SELECT toDate(timestamp) AS d, count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND timestamp > now() - INTERVAL 14 DAY GROUP BY d ORDER BY d`),
    hog(`SELECT properties.$pathname, count() FROM events WHERE ${PV} AND timestamp > now() - INTERVAL 30 DAY GROUP BY properties.$pathname ORDER BY count() DESC LIMIT 8`),
    hog(`SELECT coalesce(nullIf(properties.$referring_domain, ''), '(direct)'), count() FROM events WHERE ${PV} AND timestamp > now() - INTERVAL 30 DAY GROUP BY 1 ORDER BY count() DESC LIMIT 8`),
    hog(`SELECT properties.utm_source, count(DISTINCT person_id) FROM events WHERE timestamp > now() - INTERVAL 30 DAY AND properties.utm_source != '' GROUP BY properties.utm_source ORDER BY 2 DESC LIMIT 8`),
  ]);

  return {
    week: { views: num(d7[0]?.[0]), visitors: num(d7[0]?.[1]) },
    month: { views: num(d30[0]?.[0]), visitors: num(d30[0]?.[1]) },
    trend: trend.map((r) => ({ day: str(r[0]), views: num(r[1]), visitors: num(r[2]) })),
    pages: pages.map((r) => ({ path: str(r[0]) || "/", views: num(r[1]) })),
    sources: sources.map((r) => ({ source: str(r[0]), views: num(r[1]) })),
    utm: utm.map((r) => ({ source: str(r[0]), visitors: num(r[1]) })),
  };
}
