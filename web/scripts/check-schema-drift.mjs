#!/usr/bin/env node
/**
 * Schema-drift gate (VASPERA-SPINE G3).
 *
 * Compares the LIVE Supabase public schema (columns + indexes) against a committed
 * canonical snapshot (web/schema-snapshot.json). Fails on drift — i.e. the live DB
 * changed in a way not captured in git (an unmigrated manual change, or a migration
 * applied to the mirror but not to prod, or vice versa).
 *
 * Introspection goes through the `schema_snapshot()` SQL function via the service
 * role — no direct Postgres connection string needed, so it runs in CI with the
 * SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY secrets already present.
 *
 *   node scripts/check-schema-drift.mjs            # check; exit 1 on drift
 *   node scripts/check-schema-drift.mjs --update   # regenerate the snapshot (after
 *                                                   # an intentional schema change)
 *
 * Skips cleanly (exit 0) when creds are absent (fork PRs), like the e2e suite.
 */
import { createClient } from "@supabase/supabase-js";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SNAPSHOT = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "schema-snapshot.json",
);

const url = process.env.SUPABASE_URL || process.env.E2E_SUPABASE_URL;
const key =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.E2E_SUPABASE_SERVICE_ROLE_KEY;
const update = process.argv.includes("--update");

if (!url || !key) {
  console.log(
    "[schema-drift] Supabase creds absent — skipping (fork PR / local without creds).",
  );
  process.exit(0);
}

const supabase = createClient(url, key, { auth: { persistSession: false } });

const { data, error } = await supabase.rpc("schema_snapshot");
if (error) {
  console.error("[schema-drift] schema_snapshot() RPC failed:", error.message);
  process.exit(2);
}

// Stable, human-diffable serialization (the RPC already orders its arrays).
const live = JSON.stringify(data, null, 2) + "\n";

if (update) {
  writeFileSync(SNAPSHOT, live);
  console.log(`[schema-drift] Snapshot updated → ${SNAPSHOT}`);
  process.exit(0);
}

let committed;
try {
  committed = readFileSync(SNAPSHOT, "utf8");
} catch {
  console.error(
    `[schema-drift] No committed snapshot at ${SNAPSHOT}. Run with --update to create it.`,
  );
  process.exit(2);
}

if (committed === live) {
  console.log("[schema-drift] ✅ live schema matches the committed snapshot.");
  process.exit(0);
}

// Report a compact, actionable diff of the two entity sets.
const parse = (s) => {
  const j = JSON.parse(s);
  return {
    cols: new Set(
      (j.columns || []).map(
        (c) => `${c.table}.${c.column} ${c.type} null=${c.nullable}`,
      ),
    ),
    idx: new Set((j.indexes || []).map((i) => i.def)),
  };
};
const a = parse(committed);
const b = parse(live);
const diff = (setA, setB, label) => {
  for (const x of setB) if (!setA.has(x)) console.error(`  + [${label}] ${x}`);
  for (const x of setA) if (!setB.has(x)) console.error(`  - [${label}] ${x}`);
};

console.error(
  "[schema-drift] ❌ DRIFT: live schema differs from the committed snapshot.\n" +
    "  If this change is intentional, add a migration + mirror it in " +
    "supabase-schema.sql,\n  then regenerate: node scripts/check-schema-drift.mjs --update\n",
);
diff(a.cols, b.cols, "column");
diff(a.idx, b.idx, "index");
process.exit(1);
