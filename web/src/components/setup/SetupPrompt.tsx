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
  const [copied, setCopied] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);

  const setupPrompt = `I just signed up for AccountingQB and need help setting it up. Please configure the MCP server for me.

My license key is: ${licenseKey}

Please:
1. Add AccountingQB to my Claude MCP configuration file
2. The config should use uvx to run the accountingqb package
3. After updating the config, remind me to restart Claude Desktop
4. Then help me verify the connection by calling the verify endpoint

Here's the MCP config to add:
{
  "mcpServers": {
    "accountingqb": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "${licenseKey}"
      }
    }
  }
}

Config file locations:
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
- Windows: %APPDATA%\\Claude\\claude_desktop_config.json
- Linux: ~/.config/Claude/claude_desktop_config.json

After setup, I'll need to connect my QuickBooks account at: https://accountingqb.com/api/oauth/start?license_key=${encodeURIComponent(licenseKey)}`;

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(setupPrompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
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
            Copy this prompt into Claude Desktop to auto-configure everything.
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
          {copied ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied! Paste in Claude
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
            <span>Open Claude Desktop and paste it</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">3</span>
            <span>Claude will configure everything automatically</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">4</span>
            <span>Restart Claude Desktop when prompted</span>
          </li>
        </ol>
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
