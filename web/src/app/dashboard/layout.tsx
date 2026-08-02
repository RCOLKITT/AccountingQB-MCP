import type { Metadata } from "next";

// The dashboard is a private, key/auth-gated surface — keep it out of every
// index (the page itself is a client component, so noindex lives here on a
// server layout). robots.ts also Disallows /dashboard.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
