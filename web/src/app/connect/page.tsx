import type { Metadata } from "next";
import Link from "next/link";
import LandingNav from "@/components/nav/LandingNav";
import Footer from "@/components/Footer";
import ConnectorInstructions from "@/components/ConnectorInstructions";
import DownloadTrial from "@/components/DownloadTrial";

export const metadata: Metadata = {
  title: "How to use AccountingQB — pick what fits you",
  description:
    "Four ways to use AccountingQB with your QuickBooks: inside Claude via the hosted connector, the standalone desktop app, the Claude Desktop extension, or the Cowork plugin. Same 138 tools, same free trial — pick whichever fits how you work.",
};

function Card({
  tag,
  title,
  bestFor,
  children,
}: {
  tag: string;
  title: string;
  bestFor: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 p-8">
      <span className="text-xs font-semibold uppercase tracking-wide text-cyan-400">
        {tag}
      </span>
      <h2 className="mt-2 text-2xl font-bold text-white">{title}</h2>
      <p className="mt-2 text-gray-400">
        <span className="font-medium text-gray-300">Best for you if:</span>{" "}
        {bestFor}
      </p>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function Steps({ items }: { items: React.ReactNode[] }) {
  return (
    <ol className="list-inside list-decimal space-y-2 text-sm text-gray-400">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ol>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-5 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs text-gray-400">
      {children}
    </p>
  );
}

export default function ConnectPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a] text-gray-100">
      <LandingNav />

      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold text-white sm:text-4xl">
          How to use AccountingQB
        </h1>
        <p className="mt-4 text-lg text-gray-400">
          There are four ways to use AccountingQB with your QuickBooks — they
          all run the same 138 tools and the same free 14-day trial (no credit
          card). Pick whichever fits how you like to work.
        </p>
        <p className="mt-2 text-sm text-gray-500">
          New here?{" "}
          <Link href="/pricing" className="text-cyan-400 hover:underline">
            Start your free trial
          </Link>{" "}
          first — every option signs in to the same account.
        </p>

        <div className="mt-10 space-y-6">
          {/* Option: hosted connector */}
          <Card
            tag="Inside Claude"
            title="Add it as a connector in Claude"
            bestFor="you already use Claude (web, desktop, or mobile) and want nothing to install."
          >
            <ConnectorInstructions />
            <Note>
              Nothing to download and no API key — you use AccountingQB with
              your existing Claude subscription. Your books pass through our
              zero-retention connector and are never stored.
            </Note>
          </Card>

          {/* Option: standalone desktop app */}
          <Card
            tag="Standalone app"
            title="Download the desktop app (macOS / Windows)"
            bestFor="you want a dedicated local app that runs entirely on your own machine."
          >
            <Steps
              items={[
                "Download and install the app for your platform (buttons below).",
                "Open the app and activate — enter the license key we email you, or start a free trial right in the app.",
                "Connect your QuickBooks company when prompted.",
                "Add your own Anthropic API key in the app to chat with your books.",
              ]}
            />
            <div className="mt-6">
              <DownloadTrial enabled />
            </div>
            <Note>
              Fully local — your books never leave your machine. The desktop app
              uses{" "}
              <span className="text-gray-300">your own Anthropic API key</span>{" "}
              for chat (you add it once in the app); the other options use your
              Claude subscription instead.
            </Note>
          </Card>

          {/* Option: Claude Desktop extension */}
          <Card
            tag="Claude Desktop"
            title="Install the Claude Desktop extension (.mcpb)"
            bestFor="you use Claude Desktop and want a one-file local install."
          >
            <Steps
              items={[
                <>
                  Install{" "}
                  <a
                    href="https://claude.ai/download"
                    className="text-cyan-400 hover:underline"
                  >
                    Claude Desktop
                  </a>{" "}
                  if you don&apos;t have it.
                </>,
                "Add the AccountingQB extension and enter your license key.",
                "Connect your QuickBooks company when prompted.",
                <>
                  Full step-by-step with the config details:{" "}
                  <Link
                    href="/setup-wizard"
                    className="text-cyan-400 hover:underline"
                  >
                    open the setup guide
                  </Link>
                  .
                </>,
              ]}
            />
            <Note>
              Runs locally through Claude Desktop — your books never touch our
              servers.
            </Note>
          </Card>

          {/* Option: Cowork plugin */}
          <Card
            tag="Cowork"
            title="Add the Cowork plugin"
            bestFor="you work in Cowork and want AccountingQB available there."
          >
            <Steps
              items={[
                <>
                  Download the plugin:{" "}
                  <a
                    href="/downloads/accountingqb.plugin"
                    download
                    className="text-cyan-400 hover:underline"
                  >
                    accountingqb.plugin
                  </a>
                  .
                </>,
                "In Cowork, add the plugin from the downloaded file.",
                "Sign in with your AccountingQB account and approve access for your license.",
              ]}
            />
            <Note>
              The Cowork plugin connects through the same hosted connector — no
              separate setup.
            </Note>
          </Card>
        </div>

        <p className="mt-10 text-center text-sm text-gray-500">
          Stuck on any of these? Email{" "}
          <a
            href="mailto:support@vasperacapital.com"
            className="text-cyan-400 hover:underline"
          >
            support@vasperacapital.com
          </a>{" "}
          and we&apos;ll walk you through it.
        </p>
      </div>

      <Footer />
    </main>
  );
}
