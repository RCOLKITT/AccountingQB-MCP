import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * POST /api/user/read-only  { licenseKey, enabled }
 *
 * Toggle the license's read-only connector mode. When enabled, the remote MCP
 * connector refuses every book-mutating tool (server-enforced) and hides them from
 * tools/list — a hard read-only lock the client selects, beyond per-action approval.
 * License-key access model, consistent with the other /api/user/* routes.
 */
export async function POST(req: NextRequest) {
  let body: { licenseKey?: string; enabled?: boolean };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Body must be JSON" }, { status: 400 });
  }

  const { licenseKey, enabled } = body;
  if (!licenseKey) {
    return NextResponse.json(
      { error: "License key required" },
      { status: 400 },
    );
  }
  if (typeof enabled !== "boolean") {
    return NextResponse.json(
      { error: "`enabled` must be a boolean" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();
  const { data, error } = await supabase
    .from("licenses")
    .update({ read_only: enabled, updated_at: new Date().toISOString() })
    .eq("key", licenseKey)
    .select("key")
    .maybeSingle();

  if (error) {
    console.error("read-only toggle error:", error);
    return NextResponse.json({ error: "Failed to update" }, { status: 500 });
  }
  if (!data) {
    return NextResponse.json({ error: "License not found" }, { status: 404 });
  }

  return NextResponse.json({ ok: true, readOnly: enabled });
}
