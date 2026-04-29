"use client";

import { useAuth, UserButton } from "@clerk/nextjs";

/* Inline Logo SVG Component */
function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lg" x1="60" y1="60" x2="452" y2="452" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="40%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <path d="M 210 108 A 148 148 0 1 1 209.99 108 Z M 210 164 A 92 92 0 1 0 210.01 164 Z"
        fill="url(#lg)" fillRule="evenodd" />
      <rect x="290" y="310" width="120" height="52" rx="26" fill="url(#lg)" transform="rotate(42, 350, 336)" />
      <rect x="290" y="118" width="42" height="268" rx="4" fill="url(#lg)" />
      <path d="M 311 118 L 360 118 A 62 62 0 0 1 360 242 L 311 242 Z" fill="url(#lg)" />
      <path d="M 311 242 L 370 242 A 72 72 0 0 1 370 386 L 311 386 Z" fill="url(#lg)" />
      <path d="M 318 148 L 348 148 A 34 34 0 0 1 348 216 L 318 216 Z" fill="#0a0e1a" />
      <path d="M 318 268 L 355 268 A 42 42 0 0 1 355 364 L 318 364 Z" fill="#0a0e1a" />
    </svg>
  );
}

export default function LandingNav() {
  const { isSignedIn, isLoaded } = useAuth();

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/[0.06] bg-[#0a0e1a]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <a href="/" className="flex items-center gap-2.5">
          <LogoMark className="h-8 w-8" />
          <span className="text-lg font-bold tracking-tight text-white">
            Accounting<span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">QB</span>
          </span>
        </a>
        <div className="hidden items-center gap-8 md:flex">
          <a href="#features" className="text-sm text-gray-400 transition hover:text-white">Features</a>
          <a href="#demo" className="text-sm text-gray-400 transition hover:text-white">Demo</a>
          <a href="#pricing" className="text-sm text-gray-400 transition hover:text-white">Pricing</a>
          <a href="#faq" className="text-sm text-gray-400 transition hover:text-white">FAQ</a>
        </div>
        <div className="flex items-center gap-4">
          {!isLoaded ? (
            <div className="h-8 w-8 animate-pulse rounded-full bg-white/10" />
          ) : isSignedIn ? (
            <>
              <a
                href="/dashboard"
                className="text-sm text-gray-400 transition hover:text-white"
              >
                Dashboard
              </a>
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: "w-8 h-8",
                  },
                }}
              />
            </>
          ) : (
            <>
              <a
                href="/sign-in"
                className="text-sm text-gray-400 transition hover:text-white"
              >
                Sign in
              </a>
              <a
                href="#pricing"
                className="rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:shadow-blue-500/30 hover:brightness-110"
              >
                Get Started
              </a>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
