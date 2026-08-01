import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@clerk/nextjs/server";
import Anthropic from "@anthropic-ai/sdk";
import type { CampaignContent } from "@/lib/emails/templates/campaign";

// AI drafts the COPY for a marketing email; the branded template handles
// styling. The admin edits + previews + approves before anything sends.
// Model: claude-opus-4-8 (override via COMPOSE_MODEL).

const COHORT_HINTS: Record<string, string> = {
  active: "current paying customers — announce and get them to adopt the new capability",
  trialing: "people mid-trial — nudge them to activate and convert",
  stuck: "signed up but never connected QuickBooks — a gentle re-activation nudge",
  canceled: "former customers who churned — a win-back; lead with what's new since they left",
  all: "a mixed audience of current, trial, and former users — keep it broadly relevant",
};

const SYSTEM = `You are the marketing copywriter for AccountingQB, an AI tool that connects Claude to QuickBooks Online (119 tools for reports, bookkeeping cleanup, and US & Canadian tax prep; runs locally or via a zero-retention connector). Brand voice: clear, confident, practical, a little warm — never hypey, never spammy, no exclamation-point overload. You write concise marketing emails a small-business owner or bookkeeper would actually read.

Return ONLY a JSON object (no markdown fences, no prose) with this exact shape:
{
  "subject": "compelling, specific, <60 chars, no emoji",
  "preheader": "one-line preview text, <100 chars",
  "headline": "short in-email H1",
  "paragraphs": ["2-4 short paragraphs of body copy"],
  "bullets": ["optional 0-4 benefit bullets"],
  "ctaText": "short button label, e.g. 'See what's new'",
  "ctaUrl": "https://accountingqb.com relevant path",
  "signoff": "— Ryan, AccountingQB"
}
Keep it tight. Do not invent features that don't exist. Do not include an unsubscribe line — the system adds compliant footers automatically.`;

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if ((user.publicMetadata as { role?: string })?.role !== "admin")
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const goal = String(body.goal || "").trim();
  const cohort = String(body.cohort || "all");
  const tone = String(body.tone || "").trim();
  if (!goal) return NextResponse.json({ error: "Describe the campaign goal" }, { status: 400 });

  const audience = COHORT_HINTS[cohort] || COHORT_HINTS.all;
  const userPrompt = `Draft a marketing email.
Goal: ${goal}
Audience: ${audience}${tone ? `\nTone/notes: ${tone}` : ""}`;

  try {
    const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    const response = await anthropic.messages.create({
      model: process.env.COMPOSE_MODEL || "claude-opus-4-8",
      max_tokens: 2048,
      system: SYSTEM,
      messages: [{ role: "user", content: userPrompt }],
    });
    const text =
      response.content[0]?.type === "text" ? response.content[0].text : "";

    // Robust parse: strip any accidental markdown fences, then JSON.parse.
    const cleaned = text.replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
    let draft: CampaignContent;
    try {
      draft = JSON.parse(cleaned) as CampaignContent;
    } catch {
      // Fallback: use the raw text as a single paragraph so the admin can edit.
      draft = {
        subject: goal.slice(0, 60),
        paragraphs: [text || "Draft failed to parse — edit below."],
        signoff: "— Ryan, AccountingQB",
      };
    }
    return NextResponse.json({ draft });
  } catch (e) {
    console.error("Compose draft failed:", e);
    return NextResponse.json({ error: "AI drafting failed" }, { status: 500 });
  }
}
