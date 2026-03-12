import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://accountingqb.com";

export const metadata: Metadata = {
  title: {
    default: "AccountingQB — AI-Powered QuickBooks for Claude",
    template: "%s | AccountingQB",
  },
  description:
    "91 AI tools connecting Claude to your QuickBooks Online. Run reports, reconcile books, prep taxes, detect anomalies — all through natural conversation. Your data never leaves your machine.",
  keywords: [
    "quickbooks ai",
    "claude quickbooks",
    "mcp server",
    "ai accounting",
    "ai bookkeeping",
    "quickbooks automation",
    "schedule c ai",
    "tax prep ai",
    "small business accounting",
    "quickbooks claude integration",
  ],
  metadataBase: new URL(siteUrl),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName: "AccountingQB",
    title: "AccountingQB — AI-Powered QuickBooks for Claude",
    description:
      "91 AI tools connecting Claude to your QuickBooks Online. Your data stays local. 14-day free trial.",
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
      "91 AI tools connecting Claude to your QuickBooks Online. Your data stays local.",
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
      "91 AI tools connecting Claude to your QuickBooks Online for automated bookkeeping, tax prep, and financial analysis.",
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
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="bg-white text-gray-900 antialiased">{children}</body>
    </html>
  );
}
