"use client";

// Product analytics for AccountingQB. No-ops safely when
// NEXT_PUBLIC_POSTHOG_KEY is unset, so it's safe to ship before the key
// exists in Doppler. Autocapture gives page views + clicks out of the box;
// funnels are built in the PostHog UI on top of these events.

import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";

if (typeof window !== "undefined" && KEY && !(posthog as { __loaded?: boolean }).__loaded) {
  posthog.init(KEY, {
    api_host: HOST,
    capture_pageview: false, // captured manually below for the App Router
    capture_pageleave: true,
    autocapture: true,
    person_profiles: "identified_only",
  });
}

function PageViewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (!KEY) return;
    let url = window.origin + pathname;
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
    posthog.capture("$pageview", { $current_url: url });
  }, [pathname, searchParams]);
  return null;
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  if (!KEY) return <>{children}</>;
  return (
    <PHProvider client={posthog}>
      <Suspense fallback={null}>
        <PageViewTracker />
      </Suspense>
      {children}
    </PHProvider>
  );
}
