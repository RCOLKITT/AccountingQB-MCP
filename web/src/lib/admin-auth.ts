import { getSupabase } from "@/lib/supabase";
import { cookies } from "next/headers";

const ADMIN_COOKIE_NAME = "admin_session";
const ADMIN_SESSION_DURATION = 24 * 60 * 60 * 1000; // 24 hours

interface AdminUser {
  id: string;
  email: string;
  role: "admin" | "super_admin";
}

/**
 * Check if the current request is from an authenticated admin
 * Uses a simple email-based session stored in a cookie
 */
export async function getAdminSession(): Promise<AdminUser | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(ADMIN_COOKIE_NAME);

  if (!sessionCookie?.value) {
    return null;
  }

  try {
    const session = JSON.parse(
      Buffer.from(sessionCookie.value, "base64").toString("utf8")
    );

    // Verify session hasn't expired
    if (session.expiresAt < Date.now()) {
      return null;
    }

    // Verify admin still exists in database
    const supabase = getSupabase();
    const { data: admin } = await supabase
      .from("admin_users")
      .select("id, email, role")
      .eq("email", session.email)
      .single();

    if (!admin) {
      return null;
    }

    return admin as AdminUser;
  } catch {
    return null;
  }
}

/**
 * Create an admin session for the given email
 * Only works if the email exists in admin_users table
 */
export async function createAdminSession(
  email: string
): Promise<{ success: boolean; error?: string }> {
  const supabase = getSupabase();

  // Verify admin exists
  const { data: admin, error } = await supabase
    .from("admin_users")
    .select("id, email, role")
    .eq("email", email.toLowerCase())
    .single();

  if (error || !admin) {
    return { success: false, error: "Not an admin user" };
  }

  // Create session cookie
  const session = {
    email: admin.email,
    role: admin.role,
    expiresAt: Date.now() + ADMIN_SESSION_DURATION,
  };

  const cookieStore = await cookies();
  cookieStore.set(ADMIN_COOKIE_NAME, Buffer.from(JSON.stringify(session)).toString("base64"), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: ADMIN_SESSION_DURATION / 1000,
    path: "/",
  });

  return { success: true };
}

/**
 * Clear the admin session
 */
export async function clearAdminSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(ADMIN_COOKIE_NAME);
}

/**
 * Check if an email is an admin (for magic link login)
 */
export async function isAdminEmail(email: string): Promise<boolean> {
  const supabase = getSupabase();
  const { data } = await supabase
    .from("admin_users")
    .select("id")
    .eq("email", email.toLowerCase())
    .single();

  return !!data;
}

/**
 * Require admin auth - throws redirect if not authenticated
 */
export async function requireAdmin(): Promise<AdminUser> {
  const admin = await getAdminSession();
  if (!admin) {
    throw new Error("UNAUTHORIZED");
  }
  return admin;
}
