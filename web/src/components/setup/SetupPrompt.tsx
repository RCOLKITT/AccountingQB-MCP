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
  const [copied, setCopied] = useState<"prompt" | "terminal" | "key" | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  // Prompt does NOT include the license key - Claude will ask for it
  const setupPrompt = `I want to set up AccountingQB, an MCP server that connects QuickBooks to Claude Desktop.

Please help me configure it:

1. Read my Claude Desktop config file:
   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   - Windows: %APPDATA%\\Claude\\claude_desktop_config.json
2. If it doesn't exist, create it with: {"mcpServers": {}}
3. Ask me for my license key. When I provide it, do NOT echo it back in your response.
4. Merge this entry into mcpServers (preserve existing servers):

"accountingqb": {
  "command": "uvx",
  "args": ["accountingqb"],
  "env": {
    "QB_LICENSE_KEY": "<my-license-key>"
  }
}

5. Write the file back as valid JSON (pretty-printed, 2-space indent)
6. Tell me to fully quit Claude Desktop with Cmd+Q (macOS) or right-click tray → Quit (Windows). Closing the window is NOT enough.`;

  const terminalCommand = `uvx accountingqb-setup --license-key ${licenseKey}`;

  const copyKey = async () => {
    await navigator.clipboard.writeText(licenseKey);
    setCopied("key");
    setTimeout(() => setCopied(null), 3000);
  };

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
            Paste this prompt into <span className="text-white font-medium">Claude Desktop</span> — no terminal required.
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

      {/* Primary: Claude prompt */}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          onClick={copyPrompt}
          className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
        >
          {copied === "prompt" ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied! Paste in Claude Desktop
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
          onClick={copyKey}
          className="rounded-xl border border-white/10 px-4 py-4 text-sm text-gray-400 transition hover:bg-white/5 hover:text-white"
        >
          {copied === "key" ? "Key Copied!" : "Copy License Key"}
        </button>
        <button
          onClick={() => setShowPrompt(!showPrompt)}
          className="rounded-xl border border-white/10 px-4 py-4 text-sm text-gray-400 transition hover:bg-white/5 hover:text-white"
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
            <span>Copy the prompt and paste it into <a href="https://claude.ai/download" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">Claude Desktop</a></span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">2</span>
            <span>Claude will ask for your license key — paste it when prompted</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">3</span>
            <span>Quit Claude Desktop with <span className="text-white">Cmd+Q</span> (macOS) or right-click tray → Quit (Windows)</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">4</span>
            <span>Reopen Claude Desktop — AccountingQB is now available</span>
          </li>
        </ol>
      </div>

      {/* Alternative: Terminal command */}
      <div className="mt-4 rounded-xl bg-white/[0.03] p-4">
        <h4 className="text-sm font-medium text-white mb-2">Alternative: Use Terminal</h4>
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
          Requires <a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">uv</a>. Run <code className="text-cyan-400">uvx accountingqb-setup --doctor</code> to troubleshoot.
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
