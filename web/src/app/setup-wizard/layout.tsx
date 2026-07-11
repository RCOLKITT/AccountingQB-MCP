import type { Metadata } from "next";

// The page itself is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: "Connect AccountingQB to Claude — Setup Wizard",
  description:
    "Connect Claude to your QuickBooks in minutes: add the remote connector (no install) or install the desktop extension.",
  alternates: { canonical: "/setup-wizard" },
};

export default function SetupWizardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
