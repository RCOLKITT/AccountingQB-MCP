import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/next";
import { Hanken_Grotesk, Fraunces } from "next/font/google";
import SupportWidget from "@/components/support/SupportWidget";
import { PostHogProvider } from "@/components/PostHogProvider";
import "./globals.css";

// Self-hosted at build (next/font). Hanken Grotesk = clean, credible UI type;
// Fraunces = a restrained serif for trust-forward headline accents.
const hanken = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-hanken",
  display: "swap",
});
const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["italic", "normal"],
  variable: "--font-fraunces",
  display: "swap",
});

const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";

export const metadata: Metadata = {
  title: {
    default: "AccountingQB — AI-Powered QuickBooks for Claude",
    template: "%s | AccountingQB",
  },
  description:
    "138 AI tools connecting Claude to your QuickBooks Online. Run reports, reconcile books, prep US & Canadian taxes, detect anomalies — all through natural conversation. Runs locally or through our zero-retention connector — we never store your books.",
  keywords: [
    "quickbooks ai",
    "claude quickbooks",
    "mcp server",
    "ai accounting",
    "ai bookkeeping",
    "quickbooks automation",
    "schedule c ai",
    "tax prep ai",
    "gst hst ai",
    "t2125",
    "canadian bookkeeping ai",
    "small business accounting",
    "quickbooks claude integration",
  ],
  metadataBase: new URL(siteUrl),
  // No canonical here: it would cascade to every page that doesn't set its
  // own, telling Google they're duplicates of the homepage. Each page sets
  // its own alternates (client pages via a segment layout.tsx).
  // Search-console ownership verification (Google Search Console + Bing Webmaster
  // Tools — Bing feeds ChatGPT Search & Copilot). Set the tokens via env; each is
  // omitted from markup when unset. DNS verification also works and needs neither.
  ...(() => {
    const google = process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION;
    const bing = process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION;
    const verification: { google?: string; other?: Record<string, string> } =
      {};
    if (google) verification.google = google;
    if (bing) verification.other = { "msvalidate.01": bing };
    return Object.keys(verification).length ? { verification } : {};
  })(),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName: "AccountingQB",
    title: "AccountingQB — AI-Powered QuickBooks for Claude",
    description:
      "138 AI tools connecting Claude to your QuickBooks Online. Run it locally or via our zero-retention connector — we never store your books. 14-day free trial.",
    images: [
      {
        url: `${siteUrl}/og-image.png`,
        width: 1200,
        height: 630,
        alt: "AccountingQB — Your QuickBooks, Powered by Claude",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AccountingQB — AI-Powered QuickBooks for Claude",
    description:
      "138 AI tools connecting Claude to your QuickBooks Online. Runs locally or via our zero-retention connector — we never store your books.",
    images: [`${siteUrl}/og-image.png`],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const offers = [
    { name: "Solopreneur", price: "39.00" },
    { name: "Business", price: "99.00" },
    { name: "Firm", price: "299.00" },
  ].map((o) => ({
    "@type": "Offer",
    name: o.name,
    price: o.price,
    priceCurrency: "USD",
    priceValidUntil: "2027-12-31",
    availability: "https://schema.org/InStock",
  }));

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: "AccountingQB",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Windows, macOS, Linux",
        url: siteUrl,
        description:
          "138 AI tools connecting Claude to your QuickBooks Online for automated bookkeeping, tax prep, and financial analysis for US and Canadian businesses.",
        offers,
      },
      {
        "@type": "Organization",
        name: "AccountingQB",
        url: siteUrl,
        logo: `${siteUrl}/og-image.png`,
        description:
          "AI-powered QuickBooks Online bookkeeping, reporting, and US & Canadian tax prep for Claude.",
        founder: { "@type": "Organization", name: "Vaspera Capital" },
        sameAs: ["https://github.com/RCOLKITT/AccountingQB-MCP"],
      },
    ],
  };

  return (
    <html lang="en" className={`${hanken.variable} ${fraunces.variable}`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="bg-[#0a0e1a] font-sans text-gray-100 antialiased">
        <PostHogProvider>
          <ClerkProvider
            afterSignInUrl="/dashboard"
            afterSignUpUrl="/dashboard"
          >
            {children}
            <Analytics />
            <SupportWidget />
          </ClerkProvider>
        </PostHogProvider>
      </body>
    </html>
  );
}
