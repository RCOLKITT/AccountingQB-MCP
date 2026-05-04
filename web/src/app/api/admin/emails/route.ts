import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { currentUser } from "@clerk/nextjs/server";

/**
 * GET /api/admin/emails
 * Get scheduled emails or escalations.
 */
export async function GET(req: NextRequest) {
  // Verify admin via Clerk
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const role = (user.publicMetadata as { role?: string })?.role;
  if (role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { searchParams } = req.nextUrl;
  const type = searchParams.get("type") || "scheduled";

  const supabase = getSupabase();

  if (type === "escalations") {
    // Get escalated support conversations
    const { data: conversations, error } = await supabase
      .from("support_conversations")
      .select("id, license_key, user_email, status, created_at, updated_at")
      .order("updated_at", { ascending: false })
      .limit(100);

    if (error) {
      console.error("Failed to fetch escalations:", error);
      return NextResponse.json(
        { error: "Failed to fetch escalations" },
        { status: 500 }
      );
    }

    // Get message counts for each conversation
    const escalations = await Promise.all(
      (conversations || []).map(async (conv) => {
        const { count } = await supabase
          .from("support_messages")
          .select("*", { count: "exact", head: true })
          .eq("conversation_id", conv.id);

        return {
          ...conv,
          message_count: count || 0,
        };
      })
    );

    return NextResponse.json({ escalations });
  }

  // Get email schedules
  const query = supabase
    .from("email_schedules")
    .select("id, license_key, email_type, scheduled_for, sent_at, cancelled, metadata, created_at")
    .order("scheduled_for", { ascending: false })
    .limit(100);

  if (type === "sent") {
    query.not("sent_at", "is", null);
  } else {
    // scheduled (pending)
    query.is("sent_at", null).eq("cancelled", false);
  }

  const { data: emails, error } = await query;

  if (error) {
    console.error("Failed to fetch emails:", error);
    return NextResponse.json(
      { error: "Failed to fetch emails" },
      { status: 500 }
    );
  }

  return NextResponse.json({ emails: emails || [] });
}
