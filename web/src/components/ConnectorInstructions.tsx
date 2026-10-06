"use client";

import { useState } from "react";

/**
 * The canonical "add AccountingQB as a custom connector in Claude" block —
 * connector URL + copy button + the 5 steps. Rendered on both /connect and
 * /setup-wizard so the steps never drift. The URL defaults to the production
 * connector so it is never hidden if NEXT_PUBLIC_REMOTE_MCP_URL is unset.
 */
export const REMOTE_MCP_URL =
  process.env.NEXT_PUBLIC_REMOTE_MCP_URL || "https://mcp.accountingqb.com/mcp";

export default function ConnectorInstructions() {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(REMOTE_MCP_URL);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div className="mt-2">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-gray-400">Connector URL</span>
          <button
            onClick={copy}
            className="rounded border border-white/10 px-3 py-1 text-xs transition hover:bg-white/10"
          >
            {copied ? "✓ Copied!" : "Copy"}
          </button>
        </div>
        <code className="block overflow-x-auto rounded-lg bg-black/40 px-4 py-3 text-sm text-cyan-400">
          {REMOTE_MCP_URL}
        </code>
      </div>

      <div className="mt-6 space-y-3 text-sm text-gray-300">
        <p>
          <strong className="text-white">Steps:</strong>
        </p>
        <ol className="list-inside list-decimal space-y-2 text-gray-400">
          <li>
            In Claude, open{" "}
            <span className="text-white">Settings → Connectors</span>
          </li>
          <li>
            Click <span className="text-white">Add custom connector</span>
          </li>
          <li>
            Paste the URL above and click{" "}
            <span className="text-white">Add</span>
          </li>
          <li>
            Click <span className="text-white">Connect</span> and sign in with
            your AccountingQB account
          </li>
          <li>Approve access for your license — that&apos;s it</li>
        </ol>
      </div>
    </div>
  );
}
