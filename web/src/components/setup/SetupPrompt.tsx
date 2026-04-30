"use client";

import { useState } from "react";

interface SetupPromptProps {
  licenseKey: string;
  hasClaudeConfigured?: boolean;
  hasQBConnected?: boolean;
}

export function SetupPrompt({
  licenseKey,
  hasClaudeConfigured = false,
  hasQBConnected = false,
}: SetupPromptProps) {
  const [copied, setCopied] = useState<"prompt" | "terminal" | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  const setupPrompt = `I want to set up AccountingQB, an MCP server that connects QuickBooks to Claude Desktop. My license key is: ${licenseKey}

Please help me set it up. Pick whichever option works in your current environment:

OPTION A — If you have filesystem access (Claude Desktop/Claude Code):

1. Read my Claude Desktop config file:
   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json
2. If it doesn't exist, create it with: {"mcpServers": {}}
3. Parse it as JSON and merge this entry into mcpServers (preserve all existing servers):

"accountingqb": {
  "command": "uvx",
  "args": ["accountingqb"],
  "env": {
    "QB_LICENSE_KEY": "${licenseKey}"
  }
}

4. Write the file back as valid JSON (pretty-printed, 2-space indent)
5. Tell me to fully quit Claude Desktop with Cmd+Q (macOS) or right-click tray → Quit (Windows). Closing the window is NOT enough.

OPTION B — If you can't access my filesystem (Cowork mode or claude.ai web):

Tell me to run this in my terminal:
  uvx accountingqb-setup --license-key ${licenseKey}

Or give me manual instructions to edit the config file myself.`;

  const terminalCommand = `uvx accountingqb-setup --license-key ${licenseKey}`;

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(setupPrompt);
    setCopied("prompt");
    setTimeout(() => setCopied(null), 3000);
  };

  const copyTerminal = async () => {
    await navigator.clipboard.writeText(terminalCommand);
    setCopied("terminal");
    setTimeout(() => setCopied(null), 3000);
  };

  const allComplete = hasClaudeConfigured && hasQBConnected;

  if (allComplete) {
    return (
      <div className="rounded-2xl border border-green-500/20 bg-green-500/5 p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20">
            <svg className="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-white">Setup Complete</h3>
            <p className="text-sm text-gray-400">
              You&apos;re all set! Open Claude Desktop and start asking questions about your books.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Get Started in 1 Minute</h3>
          <p className="mt-1 text-sm text-gray-400">
            Paste this into the <span className="text-white font-medium">Claude Desktop app</span> (not claude.ai web).
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`flex items-center gap-1 ${hasClaudeConfigured ? "text-green-400" : "text-gray-500"}`}>
            {hasClaudeConfigured ? (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01" />
              </svg>
            )}
            Claude
          </span>
          <span className={`flex items-center gap-1 ${hasQBConnected ? "text-green-400" : "text-gray-500"}`}>
            {hasQBConnected ? (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01" />
              </svg>
            )}
            QuickBooks
          </span>
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-4 sm:flex-row">
        <button
          onClick={copyPrompt}
          className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
        >
          {copied === "prompt" ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied! Paste in Claude Desktop App
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy Setup Prompt
            </span>
          )}
        </button>
        <button
          onClick={() => setShowPrompt(!showPrompt)}
          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-gray-400 transition hover:bg-white/5 hover:text-white"
        >
          {showPrompt ? "Hide" : "Preview"}
        </button>
      </div>

      {showPrompt && (
        <div className="mt-4 rounded-xl bg-black/40 p-4">
          <pre className="whitespace-pre-wrap text-xs text-gray-400 font-mono">
            {setupPrompt}
          </pre>
        </div>
      )}

      <div className="mt-6 rounded-xl bg-white/[0.03] p-4">
        <h4 className="text-sm font-medium text-white mb-3">How it works:</h4>
        <ol className="space-y-2 text-sm text-gray-400">
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">1</span>
            <span>Copy the prompt above</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">2</span>
            <span>Open the <span className="text-white">Claude Desktop app</span> (download at <a href="https://claude.ai/download" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">claude.ai/download</a>)</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">3</span>
            <span>Paste the prompt — Claude will edit your config file</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">4</span>
            <span>Quit (Cmd+Q) and reopen Claude Desktop</span>
          </li>
        </ol>
        <p className="mt-3 text-xs text-gray-500">
          Note: This works best in the Claude Desktop app or Claude Code.
        </p>
      </div>

      {/* Terminal alternative */}
      <div className="mt-4 rounded-xl bg-white/[0.03] p-4">
        <h4 className="text-sm font-medium text-white mb-2">Or run in Terminal:</h4>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-lg bg-black/40 px-3 py-2 text-sm text-cyan-400 font-mono overflow-x-auto">
            {terminalCommand}
          </code>
          <button
            onClick={copyTerminal}
            className="shrink-0 rounded-lg border border-white/10 px-3 py-2 text-sm text-gray-400 hover:bg-white/5 hover:text-white transition"
          >
            {copied === "terminal" ? "Copied!" : "Copy"}
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Requires <a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">uv</a> installed. Run <code className="text-cyan-400">uvx accountingqb-setup --doctor</code> to troubleshoot.
        </p>
      </div>

      {!hasQBConnected && (
        <div className="mt-4 text-center">
          <a
            href={`/api/oauth/start?license_key=${encodeURIComponent(licenseKey)}`}
            className="text-sm text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            Or connect QuickBooks manually
          </a>
        </div>
      )}
    </div>
  );
}
