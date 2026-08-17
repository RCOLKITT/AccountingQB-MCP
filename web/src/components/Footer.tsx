/* Shared marketing footer. Extracted from the homepage so every marketing page
   (/, /about, …) renders the same footer from one source. Section anchors are
   root-relative (/#features) so they resolve from any route, not just "/". */

function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="footer-lg" x1="60" y1="60" x2="452" y2="452" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="40%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <path d="M 210 108 A 148 148 0 1 1 209.99 108 Z M 210 164 A 92 92 0 1 0 210.01 164 Z"
        fill="url(#footer-lg)" fillRule="evenodd" />
      <rect x="290" y="310" width="120" height="52" rx="26" fill="url(#footer-lg)" transform="rotate(42, 350, 336)" />
      <rect x="290" y="118" width="42" height="268" rx="4" fill="url(#footer-lg)" />
      <path d="M 311 118 L 360 118 A 62 62 0 0 1 360 242 L 311 242 Z" fill="url(#footer-lg)" />
      <path d="M 311 242 L 370 242 A 72 72 0 0 1 370 386 L 311 386 Z" fill="url(#footer-lg)" />
      <path d="M 318 148 L 348 148 A 34 34 0 0 1 348 216 L 318 216 Z" fill="#0a0e1a" />
      <path d="M 318 268 L 355 268 A 42 42 0 0 1 355 364 L 318 364 Z" fill="#0a0e1a" />
    </svg>
  );
}

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06] bg-[#0a0e1a]">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <a href="/" className="flex items-center gap-2">
              <LogoMark className="h-7 w-7" />
              <span className="text-lg font-bold text-white">
                Accounting<span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">QB</span>
              </span>
            </a>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-gray-500">
              AI-powered QuickBooks — bookkeeping, reporting, and US &amp; Canadian
              tax prep for Claude. Your books stay local or transit with zero
              retention.
            </p>
            <p className="mt-4 text-[13px] text-gray-600">
              A <a href="https://vasperacapital.com" className="text-gray-400 transition hover:text-white">Vaspera Capital</a> product &middot; Boston, USA
            </p>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-300">Product</h4>
            <ul className="mt-4 space-y-2.5 text-sm text-gray-500">
              <li><a href="/#features" className="transition hover:text-white">Features</a></li>
              <li><a href="/pricing" className="transition hover:text-white">Pricing</a></li>
              <li><a href="/#faq" className="transition hover:text-white">FAQ</a></li>
              <li><a href="/changelog" className="transition hover:text-white">What&rsquo;s new</a></li>
              <li><a href="/canada" className="transition hover:text-white">For Canadian businesses</a></li>
              <li><a href="/downloads/accountingqb.plugin" download className="transition hover:text-white">Download for Cowork</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-300">Security &amp; Trust</h4>
            <ul className="mt-4 space-y-2.5 text-sm text-gray-500">
              <li><a href="/security" className="transition hover:text-white">Security overview</a></li>
              <li><a href="/#tax-accuracy" className="transition hover:text-white">Tax data &amp; sources</a></li>
              <li><a href="/privacy" className="transition hover:text-white">Privacy Policy</a></li>
              <li><a href="/terms" className="transition hover:text-white">Terms of Service</a></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-300">Company</h4>
            <ul className="mt-4 space-y-2.5 text-sm text-gray-500">
              <li><a href="/about" className="transition hover:text-white">About</a></li>
              <li><a href="/dashboard" className="transition hover:text-white">Dashboard</a></li>
              <li><a href="/sign-in" className="transition hover:text-white">Sign In</a></li>
              <li><a href="mailto:support@vasperacapital.com" className="transition hover:text-white">Contact</a></li>
            </ul>
          </div>
        </div>
        <div className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-white/[0.06] pt-8 text-sm text-gray-600 sm:flex-row">
          <span>&copy; {new Date().getFullYear()} Vaspera Capital. All rights reserved.</span>
          <span>Not affiliated with Intuit Inc. QuickBooks is a trademark of Intuit Inc.</span>
        </div>
      </div>
    </footer>
  );
}
