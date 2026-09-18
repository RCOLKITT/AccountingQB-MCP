#!/usr/bin/env node
/**
 * Generate the dashboard tools catalog from the canonical MCP manifest.
 *
 * Reads mcpb/manifest.json (the authoritative tool list — regenerated from
 * server.py by scripts/generate-schemas.py) and writes a compact, UI-friendly
 * catalog the dashboard renders: each tool's name, description, and whether it
 * WRITES to QuickBooks (write = NOT readOnlyHint). This keeps the in-app
 * read-only/write reference in lockstep with the real tools — no hand-maintained
 * drift. `tests/tools-catalog.test.ts` fails if the committed catalog is stale.
 *
 *   node scripts/generate-tools-catalog.mjs          # write the catalog
 *   node scripts/generate-tools-catalog.mjs --check  # verify committed == generated (CI)
 *
 * Run this after scripts/generate-schemas.py whenever tools change.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const MANIFEST = join(root, "mcpb", "manifest.json");
const OUT = join(root, "web", "src", "lib", "tools-catalog.json");

const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
const catalog = (manifest.tools || [])
  .map((t) => ({
    name: t.name,
    description: (t.description || "").trim(),
    // A tool writes to QuickBooks unless it is explicitly annotated read-only.
    write: !((t.annotations || {}).readOnlyHint === true || t.readOnlyHint === true),
  }))
  .sort((a, b) => a.name.localeCompare(b.name));

const serialized = JSON.stringify(catalog, null, 2) + "\n";

if (process.argv.includes("--check")) {
  const current = readFileSync(OUT, "utf8");
  if (current !== serialized) {
    console.error(
      "[tools-catalog] ✗ committed catalog is stale — run `node scripts/generate-tools-catalog.mjs`",
    );
    process.exit(1);
  }
  console.log(`[tools-catalog] ✓ up to date (${catalog.length} tools)`);
} else {
  writeFileSync(OUT, serialized);
  const reads = catalog.filter((t) => !t.write).length;
  console.log(
    `[tools-catalog] wrote ${catalog.length} tools (${reads} read-only, ${catalog.length - reads} write) → ${OUT}`,
  );
}
