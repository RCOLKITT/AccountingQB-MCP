import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuickBooks Accounting for Claude | AI-Powered Bookkeeping",
  description:
    "Connect Claude to your QuickBooks Online. 91 tools for transactions, reports, tax prep, and smart bookkeeping automation. Your data stays local.",
  keywords: [
    "quickbooks",
    "claude",
    "mcp",
    "accounting",
    "bookkeeping",
    "ai",
    "tax prep",
    "schedule c",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">{children}</body>
    </html>
  );
}
