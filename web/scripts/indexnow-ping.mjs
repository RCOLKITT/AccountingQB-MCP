// Instant re-crawl on every PRODUCTION deploy: submit the sitemap URLs to
// IndexNow (Bing/Yandex/Seznam + partners). Guarded to prod and always exits 0,
// so it can never fail a build. The key file lives in public/<hex>.txt.
import { readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

async function main() {
  if (process.env.VERCEL_ENV !== "production") {
    console.log("[indexnow] not prod — skip");
    return;
  }
  const SITE_URL = (process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com").replace(/\/$/, "");
  const host = new URL(SITE_URL).host;
  const publicDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
  const keyFile = readdirSync(publicDir).find((f) => /^[a-f0-9]{16,}\.txt$/.test(f));
  if (!keyFile) {
    console.log("[indexnow] no key file — skip");
    return;
  }
  const key = keyFile.replace(/\.txt$/, "");
  let urls = [`${SITE_URL}/`];
  try {
    const res = await fetch(`${SITE_URL}/sitemap.xml`, { signal: AbortSignal.timeout(8000) });
    if (res.ok) {
      const xml = await res.text();
      const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
      if (locs.length) urls = locs;
    }
  } catch {}
  const res = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ host, key, keyLocation: `${SITE_URL}/${keyFile}`, urlList: urls }),
    signal: AbortSignal.timeout(8000),
  });
  console.log(`[indexnow] submitted ${urls.length} url(s) -> HTTP ${res.status}`);
}

main()
  .catch((e) => console.log("[indexnow] skipped:", e?.message || e))
  .finally(() => process.exit(0));
