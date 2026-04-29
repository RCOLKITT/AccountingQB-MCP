import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { auth } from "@clerk/nextjs/server";

/**
 * GET /api/artifacts/[id]
 * Get a single artifact by ID.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const supabase = getSupabase();

  const { data: artifact, error } = await supabase
    .from("artifacts")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !artifact) {
    return NextResponse.json({ error: "Artifact not found" }, { status: 404 });
  }

  return NextResponse.json({ artifact });
}

/**
 * PATCH /api/artifacts/[id]
 * Update an artifact (star/unstar, rename, update tags).
 */
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const body = await req.json();
  const { name, description, starred, tags } = body;

  const supabase = getSupabase();

  // Build update object with only provided fields
  const updates: Record<string, unknown> = {};
  if (name !== undefined) updates.name = name;
  if (description !== undefined) updates.description = description;
  if (starred !== undefined) updates.starred = starred;
  if (tags !== undefined) updates.tags = tags;

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "No updates provided" }, { status: 400 });
  }

  const { data: artifact, error } = await supabase
    .from("artifacts")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    console.error("Failed to update artifact:", error);
    return NextResponse.json({ error: "Failed to update artifact" }, { status: 500 });
  }

  return NextResponse.json({ artifact });
}

/**
 * DELETE /api/artifacts/[id]
 * Delete an artifact.
 */
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const supabase = getSupabase();

  const { error } = await supabase.from("artifacts").delete().eq("id", id);

  if (error) {
    console.error("Failed to delete artifact:", error);
    return NextResponse.json({ error: "Failed to delete artifact" }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
