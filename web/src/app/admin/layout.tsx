import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { SignOutButton } from "@clerk/nextjs";
import Link from "next/link";
import { resolveAdmin, type AdminClaims } from "@/lib/admin-auth";

// Private surface — keep it out of every index (belt-and-suspenders with robots).
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Role + email come from the SESSION TOKEN (no Clerk API call); resolveAdmin
  // falls back to one fetch only until the token is configured with the claims.
  // The middleware already gated this route — this is defense-in-depth + the email.
  const { userId, sessionClaims } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }
  const { role, email } = await resolveAdmin(userId, sessionClaims as AdminClaims, true);
  if (role !== "admin") {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-[#0a0e1a]">
      {/* Admin Header */}
      <header className="border-b border-white/10 bg-[#131a2e]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link href="/admin" className="flex items-center gap-2">
              <span className="text-xl font-bold">
                <span className="text-cyan-400">Accounting</span>
                <span className="text-blue-500">QB</span>
              </span>
              <span className="rounded bg-cyan-500/10 px-2 py-0.5 text-xs font-medium text-cyan-400">
                Admin
              </span>
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                href="/admin"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Dashboard
              </Link>
              <Link
                href="/admin/analytics"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Analytics
              </Link>
              <Link
                href="/admin/users"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Users
              </Link>
              <Link
                href="/admin/funnel"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Funnel
              </Link>
              <Link
                href="/admin/revenue"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Revenue
              </Link>
              <Link
                href="/admin/usage"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Usage
              </Link>
              <Link
                href="/admin/downloads"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Downloads
              </Link>
              <Link
                href="/admin/emails"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Emails
              </Link>
              <Link
                href="/admin/compose"
                className="text-sm text-gray-400 hover:text-white transition"
              >
                Compose
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{email}</span>
            <Link
              href="/"
              className="text-sm text-gray-400 hover:text-white transition"
            >
              Exit Admin
            </Link>
            <SignOutButton redirectUrl="/">
              <button className="text-sm text-gray-400 hover:text-white transition">
                Sign out
              </button>
            </SignOutButton>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}
