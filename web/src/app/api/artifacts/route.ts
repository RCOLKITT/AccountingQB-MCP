import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { auth } from "@clerk/nextjs/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/artifacts
 * List artifacts for the authenticated user's license.
 */
export async function GET(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const licenseKey = searchParams.get("licenseKey");
  const realmId = searchParams.get("realmId");
  const type = searchParams.get("type");
  const starred = searchParams.get("starred");

  if (!licenseKey) {
    return NextResponse.json({ error: "License key required" }, { status: 400 });
  }

  const supabase = getSupabase();

  let query = supabase
    .from("artifacts")
    .select("*")
    .eq("license_key", licenseKey)
    .order("created_at", { ascending: false });

  if (realmId) {
    query = query.eq("realm_id", realmId);
  }

  if (type) {
    query = query.eq("type", type);
  }

  if (starred === "true") {
    query = query.eq("starred", true);
  }

  const { data: artifacts, error } = await query.limit(100);

  if (error) {
    console.error("Failed to fetch artifacts:", error);
    return NextResponse.json({ error: "Failed to fetch artifacts" }, { status: 500 });
  }

  return NextResponse.json({ artifacts: artifacts || [] });
}

/**
 * POST /api/artifacts
 * Create a new artifact (called by MCP server or dashboard).
 */
export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { licenseKey, realmId, type, name, description, data, format, tags } = body;

  if (!licenseKey || !type || !name || !data) {
    return NextResponse.json(
      { error: "Missing required fields: licenseKey, type, name, data" },
      { status: 400 }
    );
  }

  const validTypes = ["report", "analysis", "reconciliation", "export"];
  if (!validTypes.includes(type)) {
    return NextResponse.json(
      { error: `Invalid type. Must be one of: ${validTypes.join(", ")}` },
      { status: 400 }
    );
  }

  const supabase = getSupabase();

  const { data: artifact, error } = await supabase
    .from("artifacts")
    .insert({
      license_key: licenseKey,
      realm_id: realmId || null,
      type,
      name,
      description: description || null,
      data,
      format: format || "table",
      tags: tags || [],
      created_by: "claude",
    })
    .select()
    .single();

  if (error) {
    console.error("Failed to create artifact:", error);
    return NextResponse.json({ error: "Failed to create artifact" }, { status: 500 });
  }

  return NextResponse.json({ artifact }, { status: 201 });
}
