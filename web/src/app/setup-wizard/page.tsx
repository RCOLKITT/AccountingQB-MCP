"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

type Platform = "mac" | "windows" | "linux" | "unknown";
type Step = "detect" | "install-claude" | "install-extension" | "connect-qb" | "done";

function detectPlatform(): Platform {
  if (typeof window === "undefined") return "unknown";
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("mac")) return "mac";
  if (ua.includes("win")) return "windows";
  if (ua.includes("linux")) return "linux";
  return "unknown";
}

const CONFIG_PATHS: Record<Platform, string> = {
  mac: "~/Library/Application Support/Claude/claude_desktop_config.json",
  windows: "%APPDATA%\\Claude\\claude_desktop_config.json",
  linux: "~/.config/Claude/claude_desktop_config.json",
  unknown: "~/Library/Application Support/Claude/claude_desktop_config.json",
};

function SetupWizardContent() {
  const searchParams = useSearchParams();
  const licenseKey = searchParams.get("key") || "";
  const [platform, setPlatform] = useState<Platform>("unknown");
  const [step, setStep] = useState<Step>("detect");
  const [copied, setCopied] = useState(false);
  const [hasClaudeDesktop, setHasClaudeDesktop] = useState<boolean | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [inputKey, setInputKey] = useState(licenseKey);
  const [oauthTimeout, setOauthTimeout] = useState(false);
  const [showTroubleshooting, setShowTroubleshooting] = useState(false);

  useEffect(() => {
    setPlatform(detectPlatform());
    // Check if they came with a license key
    if (licenseKey) {
      setStep("install-claude");
    }
  }, [licenseKey]);

  const effectiveKey = inputKey || licenseKey || "YOUR_LICENSE_KEY";

  const configSnippet = `{
  "mcpServers": {
    "accountingqb": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "${effectiveKey}"
      }
    }
  }
}`;

  const copyConfig = () => {
    navigator.clipboard.writeText(configSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleConnectQB = () => {
    if (!effectiveKey || effectiveKey === "YOUR_LICENSE_KEY") {
      alert("Please enter your license key first");
      return;
    }
    setConnecting(true);
    // Open OAuth in new window
    window.open(
      `/api/oauth/start?license_key=${encodeURIComponent(effectiveKey)}`,
      "qb-oauth",
      "width=600,height=700"
    );
    // Listen for OAuth completion
    const checkInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/oauth/status?license_key=${encodeURIComponent(effectiveKey)}`);
        const data = await res.json();
        if (data.connected) {
          clearInterval(checkInterval);
          setConnecting(false);
          setConnected(true);
          setStep("done");
        }
      } catch {
        // ignore
      }
    }, 2000);
    // Show timeout message after 2 minutes
    setTimeout(() => {
      if (!connected) {
        setOauthTimeout(true);
      }
    }, 120000);
    // Stop checking after 5 minutes
    setTimeout(() => {
      clearInterval(checkInterval);
      setConnecting(false);
    }, 300000);
  };

  const resetOAuth = () => {
    setConnecting(false);
    setOauthTimeout(false);
  };

  return (
    <main className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Nav */}
      <nav className="border-b border-white/5 px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <a href="/" className="text-xl font-bold">
            <span className="text-white">Accounting</span>
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">QB</span>
          </a>
          <a href="mailto:support@vasperacapital.com" className="text-sm text-gray-400 hover:text-white transition">
            Need help?
          </a>
        </div>
      </nav>

      <div className="mx-auto max-w-2xl px-6 py-12">
        {/* Progress */}
        <div className="flex items-center justify-center gap-3 mb-10">
          {["Install Claude", "Add Extension", "Connect QB", "Done"].map((label, i) => {
            const stepIndex = i + 1;
            const currentIndex = step === "detect" ? 0
              : step === "install-claude" ? 1
              : step === "install-extension" ? 2
              : step === "connect-qb" ? 3
              : 4;
            const isActive = stepIndex === currentIndex;
            const isDone = stepIndex < currentIndex;
            return (
              <div key={label} className="flex items-center gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all ${
                  isDone ? "bg-green-500 text-white"
                  : isActive ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg"
                  : "border border-white/20 text-gray-500"
                }`}>
                  {isDone ? "✓" : stepIndex}
                </div>
                {i < 3 && <div className={`w-8 h-px ${isDone ? "bg-green-500" : "bg-white/10"}`} />}
              </div>
            );
          })}
        </div>

        {/* License Key Input (if not provided) */}
        {!licenseKey && step !== "done" && (
          <div className="mb-8 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Enter your license key
            </label>
            <input
              type="text"
              value={inputKey}
              onChange={(e) => setInputKey(e.target.value)}
              placeholder="LK-XXXXXXXX..."
              className="w-full rounded-lg bg-black/40 border border-white/10 px-4 py-3 font-mono text-cyan-400 placeholder-gray-600 focus:border-cyan-400/50 focus:outline-none"
            />
            <p className="mt-2 text-xs text-gray-500">
              Check your email or <a href="/dashboard" className="text-cyan-400 hover:underline">dashboard</a> for your license key
            </p>
          </div>
        )}

        {/* Step 1: Install Claude Desktop */}
        {step === "install-claude" && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-2xl font-bold">Step 1: Install Claude Desktop</h2>
              <p className="mt-3 text-gray-400">
                AccountingQB runs as an extension inside Claude Desktop. If you haven&apos;t installed it yet, download it first.
              </p>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <a
                  href="https://claude.ai/download"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-4 hover:bg-white/10 transition"
                >
                  <span className="text-2xl">🍎</span>
                  <div>
                    <div className="font-semibold">macOS</div>
                    <div className="text-sm text-gray-500">Intel & Apple Silicon</div>
                  </div>
                </a>
                <a
                  href="https://claude.ai/download"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-4 hover:bg-white/10 transition"
                >
                  <span className="text-2xl">🪟</span>
                  <div>
                    <div className="font-semibold">Windows</div>
                    <div className="text-sm text-gray-500">Windows 10/11</div>
                  </div>
                </a>
              </div>

              <div className="mt-6 rounded-xl border border-blue-400/20 bg-blue-400/5 p-4">
                <p className="text-sm text-gray-300">
                  <strong className="text-blue-400">Already have Claude Desktop?</strong> Great! Skip to the next step.
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setHasClaudeDesktop(true)}
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition"
              >
                I have Claude Desktop → Next
              </button>
            </div>
            {hasClaudeDesktop && setStep("install-extension")}
          </div>
        )}

        {/* Step 2: Install Extension */}
        {step === "install-extension" && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-2xl font-bold">Step 2: Add AccountingQB Extension</h2>
              <p className="mt-3 text-gray-400">
                Add this configuration to your Claude Desktop config file.
              </p>

              {/* Config file location */}
              <div className="mt-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm text-gray-400">Config file location</span>
                  <div className="flex gap-1">
                    {(["mac", "windows", "linux"] as Platform[]).map((p) => (
                      <button
                        key={p}
                        onClick={() => setPlatform(p)}
                        className={`px-2 py-1 text-xs rounded ${
                          platform === p ? "bg-cyan-500 text-white" : "bg-white/10 text-gray-400 hover:bg-white/20"
                        }`}
                      >
                        {p === "mac" ? "macOS" : p === "windows" ? "Windows" : "Linux"}
                      </button>
                    ))}
                  </div>
                </div>
                <code className="block rounded-lg bg-black/40 px-4 py-3 text-sm text-cyan-400 overflow-x-auto">
                  {CONFIG_PATHS[platform]}
                </code>
              </div>

              {/* Config snippet */}
              <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-gray-400">Add this to your config</span>
                  <button
                    onClick={copyConfig}
                    className="px-3 py-1 text-xs rounded border border-white/10 hover:bg-white/10 transition"
                  >
                    {copied ? "✓ Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="rounded-xl bg-black/60 p-5 text-sm text-cyan-400 overflow-x-auto border border-white/5">
                  <code>{configSnippet}</code>
                </pre>
              </div>

              {/* Instructions */}
              <div className="mt-6 space-y-3 text-sm text-gray-300">
                <p><strong className="text-white">Instructions:</strong></p>
                <ol className="list-decimal list-inside space-y-2 text-gray-400">
                  <li>Open the config file in a text editor</li>
                  <li>If the file is empty, paste the entire config above</li>
                  <li>If you have existing servers, add the <code className="text-cyan-400">&quot;accountingqb&quot;</code> entry inside <code className="text-cyan-400">&quot;mcpServers&quot;</code></li>
                  <li>Save the file and restart Claude Desktop</li>
                </ol>
              </div>

              {/* One-time dependency */}
              <div className="mt-6 rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-4">
                <p className="text-sm text-gray-300">
                  <strong className="text-yellow-400">First time?</strong> You&apos;ll need <a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer" className="text-cyan-400 underline">uv</a> installed. Run:
                </p>
                <code className="mt-2 block rounded bg-black/40 px-3 py-2 text-sm text-cyan-400">
                  {platform === "windows" ? "winget install astral-sh.uv" : "curl -LsSf https://astral.sh/uv/install.sh | sh"}
                </code>
              </div>

              {/* Common Issues */}
              <details className="mt-6 rounded-xl border border-white/10 bg-white/[0.02]">
                <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-gray-300 hover:text-white">
                  Having trouble? Common issues & fixes
                </summary>
                <div className="px-5 pb-5 space-y-4 text-sm">
                  <div>
                    <p className="font-medium text-white">Config file doesn&apos;t exist</p>
                    <p className="text-gray-400">Create it! Just paste the config above into a new file at the path shown.</p>
                  </div>
                  <div>
                    <p className="font-medium text-white">Claude doesn&apos;t show AccountingQB tools</p>
                    <p className="text-gray-400">Make sure you saved the config and completely restarted Claude Desktop (not just closed the window).</p>
                  </div>
                  <div>
                    <p className="font-medium text-white">&quot;uvx not found&quot; error</p>
                    <p className="text-gray-400">Install uv using the command above, then restart your terminal and Claude Desktop.</p>
                  </div>
                  <div>
                    <p className="font-medium text-white">JSON syntax error</p>
                    <p className="text-gray-400">Make sure you have proper commas between entries. Use a JSON validator like <a href="https://jsonlint.com" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">jsonlint.com</a>.</p>
                  </div>
                </div>
              </details>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setStep("install-claude")}
                className="rounded-xl border border-white/10 px-6 py-4 font-medium hover:bg-white/10 transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setStep("connect-qb")}
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition"
              >
                I&apos;ve added the config → Next
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Connect QuickBooks */}
        {step === "connect-qb" && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
              <h2 className="text-2xl font-bold">Step 3: Connect QuickBooks</h2>
              <p className="mt-3 text-gray-400">
                Authorize AccountingQB to access your QuickBooks Online company. You can connect multiple companies.
              </p>

              <div className="mt-6 rounded-xl border border-green-400/20 bg-green-400/5 p-5">
                <div className="flex items-start gap-3">
                  <span className="text-green-400 text-lg">🔒</span>
                  <div className="text-sm text-gray-300">
                    <p className="font-medium text-green-400">Your data stays secure</p>
                    <p className="mt-1">OAuth tokens are stored securely. Your financial data flows directly between Claude and QuickBooks — never through our servers.</p>
                  </div>
                </div>
              </div>

              {connected ? (
                <div className="mt-6 rounded-xl bg-green-500/10 border border-green-500/20 p-6 text-center">
                  <div className="text-4xl mb-2">✓</div>
                  <p className="text-green-400 font-semibold">QuickBooks Connected!</p>
                </div>
              ) : oauthTimeout ? (
                <div className="mt-6 space-y-4">
                  <div className="rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-5">
                    <p className="font-medium text-yellow-400">Taking longer than expected?</p>
                    <p className="mt-2 text-sm text-gray-300">
                      If the OAuth window closed without completing, try again or check if a popup blocker is active.
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={resetOAuth}
                      className="flex-1 rounded-xl bg-gradient-to-r from-green-500 to-emerald-600 px-6 py-3 font-semibold"
                    >
                      Try Again
                    </button>
                    <button
                      onClick={() => setShowTroubleshooting(true)}
                      className="rounded-xl border border-white/10 px-6 py-3 font-medium hover:bg-white/10 transition"
                    >
                      Help
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={handleConnectQB}
                  disabled={connecting}
                  className="mt-6 w-full rounded-xl bg-gradient-to-r from-green-500 to-emerald-600 px-6 py-4 text-lg font-semibold shadow-lg shadow-green-500/20 hover:shadow-green-500/40 transition disabled:opacity-50"
                >
                  {connecting ? "Waiting for authorization..." : "Connect QuickBooks"}
                </button>
              )}

              {/* Troubleshooting */}
              {showTroubleshooting && (
                <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-white">Troubleshooting</h3>
                    <button
                      onClick={() => setShowTroubleshooting(false)}
                      className="text-gray-500 hover:text-white"
                    >
                      ✕
                    </button>
                  </div>
                  <ul className="space-y-3 text-sm text-gray-300">
                    <li className="flex gap-2">
                      <span className="text-cyan-400">•</span>
                      <span>Make sure popup blockers are disabled for this site</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-cyan-400">•</span>
                      <span>Try opening in an incognito/private window</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-cyan-400">•</span>
                      <span>Check that you&apos;re using the correct QuickBooks account</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-cyan-400">•</span>
                      <span>Ensure your QuickBooks company allows third-party apps</span>
                    </li>
                  </ul>
                  <div className="mt-4 pt-4 border-t border-white/10">
                    <p className="text-sm text-gray-400">
                      Still stuck? Email{" "}
                      <a href="mailto:support@vasperacapital.com" className="text-cyan-400 hover:underline">
                        support@vasperacapital.com
                      </a>{" "}
                      with your license key and we&apos;ll help within 24 hours.
                    </p>
                  </div>
                </div>
              )}

              <p className="mt-4 text-center text-sm text-gray-500">
                You can also connect later from Claude Desktop by asking Claude to connect.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setStep("install-extension")}
                className="rounded-xl border border-white/10 px-6 py-4 font-medium hover:bg-white/10 transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setStep("done")}
                className="flex-1 rounded-xl border border-white/10 px-6 py-4 font-medium hover:bg-white/10 transition"
              >
                Skip for now →
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Done */}
        {step === "done" && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-green-400/20 bg-green-400/5 p-8 text-center">
              <div className="text-5xl mb-4">🎉</div>
              <h2 className="text-2xl font-bold">You&apos;re All Set!</h2>
              <p className="mt-3 text-gray-400">
                Open Claude Desktop and start talking to your books.
              </p>

              <div className="mt-8 rounded-xl bg-white/[0.03] p-6">
                <p className="text-sm text-gray-400 mb-3">Try asking Claude:</p>
                <p className="text-xl italic text-cyan-400">
                  &quot;Show me my P&amp;L for last quarter&quot;
                </p>
              </div>

              <div className="mt-8 grid grid-cols-3 gap-4 text-center">
                <div className="rounded-lg bg-white/[0.04] p-4">
                  <div className="text-2xl font-bold text-cyan-400">91</div>
                  <div className="text-xs text-gray-500">QuickBooks tools</div>
                </div>
                <div className="rounded-lg bg-white/[0.04] p-4">
                  <div className="text-2xl font-bold text-blue-400">9</div>
                  <div className="text-xs text-gray-500">Tax prep tools</div>
                </div>
                <div className="rounded-lg bg-white/[0.04] p-4">
                  <div className="text-2xl font-bold text-green-400">∞</div>
                  <div className="text-xs text-gray-500">Hours saved</div>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <a
                href="/dashboard"
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-4 text-center font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition"
              >
                Go to Dashboard
              </a>
              <a
                href="/"
                className="rounded-xl border border-white/10 px-6 py-4 font-medium hover:bg-white/10 transition"
              >
                Home
              </a>
            </div>

            {!connected && (
              <p className="text-center text-sm text-gray-500">
                Don&apos;t forget to <button onClick={() => setStep("connect-qb")} className="text-cyan-400 hover:underline">connect QuickBooks</button> when you&apos;re ready.
              </p>
            )}
          </div>
        )}

        {/* Help footer */}
        <div className="mt-12 border-t border-white/5 pt-8 text-center text-sm text-gray-500">
          <p>
            Stuck? Email <a href="mailto:support@vasperacapital.com" className="text-cyan-400 hover:underline">support@vasperacapital.com</a> and we&apos;ll help you get connected.
          </p>
        </div>
      </div>
    </main>
  );
}

export default function SetupWizardPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#0a0e1a] text-white flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </main>
    }>
      <SetupWizardContent />
    </Suspense>
  );
}
