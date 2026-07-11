import type { Metadata } from "next";

// The page itself is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: "Advanced Setup (Self-Hosted) — AccountingQB",
  description:
    "Set up AccountingQB with your own Intuit OAuth credentials, or use the one-click easy setup.",
  alternates: { canonical: "/setup" },
};

export default function SetupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
