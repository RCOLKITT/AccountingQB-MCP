"use client";

import { useState, useEffect } from "react";

type Platform = "mac" | "windows" | "linux" | "unknown";

function detectPlatform(): Platform {
  if (typeof window === "undefined") return "unknown";
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "mac";
  if (ua.includes("linux")) return "linux";
  return "unknown";
}

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
  const [platform, setPlatform] = useState<Platform>("unknown");
  const [copied, setCopied] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [method, setMethod] = useState<"claude" | "terminal">("claude");

  useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  const configPath = {
    mac: "~/Library/Application Support/Claude/claude_desktop_config.json",
    windows: "%APPDATA%\\Claude\\claude_desktop_config.json",
    linux: "~/.config/Claude/claude_desktop_config.json",
    unknown: "~/Library/Application Support/Claude/claude_desktop_config.json",
  }[platform];

  const quitInstructions = {
    mac: "Cmd+Q",
    windows: "Right-click the Claude icon in system tray → Quit",
    linux: "Cmd+Q or right-click tray → Quit",
    unknown: "Cmd+Q (Mac) or right-click tray → Quit (Windows)",
  }[platform];

  // Claude prompt - platform specific
  const claudePrompt =
    platform === "windows"
      ? `I want to set up AccountingQB, an MCP server that connects QuickBooks to Claude Desktop.

I'm on Windows. Please help me configure it:

1. Read my Claude Desktop config file at: %APPDATA%\\Claude\\claude_desktop_config.json
2. If it doesn't exist, create it with: {"mcpServers": {}}
3. Add this entry to mcpServers (preserve any existing servers):

"accountingqb": {
  "command": "python",
  "args": ["-m", "accountingqb"],
  "env": {
    "QB_LICENSE_KEY": "${licenseKey}"
  }
}

4. Write the file back as valid JSON (pretty-printed, 2-space indent)
5. Tell me to fully quit Claude Desktop by right-clicking the Claude icon in the system tray and clicking "Quit". Just closing the window is NOT enough.
6. After I restart Claude, remind me to click "Allow" when Claude asks about the accountingqb server.`
      : `I want to set up AccountingQB, an MCP server that connects QuickBooks to Claude Desktop.

I'm on ${platform === "mac" ? "macOS" : "Linux"}. Please help me configure it:

1. Read my Claude Desktop config file at: ${configPath}
2. If it doesn't exist, create it with: {"mcpServers": {}}
3. Add this entry to mcpServers (preserve any existing servers):

"accountingqb": {
  "command": "uvx",
  "args": ["accountingqb"],
  "env": {
    "QB_LICENSE_KEY": "${licenseKey}"
  }
}

4. Write the file back as valid JSON (pretty-printed, 2-space indent)
5. Tell me to fully quit Claude Desktop with ${quitInstructions}. Just closing the window is NOT enough.
6. After I restart Claude, remind me to click "Allow" when Claude asks about the accountingqb server.`;

  // Terminal commands - platform specific
  const terminalSteps =
    platform === "windows"
      ? {
          prereq: {
            title: "Install Python (if not installed)",
            command: "winget install Python.Python.3.12",
            note: "Or download from python.org",
          },
          install: {
            title: "Install AccountingQB",
            command: "pip install accountingqb",
          },
          config: {
            title: "Config file location",
            command: "%APPDATA%\\Claude\\claude_desktop_config.json",
            note: "Create this file if it doesn't exist",
          },
        }
      : {
          prereq: {
            title: "Install uv (if not installed)",
            command: "curl -LsSf https://astral.sh/uv/install.sh | sh",
            note: "Then restart your terminal",
          },
          install: null, // uvx handles this automatically
          config: {
            title: "Config file location",
            command: configPath,
            note: "Create this file if it doesn't exist",
          },
        };

  const configSnippet =
    platform === "windows"
      ? `{
  "mcpServers": {
    "accountingqb": {
      "command": "python",
      "args": ["-m", "accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "${licenseKey}"
      }
    }
  }
}`
      : `{
  "mcpServers": {
    "accountingqb": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "${licenseKey}"
      }
    }
  }
}`;

  const copy = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 3000);
  };

  const allComplete = hasClaudeConfigured && hasQBConnected;

  if (allComplete) {
    return (
      <div className="rounded-2xl border border-green-500/20 bg-green-500/5 p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20">
            <svg
              className="h-5 w-5 text-green-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-white">Setup Complete</h3>
            <p className="text-sm text-gray-400">
              You&apos;re all set! Open Claude Desktop and start asking
              questions about your books.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Set Up AccountingQB
          </h3>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-sm text-gray-400">Detected:</span>
            <div className="flex gap-1">
              {(["mac", "windows", "linux"] as Platform[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPlatform(p)}
                  className={`px-2 py-0.5 text-xs rounded transition ${
                    platform === p
                      ? "bg-cyan-500 text-white"
                      : "bg-white/10 text-gray-400 hover:bg-white/20"
                  }`}
                >
                  {p === "mac"
                    ? "macOS"
                    : p === "windows"
                      ? "Windows"
                      : "Linux"}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`flex items-center gap-1 ${hasClaudeConfigured ? "text-green-400" : "text-gray-500"}`}
          >
            {hasClaudeConfigured ? "✓" : "○"} Claude
          </span>
          <span
            className={`flex items-center gap-1 ${hasQBConnected ? "text-green-400" : "text-gray-500"}`}
          >
            {hasQBConnected ? "✓" : "○"} QuickBooks
          </span>
        </div>
      </div>

      {/* Method Toggle */}
      <div className="mt-4 flex rounded-lg bg-white/5 p-1">
        <button
          onClick={() => setMethod("claude")}
          className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
            method === "claude"
              ? "bg-cyan-500 text-white"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Use Claude (Recommended)
        </button>
        <button
          onClick={() => setMethod("terminal")}
          className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
            method === "terminal"
              ? "bg-cyan-500 text-white"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Use Terminal
        </button>
      </div>

      {/* Claude Method */}
      {method === "claude" && (
        <div className="mt-6 space-y-4">
          {platform === "windows" && (
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
              <p className="text-sm text-yellow-400 font-medium">
                Windows Prerequisite
              </p>
              <p className="mt-1 text-sm text-gray-400">
                First, install AccountingQB by opening PowerShell and running:
              </p>
              <div className="mt-2 flex items-center gap-2">
                <code className="flex-1 rounded bg-black/40 px-3 py-2 text-sm text-cyan-400 font-mono">
                  pip install accountingqb
                </code>
                <button
                  onClick={() => copy("pip install accountingqb", "pip")}
                  className="shrink-0 rounded border border-white/10 px-3 py-2 text-xs text-gray-400 hover:bg-white/5"
                >
                  {copied === "pip" ? "Copied!" : "Copy"}
                </button>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Don&apos;t have Python? Run{" "}
                <code className="text-cyan-400">
                  winget install Python.Python.3.12
                </code>{" "}
                first.
              </p>
            </div>
          )}

          <div className="rounded-xl bg-white/[0.03] p-4">
            <h4 className="text-sm font-medium text-white mb-3">
              {platform === "windows"
                ? "Then paste this in Claude Desktop:"
                : "Paste this prompt in Claude Desktop:"}
            </h4>
            <button
              onClick={() => copy(claudePrompt, "prompt")}
              className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:shadow-cyan-500/40"
            >
              {copied === "prompt" ? (
                <span className="flex items-center justify-center gap-2">
                  ✓ Copied! Now paste in Claude Desktop
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Copy Setup Prompt
                </span>
              )}
            </button>
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="mt-2 w-full text-center text-xs text-gray-500 hover:text-gray-400"
            >
              {showDetails ? "Hide prompt preview" : "Show prompt preview"}
            </button>
            {showDetails && (
              <pre className="mt-3 rounded-lg bg-black/40 p-3 text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto">
                {claudePrompt}
              </pre>
            )}
          </div>

          <div className="rounded-xl bg-white/[0.03] p-4">
            <h4 className="text-sm font-medium text-white mb-2">
              What happens next:
            </h4>
            <ol className="space-y-2 text-sm text-gray-400">
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">
                  1
                </span>
                <span>Claude edits your config file automatically</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">
                  2
                </span>
                <span>
                  Quit Claude Desktop completely:{" "}
                  <span className="text-white">{quitInstructions}</span>
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">
                  3
                </span>
                <span>Reopen Claude Desktop</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs text-cyan-400">
                  4
                </span>
                <span>
                  Click{" "}
                  <span className="text-green-400">&quot;Allow&quot;</span> when
                  Claude asks about AccountingQB
                </span>
              </li>
            </ol>
          </div>
        </div>
      )}

      {/* Terminal Method */}
      {method === "terminal" && (
        <div className="mt-6 space-y-4">
          {/* Step 1: Prerequisites */}
          <div className="rounded-xl bg-white/[0.03] p-4">
            <h4 className="text-sm font-medium text-white mb-2">
              Step 1: {terminalSteps.prereq.title}
            </h4>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded bg-black/40 px-3 py-2 text-sm text-cyan-400 font-mono overflow-x-auto">
                {terminalSteps.prereq.command}
              </code>
              <button
                onClick={() => copy(terminalSteps.prereq.command, "prereq")}
                className="shrink-0 rounded border border-white/10 px-3 py-2 text-xs text-gray-400 hover:bg-white/5"
              >
                {copied === "prereq" ? "Copied!" : "Copy"}
              </button>
            </div>
            {terminalSteps.prereq.note && (
              <p className="mt-2 text-xs text-gray-500">
                {terminalSteps.prereq.note}
              </p>
            )}
          </div>

          {/* Step 2: Install (Windows only) */}
          {terminalSteps.install && (
            <div className="rounded-xl bg-white/[0.03] p-4">
              <h4 className="text-sm font-medium text-white mb-2">
                Step 2: {terminalSteps.install.title}
              </h4>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded bg-black/40 px-3 py-2 text-sm text-cyan-400 font-mono">
                  {terminalSteps.install.command}
                </code>
                <button
                  onClick={() =>
                    copy(terminalSteps.install!.command, "install")
                  }
                  className="shrink-0 rounded border border-white/10 px-3 py-2 text-xs text-gray-400 hover:bg-white/5"
                >
                  {copied === "install" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Config */}
          <div className="rounded-xl bg-white/[0.03] p-4">
            <h4 className="text-sm font-medium text-white mb-2">
              Step {terminalSteps.install ? "3" : "2"}: Edit Config File
            </h4>
            <p className="text-sm text-gray-400 mb-2">
              Open this file (create it if it doesn&apos;t exist):
            </p>
            <div className="flex items-center gap-2 mb-3">
              <code className="flex-1 rounded bg-black/40 px-3 py-2 text-sm text-cyan-400 font-mono overflow-x-auto">
                {terminalSteps.config.command}
              </code>
              <button
                onClick={() => copy(terminalSteps.config.command, "path")}
                className="shrink-0 rounded border border-white/10 px-3 py-2 text-xs text-gray-400 hover:bg-white/5"
              >
                {copied === "path" ? "Copied!" : "Copy"}
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-2">Add this content:</p>
            <div className="relative">
              <pre className="rounded-lg bg-black/40 p-3 text-sm text-cyan-400 font-mono overflow-x-auto">
                {configSnippet}
              </pre>
              <button
                onClick={() => copy(configSnippet, "config")}
                className="absolute top-2 right-2 rounded border border-white/10 px-2 py-1 text-xs text-gray-400 hover:bg-white/10"
              >
                {copied === "config" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Step 4: Restart */}
          <div className="rounded-xl bg-white/[0.03] p-4">
            <h4 className="text-sm font-medium text-white mb-2">
              Step {terminalSteps.install ? "4" : "3"}: Restart Claude Desktop
            </h4>
            <ol className="space-y-1 text-sm text-gray-400">
              <li>
                1. Fully quit Claude Desktop:{" "}
                <span className="text-white">{quitInstructions}</span>
              </li>
              <li>2. Reopen Claude Desktop</li>
              <li>
                3. Click{" "}
                <span className="text-green-400">&quot;Allow&quot;</span> when
                asked about AccountingQB
              </li>
            </ol>
          </div>
        </div>
      )}

      {/* License Key */}
      <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">
              Your License Key
            </p>
            <code className="mt-1 block text-sm text-cyan-400 font-mono">
              {licenseKey}
            </code>
          </div>
          <button
            onClick={() => copy(licenseKey, "key")}
            className="rounded border border-white/10 px-3 py-2 text-sm text-gray-400 hover:bg-white/5"
          >
            {copied === "key" ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>

      {/* QuickBooks Connect */}
      {!hasQBConnected && (
        <div className="mt-4 text-center">
          <a
            href={`/api/oauth/start?license_key=${encodeURIComponent(licenseKey)}`}
            className="text-sm text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            Connect QuickBooks →
          </a>
        </div>
      )}
    </div>
  );
}
