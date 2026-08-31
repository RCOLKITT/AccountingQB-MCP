import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";

/**
 * GET /api/oauth2/client-info?client_id=...
 * Public, read-only lookup used by the /oauth/authorize consent page to show
 * which app is requesting access. Never returns secrets.
 */
export async function GET(req: NextRequest) {
  const clientId = req.nextUrl.searchParams.get("client_id");
  if (!clientId) {
    return NextResponse.json(
      { error: "client_id is required" },
      { status: 400 },
    );
  }

  const supabase = getSupabase();
  const { data: client } = await supabase
    .from("mcp_oauth_clients")
    .select("client_id, client_name, redirect_uris")
    .eq("client_id", clientId)
    .maybeSingle();

  if (!client) {
    return NextResponse.json({ error: "Unknown client" }, { status: 404 });
  }

  return NextResponse.json({
    client_id: client.client_id,
    client_name: client.client_name,
    redirect_uris: client.redirect_uris,
  });
}
