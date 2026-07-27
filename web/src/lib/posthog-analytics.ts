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

// Internal-traffic filter: keep the public marketing site, drop app/admin/auth
// pages, exclude @vasperacapital.com identified users, and exclude internal IPs
// (INTERNAL_IPS — your office/dev IP, where QA hits also originate).
const NOT_INTERNAL_PAGE = [
  "admin", "dashboard", "api", "oauth", "sign-", "setup", "success",
]
  .map((p) => `properties.$pathname NOT LIKE '/${p}%'`)
  .join(" AND ");

function notInternalPerson(): string {
  const ips = (process.env.INTERNAL_IPS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const email =
    "(person.properties.email IS NULL OR person.properties.email NOT ILIKE '%@vasperacapital.com%')";
  const ipClause = ips.length
    ? ` AND properties.$ip NOT IN (${ips.map((ip) => `'${ip}'`).join(", ")})`
    : "";
  return email + ipClause;
}

export interface Row2 {
  label: string;
  value: number;
}

export interface SiteAnalytics {
  days: number;
  current: { views: number; visitors: number };
  previous: { views: number; visitors: number };
  trend: { day: string; views: number; visitors: number }[];
  pages: { path: string; views: number }[];
  sources: { source: string; views: number }[];
  utm: { source: string; visitors: number }[];
  geo: Row2[];
  devices: Row2[];
  newReturning: { newVisitors: number; returning: number };
}

export async function getSiteAnalytics(days: number): Promise<SiteAnalytics> {
  const person = notInternalPerson();
  const PV = `event = '$pageview' AND ${NOT_INTERNAL_PAGE} AND ${person}`;
  const win = `timestamp > now() - INTERVAL ${days} DAY`;
  const prevWin = `timestamp > now() - INTERVAL ${days * 2} DAY AND timestamp <= now() - INTERVAL ${days} DAY`;
  // Daily buckets up to 30d; weekly beyond so the chart stays readable at 90d.
  const bucket = days <= 30 ? "toDate(timestamp)" : "toStartOfWeek(timestamp)";

  // New vs returning: among visitors active in the window, is their first-ever
  // pageview inside the window (new) or before it (returning)?
  const newRetQ = `SELECT countIf(fs >= now() - INTERVAL ${days} DAY) AS n, countIf(fs < now() - INTERVAL ${days} DAY) AS r FROM (SELECT person_id, min(timestamp) AS fs FROM events WHERE event = '$pageview' AND ${NOT_INTERNAL_PAGE} AND ${person} GROUP BY person_id HAVING max(timestamp) >= now() - INTERVAL ${days} DAY)`;

  const [cur, prev, trend, pages, sources, utm, geo, devices, newRet] = await Promise.all([
    hog(`SELECT count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND ${win}`),
    hog(`SELECT count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND ${prevWin}`),
    hog(`SELECT ${bucket} AS d, count(), count(DISTINCT person_id) FROM events WHERE ${PV} AND ${win} GROUP BY d ORDER BY d`),
    hog(`SELECT properties.$pathname, count() FROM events WHERE ${PV} AND ${win} GROUP BY properties.$pathname ORDER BY count() DESC LIMIT 8`),
    hog(`SELECT coalesce(nullIf(properties.$referring_domain, ''), '(direct)'), count() FROM events WHERE ${PV} AND ${win} GROUP BY 1 ORDER BY count() DESC LIMIT 8`),
    hog(`SELECT properties.utm_source, count(DISTINCT person_id) FROM events WHERE ${win} AND properties.utm_source != '' AND ${person} GROUP BY properties.utm_source ORDER BY 2 DESC LIMIT 8`),
    hog(`SELECT coalesce(nullIf(properties.$geoip_country_name, ''), 'Unknown'), count(DISTINCT person_id) FROM events WHERE ${PV} AND ${win} GROUP BY 1 ORDER BY 2 DESC LIMIT 8`),
    hog(`SELECT coalesce(nullIf(properties.$device_type, ''), 'Unknown'), count(DISTINCT person_id) FROM events WHERE ${PV} AND ${win} GROUP BY 1 ORDER BY 2 DESC LIMIT 5`),
    hog(newRetQ),
  ]);

  return {
    days,
    current: { views: num(cur[0]?.[0]), visitors: num(cur[0]?.[1]) },
    previous: { views: num(prev[0]?.[0]), visitors: num(prev[0]?.[1]) },
    trend: trend.map((r) => ({ day: str(r[0]), views: num(r[1]), visitors: num(r[2]) })),
    pages: pages.map((r) => ({ path: str(r[0]) || "/", views: num(r[1]) })),
    sources: sources.map((r) => ({ source: str(r[0]), views: num(r[1]) })),
    utm: utm.map((r) => ({ source: str(r[0]), visitors: num(r[1]) })),
    geo: geo.map((r) => ({ label: str(r[0]), value: num(r[1]) })),
    devices: devices.map((r) => ({ label: str(r[0]), value: num(r[1]) })),
    newReturning: { newVisitors: num(newRet[0]?.[0]), returning: num(newRet[0]?.[1]) },
  };
}
