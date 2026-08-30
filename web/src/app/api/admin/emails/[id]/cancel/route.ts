import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { currentUser } from "@clerk/nextjs/server";

/**
 * POST /api/admin/emails/[id]/cancel
 * Cancel a scheduled email.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { id } = await params;
  const supabase = getSupabase();

  const { error } = await supabase
    .from("email_schedules")
    .update({ cancelled: true })
    .eq("id", id)
    .is("sent_at", null);

  if (error) {
    console.error("Failed to cancel email:", error);
    return NextResponse.json(
      { error: "Failed to cancel email" },
      { status: 500 },
    );
  }

  return NextResponse.json({ success: true });
}
