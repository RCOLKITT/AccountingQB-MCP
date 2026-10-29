// Editorial grouping of the tool catalog — the ONE human input in the tool-docs
// pipeline, and it is DATA (a name→category mapping), not prose. The data lives
// in tools-categories.json so scripts/generate-tools-catalog.mjs can read the
// same source this module serves to the dashboard. Everything derived from it
// (tools-catalog.json, support-kb/tools.md) is GENERATED — never hand-edit those;
// run `node scripts/generate-tools-catalog.mjs` (CI --check enforces parity).
// tools-catalog.test.ts asserts every tool is categorized exactly once.

import categories from "./tools-categories.json";

export interface ToolCategory {
  category: string;
  icon: string;
  blurb: string;
  tools: string[];
}

export const TOOL_CATEGORIES: ToolCategory[] = categories;
