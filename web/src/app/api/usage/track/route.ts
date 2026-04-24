import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { getTimeSaved } from "@/lib/time-saved";
import {
  getUsageTrackLimiter,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

/**
 * POST /api/usage/track
 * Called by MCP server after each tool invocation.
 * Validated by license key (must exist in licenses table via FK constraint).
 * Rate limited per license key.
 *
 * Body: {
 *   licenseKey: string,
 *   toolName: string,
 *   realmId?: string
 * }
 */
export async function POST(req: NextRequest) {
  // Rate limit: 100 requests per minute per license key
  if (isRateLimitingEnabled()) {
    try {
      const body = await req.clone().json();
      const limitKey = body.licenseKey || "unknown";
      const { success, reset } = await getUsageTrackLimiter().limit(limitKey);
      if (!success) {
        return rateLimitResponse(reset);
      }
    } catch {
      // If we can't parse the body for rate limiting, continue anyway
    }
  }

  try {
    const { licenseKey, toolName, realmId } = await req.json();

    if (!licenseKey || !toolName) {
      return NextResponse.json(
        { error: "licenseKey and toolName are required" },
        { status: 400 }
      );
    }

    // Validate license key format
    if (typeof licenseKey !== "string" || !licenseKey.startsWith("LK-")) {
      return NextResponse.json(
        { error: "Invalid license key format" },
        { status: 400 }
      );
    }

    // Validate tool name
    if (typeof toolName !== "string" || toolName.length > 100) {
      return NextResponse.json(
        { error: "Invalid tool name" },
        { status: 400 }
      );
    }

    const timeSaved = getTimeSaved(toolName);
    const supabase = getSupabase();

    // Insert usage record
    const { error } = await supabase.from("tool_usage").insert({
      license_key: licenseKey,
      tool_name: toolName,
      realm_id: realmId || null,
      time_saved_minutes: timeSaved,
    });

    if (error) {
      // Log but don't fail - usage tracking is non-critical
      console.error("Failed to track usage:", error);
      // Check if it's a foreign key violation (license doesn't exist)
      if (error.code === "23503") {
        return NextResponse.json(
          { error: "License not found" },
          { status: 404 }
        );
      }
    }

    return NextResponse.json({
      tracked: true,
      timeSaved,
    });
  } catch (err) {
    console.error("Usage tracking error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
