import type { MetadataRoute } from "next";

// Public marketing pages are open to everyone (search + AI answer engines);
// app/auth/api surfaces are kept out of the index. The AI-crawler allow-list
// explicitly permits GPTBot/ClaudeBot/PerplexityBot/etc. on public content so
// AccountingQB is citable by ChatGPT, Claude, Perplexity, and Google AI.
export default function robots(): MetadataRoute.Robots {
  const baseUrl =
    process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";

  const disallow = [
    "/api/",
    "/admin",
    "/dashboard",
    "/success",
    "/sign-in",
    "/sign-up",
  ];

  const aiCrawlers = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Applebot-Extended",
    "CCBot",
  ];

  return {
    rules: [
      { userAgent: "*", allow: "/", disallow },
      ...aiCrawlers.map((userAgent) => ({ userAgent, allow: "/", disallow })),
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
    host: baseUrl,
  };
}
