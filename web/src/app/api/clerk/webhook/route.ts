import { NextRequest, NextResponse } from "next/server";
import { Webhook } from "svix";
import { getSupabase } from "@/lib/supabase";

type ClerkWebhookEvent = {
  type: string;
  data: {
    id: string;
    email_addresses?: Array<{ email_address: string; id: string }>;
    primary_email_address_id?: string;
    first_name?: string;
    last_name?: string;
  };
};

/**
 * POST /api/clerk/webhook
 * Handles Clerk webhook events to sync users with Supabase.
 *
 * On user.created:
 * 1. Creates user_profiles row with clerk_id
 * 2. Auto-links to any existing license with matching email
 */
export async function POST(req: NextRequest) {
  const body = await req.text();
  const svixId = req.headers.get("svix-id");
  const svixTimestamp = req.headers.get("svix-timestamp");
  const svixSignature = req.headers.get("svix-signature");

  if (!svixId || !svixTimestamp || !svixSignature) {
    return NextResponse.json({ error: "Missing svix headers" }, { status: 400 });
  }

  const webhookSecret = process.env.CLERK_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error("CLERK_WEBHOOK_SECRET not configured");
    return NextResponse.json({ error: "Webhook not configured" }, { status: 500 });
  }

  let event: ClerkWebhookEvent;
  try {
    const wh = new Webhook(webhookSecret);
    event = wh.verify(body, {
      "svix-id": svixId,
      "svix-timestamp": svixTimestamp,
      "svix-signature": svixSignature,
    }) as ClerkWebhookEvent;
  } catch (err) {
    console.error("Clerk webhook verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const supabase = getSupabase();

  if (event.type === "user.created") {
    const { id: clerkId, email_addresses, primary_email_address_id, first_name, last_name } = event.data;

    // Get primary email
    const primaryEmail = email_addresses?.find(e => e.id === primary_email_address_id);
    const email = primaryEmail?.email_address || email_addresses?.[0]?.email_address;

    if (!email) {
      console.error("No email found for Clerk user:", clerkId);
      return NextResponse.json({ error: "No email" }, { status: 400 });
    }

    const displayName = [first_name, last_name].filter(Boolean).join(" ") || null;

    // Check if profile already exists (idempotent)
    const { data: existing } = await supabase
      .from("user_profiles")
      .select("id")
      .eq("clerk_id", clerkId)
      .maybeSingle();

    if (!existing) {
      // Create user profile
      const { error: insertError } = await supabase
        .from("user_profiles")
        .insert({
          clerk_id: clerkId,
          email,
          display_name: displayName,
        });

      if (insertError) {
        console.error("Failed to create user profile:", insertError);
        return NextResponse.json({ error: "Database error" }, { status: 500 });
      }

      console.log(`Created user profile for ${email} (clerk_id: ${clerkId})`);

      // Check if there's an existing license with this email and auto-link
      const { data: license } = await supabase
        .from("licenses")
        .select("key")
        .eq("email", email)
        .maybeSingle();

      if (license) {
        // Get the newly created profile ID
        const { data: profile } = await supabase
          .from("user_profiles")
          .select("id")
          .eq("clerk_id", clerkId)
          .single();

        if (profile) {
          await supabase
            .from("user_licenses")
            .upsert({
              user_id: profile.id,
              license_key: license.key,
              role: "owner",
            }, { onConflict: "user_id,license_key" });

          console.log(`Auto-linked user ${email} to license ${license.key}`);
        }
      }
    }
  }

  if (event.type === "user.updated") {
    const { id: clerkId, email_addresses, primary_email_address_id, first_name, last_name } = event.data;

    const primaryEmail = email_addresses?.find(e => e.id === primary_email_address_id);
    const email = primaryEmail?.email_address || email_addresses?.[0]?.email_address;
    const displayName = [first_name, last_name].filter(Boolean).join(" ") || null;

    if (email) {
      await supabase
        .from("user_profiles")
        .update({ email, display_name: displayName })
        .eq("clerk_id", clerkId);
    }
  }

  if (event.type === "user.deleted") {
    const { id: clerkId } = event.data;

    // Delete profile (cascades to user_licenses)
    await supabase
      .from("user_profiles")
      .delete()
      .eq("clerk_id", clerkId);

    console.log(`Deleted user profile for clerk_id: ${clerkId}`);
  }

  return NextResponse.json({ received: true });
}
