import { readFileSync } from "fs";
import { join } from "path";

// Knowledge base content loaded at build time
const KB_FILES = [
  "installation.md",
  "oauth.md",
  "tools.md",
  "common-issues.md",
  "account.md",
];

let cachedKB: string | null = null;

/**
 * Load and combine all knowledge base markdown files.
 * Content is cached after first load for performance.
 */
export function loadKnowledgeBase(): string {
  if (cachedKB) return cachedKB;

  const kbDir = join(process.cwd(), "src/lib/support-kb");
  const sections: string[] = [];

  for (const file of KB_FILES) {
    try {
      const content = readFileSync(join(kbDir, file), "utf-8");
      sections.push(content);
    } catch {
      console.warn(`[support-kb] Could not load ${file}`);
    }
  }

  cachedKB = sections.join("\n\n---\n\n");
  return cachedKB;
}

/**
 * Get a summary of available KB topics for the system prompt.
 */
export function getKBTopics(): string[] {
  return [
    "Installation & Setup (remote connector, desktop extension, Claude Desktop config, uv, license key)",
    "QuickBooks OAuth & Connection (authorization, token refresh, multiple companies)",
    "113 QuickBooks Tools (reports, transactions, US & Canadian tax prep, smart features)",
    "Common Issues & Troubleshooting (errors, fixes, FAQ)",
    "Account & Billing (pricing, plans, cancel, refunds)",
  ];
}

/**
 * Build the system prompt for the support agent.
 */
export function buildSupportSystemPrompt(context?: {
  licenseKey?: string;
  tier?: string;
  companies?: string[];
  currentPage?: string;
}): string {
  const kb = loadKnowledgeBase();

  let contextInfo = "";
  if (context?.licenseKey) {
    contextInfo += `\nUser's license tier: ${context.tier || "unknown"}`;
  }
  if (context?.companies?.length) {
    contextInfo += `\nConnected companies: ${context.companies.join(", ")}`;
  }
  if (context?.currentPage) {
    contextInfo += `\nUser is currently on: ${context.currentPage}`;
  }

  return `You are the AccountingQB Support Agent. You help users with:
- Installing AccountingQB in Claude Desktop or connecting via the remote connector (Claude web/desktop/mobile)
- Connecting QuickBooks Online accounts
- Understanding the 101 available MCP tools (US & Canadian tax prep included)
- Troubleshooting common issues
- Account and billing questions

${contextInfo ? `USER CONTEXT:${contextInfo}` : "User is not logged in."}

KNOWLEDGE BASE:
${kb}

GUIDELINES:
- Be concise and helpful
- Provide step-by-step instructions when applicable
- Use markdown formatting for clarity
- If you cannot resolve the issue, suggest emailing support@vasperacapital.com
- Never make up information about features that don't exist
- For billing questions, direct users to their dashboard at accountingqb.com/dashboard
- Be friendly but professional`;
}
