import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getSupabase } from "@/lib/supabase";
import { buildSupportSystemPrompt } from "@/lib/support-kb";
import {
  getSupportLimiter,
  rateLimitResponse,
  isRateLimitingEnabled,
} from "@/lib/ratelimit";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatRequest {
  message: string;
  conversationId?: string;
  context?: {
    licenseKey?: string;
    tier?: string;
    companies?: string[];
    currentPage?: string;
  };
}

/**
 * POST /api/support/chat
 * AI-powered support chat using Claude API.
 */
export async function POST(req: NextRequest) {
  // Rate limit: 20 messages per minute per IP
  if (isRateLimitingEnabled()) {
    const ip = req.headers.get("x-forwarded-for")?.split(",")[0] || "unknown";
    const { success, reset } = await getSupportLimiter().limit(ip);
    if (!success) {
      return rateLimitResponse(reset);
    }
  }

  try {
    const body: ChatRequest = await req.json();
    const { message, conversationId, context } = body;

    if (!message?.trim()) {
      return NextResponse.json(
        { error: "Message is required" },
        { status: 400 },
      );
    }

    const supabase = getSupabase();
    let convId = conversationId;
    let history: ChatMessage[] = [];

    // Load existing conversation if provided
    if (convId) {
      const { data: messages } = await supabase
        .from("support_messages")
        .select("role, content")
        .eq("conversation_id", convId)
        .order("created_at", { ascending: true });

      if (messages) {
        history = messages as ChatMessage[];
      }
    } else {
      // Create new conversation
      const { data: conv, error: convError } = await supabase
        .from("support_conversations")
        .insert({
          license_key: context?.licenseKey || null,
          anonymous_id: !context?.licenseKey ? crypto.randomUUID() : null,
          metadata: context ? JSON.stringify(context) : null,
        })
        .select("id")
        .single();

      if (convError) {
        console.error("Failed to create conversation:", convError);
        // Continue without persistence
      } else {
        convId = conv?.id;
      }
    }

    // Build system prompt with knowledge base
    const systemPrompt = buildSupportSystemPrompt(context);

    // Call Claude API
    const anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });

    const response = await anthropic.messages.create({
      model: process.env.SUPPORT_MODEL || "claude-sonnet-4-20250514",
      max_tokens: 1024,
      system: systemPrompt,
      messages: [
        ...history.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        })),
        { role: "user" as const, content: message },
      ],
    });

    const reply =
      response.content[0].type === "text" ? response.content[0].text : "";

    // Save messages to database
    if (convId) {
      await supabase.from("support_messages").insert([
        { conversation_id: convId, role: "user", content: message },
        { conversation_id: convId, role: "assistant", content: reply },
      ]);
    }

    // Detect if escalation might be needed
    const escalateKeywords = [
      "talk to human",
      "speak to someone",
      "real person",
      "contact support",
      "this isn't working",
      "frustrated",
      "give up",
    ];
    const shouldEscalate = escalateKeywords.some(
      (kw) =>
        message.toLowerCase().includes(kw) ||
        reply.toLowerCase().includes("contact support@vasperacapital.com"),
    );

    // Track analytics
    if (convId) {
      const topic = detectTopic(message);
      await supabase.from("support_analytics").insert({
        topic,
        resolved_self: !shouldEscalate,
        escalated: shouldEscalate,
      });
    }

    return NextResponse.json({
      reply,
      conversationId: convId,
      escalate: shouldEscalate,
    });
  } catch (err) {
    console.error("Support chat error:", err);
    return NextResponse.json(
      { error: "Failed to process message" },
      { status: 500 },
    );
  }
}

/**
 * Detect the topic of a support message for analytics.
 */
function detectTopic(message: string): string {
  const lower = message.toLowerCase();

  if (
    lower.includes("install") ||
    lower.includes("config") ||
    lower.includes("uvx") ||
    lower.includes("setup")
  ) {
    return "installation";
  }
  if (
    lower.includes("oauth") ||
    lower.includes("connect") ||
    lower.includes("quickbooks") ||
    lower.includes("authorize")
  ) {
    return "oauth";
  }
  if (
    lower.includes("tool") ||
    lower.includes("report") ||
    lower.includes("p&l") ||
    lower.includes("schedule c")
  ) {
    return "tools";
  }
  if (
    lower.includes("license") ||
    lower.includes("billing") ||
    lower.includes("cancel") ||
    lower.includes("price")
  ) {
    return "account";
  }
  if (
    lower.includes("error") ||
    lower.includes("not working") ||
    lower.includes("help")
  ) {
    return "troubleshooting";
  }

  return "general";
}
