export default function SuccessPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white flex items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 text-5xl">
          ✓
        </div>
        <h1 className="mt-8 text-3xl font-bold tracking-tight sm:text-4xl">
          Welcome aboard!
        </h1>
        <p className="mt-4 text-lg text-gray-300">
          Your 14-day free trial is active. Check your email for your license
          key and setup instructions.
        </p>

        <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-8 text-left">
          <h2 className="text-lg font-semibold">Next steps</h2>
          <ol className="mt-4 space-y-4 text-gray-300">
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                1
              </span>
              <span>
                Check your email for the license key (starts with{" "}
                <code className="rounded bg-white/10 px-1.5 py-0.5 text-sm">
                  LK-
                </code>
                )
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                2
              </span>
              <span>
                Install the extension in Claude Desktop (one-click from the
                extension directory)
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                3
              </span>
              <span>
                Connect your QuickBooks account through the OAuth setup flow
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold">
                4
              </span>
              <span>
                Start talking to your books — try{" "}
                <em>&ldquo;Show me my P&amp;L for last quarter&rdquo;</em>
              </span>
            </li>
          </ol>
        </div>

        <div className="mt-8 flex items-center justify-center gap-4">
          <a
            href="/"
            className="rounded-lg border border-white/20 px-6 py-3 text-sm font-semibold transition hover:bg-white/10"
          >
            Back to Home
          </a>
          <a
            href="mailto:ryan@vasperacapital.com"
            className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
          >
            Need Help?
          </a>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          Your trial includes full access to all 91 QuickBooks tools.
          <br />
          No credit card was charged. Cancel anytime.
        </p>
      </div>
    </main>
  );
}
