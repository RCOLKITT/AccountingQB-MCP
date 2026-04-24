import { NextResponse } from "next/server";
import { createServerComponentClient } from "@/lib/supabase-server";

/**
 * POST /api/auth/logout
 * Signs out the current user.
 */
export async function POST() {
  try {
    const supabase = await createServerComponentClient();
    await supabase.auth.signOut();

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Logout error:", err);
    return NextResponse.json(
      { error: "Failed to sign out" },
      { status: 500 }
    );
  }
}
