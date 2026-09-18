import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import catalog from "./tools-catalog.json";
import { TOOL_CATEGORIES } from "./tools-categories";

// Binds the dashboard tools reference to reality: the committed catalog must match
// the canonical manifest (regenerate via scripts/generate-tools-catalog.mjs), and
// every tool must be categorized exactly once. A tool added/removed/flipped in the
// manifest, or a new tool left uncategorized, fails here — so the read-only/write
// reference users see can't silently drift.

const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "mcpb", "manifest.json"), "utf8"),
) as {
  tools: {
    name: string;
    readOnlyHint?: boolean;
    annotations?: { readOnlyHint?: boolean };
  }[];
};

describe("tools-catalog vs manifest", () => {
  it("catalog tool names exactly match the manifest", () => {
    const catNames = catalog.map((t) => t.name).sort();
    const manNames = manifest.tools.map((t) => t.name).sort();
    expect(catNames).toEqual(manNames);
  });

  it("each tool's write flag matches the manifest readOnlyHint (regenerate if this fails)", () => {
    const manRO = new Map(
      manifest.tools.map((t) => [
        t.name,
        t.annotations?.readOnlyHint === true || t.readOnlyHint === true,
      ]),
    );
    const mismatches = catalog.filter((t) => t.write === manRO.get(t.name));
    expect(mismatches.map((t) => t.name)).toEqual([]);
  });

  it("has real content (non-empty description) for every tool", () => {
    expect(catalog.every((t) => t.description.length > 0)).toBe(true);
  });
});

describe("category coverage", () => {
  const categorized = TOOL_CATEGORIES.flatMap((c) => c.tools);
  const catalogNames = new Set(catalog.map((t) => t.name));

  it("categorizes every catalog tool exactly once", () => {
    const seen = new Map<string, number>();
    for (const n of categorized) seen.set(n, (seen.get(n) ?? 0) + 1);
    const dupes = [...seen].filter(([, c]) => c > 1).map(([n]) => n);
    const missing = [...catalogNames].filter((n) => !seen.has(n));
    expect({ dupes, missing }).toEqual({ dupes: [], missing: [] });
  });

  it("has no categorized name that isn't a real tool", () => {
    const unknown = categorized.filter((n) => !catalogNames.has(n));
    expect(unknown).toEqual([]);
  });
});
