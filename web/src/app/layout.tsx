import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/next";
import SupportWidget from "@/components/support/SupportWidget";
import { PostHogProvider } from "@/components/PostHogProvider";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";

export const metadata: Metadata = {
  title: {
    default: "AccountingQB — AI-Powered QuickBooks for Claude",
    template: "%s | AccountingQB",
  },
  description:
    "125 AI tools connecting Claude to your QuickBooks Online. Run reports, reconcile books, prep US & Canadian taxes, detect anomalies — all through natural conversation. Runs locally or through our zero-retention connector — we never store your books.",
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
  // Google Search Console ownership verification (Settings > Ownership >
  // HTML tag). Set the token via env; omitted from markup when unset.
  ...(process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION
    ? {
        verification: {
          google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
        },
      }
    : {}),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName: "AccountingQB",
    title: "AccountingQB — AI-Powered QuickBooks for Claude",
    description:
      "125 AI tools connecting Claude to your QuickBooks Online. Run it locally or via our zero-retention connector — we never store your books. 14-day free trial.",
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
      "125 AI tools connecting Claude to your QuickBooks Online. Runs locally or via our zero-retention connector — we never store your books.",
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
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AccountingQB",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows, macOS, Linux",
    description:
      "125 AI tools connecting Claude to your QuickBooks Online for automated bookkeeping, tax prep, and financial analysis for US and Canadian businesses.",
    offers: [
      {
        "@type": "Offer",
        name: "Solopreneur",
        price: "39.00",
        priceCurrency: "USD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
      {
        "@type": "Offer",
        name: "Business",
        price: "99.00",
        priceCurrency: "USD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
      {
        "@type": "Offer",
        name: "Firm",
        price: "299.00",
        priceCurrency: "USD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
      },
    ],
    aggregateRating: undefined,
  };

  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="bg-[#0a0e1a] text-gray-100 antialiased">
        <PostHogProvider>
          <ClerkProvider afterSignInUrl="/dashboard" afterSignUpUrl="/dashboard">
            {children}
            <Analytics />
            <SupportWidget />
          </ClerkProvider>
        </PostHogProvider>
      </body>
    </html>
  );
}
