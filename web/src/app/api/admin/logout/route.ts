import { NextResponse } from "next/server";
import { clearAdminSession } from "@/lib/admin-auth";

/**
 * POST /api/admin/logout
 * Clear admin session and redirect to login.
 */
export async function POST() {
  await clearAdminSession();
  return NextResponse.redirect(new URL("/admin/login", process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"), 303);
}
