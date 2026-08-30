import { NextRequest, NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import { Resend } from "resend";

// Lazy initialization to avoid build-time errors
let resend: Resend | null = null;

function getResend(): Resend {
  if (!resend) {
    resend = new Resend(process.env.RESEND_API_KEY);
  }
  return resend;
}

interface EscalateRequest {
  conversationId: string;
  licenseKey?: string;
  userEmail?: string;
  additionalContext?: string;
}

/**
 * POST /api/support/escalate
 * Send conversation to human support via email.
 */
export async function POST(req: NextRequest) {
  try {
    const body: EscalateRequest = await req.json();
    const { conversationId, licenseKey, userEmail, additionalContext } = body;

    if (!conversationId) {
      return NextResponse.json(
        { error: "Conversation ID is required" },
        { status: 400 },
      );
    }

    const supabase = getSupabase();

    // Load conversation and messages
    const { data: conversation } = await supabase
      .from("support_conversations")
      .select("*")
      .eq("id", conversationId)
      .single();

    const { data: messages } = await supabase
      .from("support_messages")
      .select("role, content, created_at")
      .eq("conversation_id", conversationId)
      .order("created_at", { ascending: true });

    if (!conversation || !messages) {
      return NextResponse.json(
        { error: "Conversation not found" },
        { status: 404 },
      );
    }

    // Format conversation transcript
    const transcript = messages
      .map((m) => {
        const time = new Date(m.created_at).toLocaleTimeString();
        const role = m.role === "user" ? "Customer" : "AI Agent";
        return `[${time}] ${role}:\n${m.content}`;
      })
      .join("\n\n---\n\n");

    // Mark conversation as escalated
    await supabase
      .from("support_conversations")
      .update({ status: "escalated" })
      .eq("id", conversationId);

    // Send email to support team
    const { error: emailError } = await getResend().emails.send({
      from: "AccountingQB Support <noreply@accountingqb.com>",
      to: process.env.SUPPORT_EMAIL || "support@vasperacapital.com",
      replyTo: userEmail || undefined,
      subject: `[Escalation] Support Request - ${licenseKey || "Anonymous"}`,
      html: `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f5f5f5;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px;">
    <h2 style="color: #333; margin-top: 0;">Support Escalation</h2>

    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>License Key:</strong></td>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;">${licenseKey || "Not provided"}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Customer Email:</strong></td>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;">${userEmail || "Not provided"}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;"><strong>Conversation ID:</strong></td>
        <td style="padding: 8px 0; border-bottom: 1px solid #eee;">${conversationId}</td>
      </tr>
    </table>

    ${
      additionalContext
        ? `
    <h3 style="color: #333;">Additional Context</h3>
    <p style="background: #f9f9f9; padding: 12px; border-radius: 4px;">${additionalContext}</p>
    `
        : ""
    }

    <h3 style="color: #333;">Conversation Transcript</h3>
    <div style="background: #f9f9f9; padding: 16px; border-radius: 4px; white-space: pre-wrap; font-size: 14px; line-height: 1.5;">
${transcript}
    </div>

    <p style="color: #666; font-size: 12px; margin-top: 24px;">
      This escalation was triggered automatically when the AI agent could not resolve the customer's issue.
    </p>
  </div>
</body>
</html>
      `,
    });

    if (emailError) {
      console.error("Failed to send escalation email:", emailError);
      return NextResponse.json(
        { error: "Failed to send escalation email" },
        { status: 500 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Escalation error:", err);
    return NextResponse.json({ error: "Failed to escalate" }, { status: 500 });
  }
}
