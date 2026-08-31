"use client";

import { useEffect, useRef, useState } from "react";
import {
  matchDemo,
  DEMO_SUGGESTIONS,
  DEMO_COMPANY,
  type DemoCard,
  type DemoResponse,
} from "@/lib/demo-script";

/* Inline brand mark for the assistant avatar (matches the site logo). */
function LogoMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 512 512"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient
          id="demo-lg"
          x1="60"
          y1="60"
          x2="452"
          y2="452"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="40%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      <path
        d="M 210 108 A 148 148 0 1 1 209.99 108 Z M 210 164 A 92 92 0 1 0 210.01 164 Z"
        fill="url(#demo-lg)"
        fillRule="evenodd"
      />
      <rect
        x="290"
        y="310"
        width="120"
        height="52"
        rx="26"
        fill="url(#demo-lg)"
        transform="rotate(42, 350, 336)"
      />
      <rect
        x="290"
        y="118"
        width="42"
        height="268"
        rx="4"
        fill="url(#demo-lg)"
      />
      <path
        d="M 311 118 L 360 118 A 62 62 0 0 1 360 242 L 311 242 Z"
        fill="url(#demo-lg)"
      />
      <path
        d="M 311 242 L 370 242 A 72 72 0 0 1 370 386 L 311 386 Z"
        fill="url(#demo-lg)"
      />
      <path
        d="M 318 148 L 348 148 A 34 34 0 0 1 348 216 L 318 216 Z"
        fill="#0d1220"
      />
      <path
        d="M 318 268 L 355 268 A 42 42 0 0 1 355 364 L 318 364 Z"
        fill="#0d1220"
      />
    </svg>
  );
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

function Card({ card }: { card: DemoCard }) {
  if (card.kind === "metrics") {
    return (
      <div>
        {card.title && (
          <p className="mb-2 font-medium text-white">{card.title}</p>
        )}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {card.items.map((it) => (
            <div key={it.label} className="rounded-lg bg-white/[0.04] p-2">
              <div className="text-gray-500">{it.label}</div>
              <div className={`text-lg font-bold ${it.tone}`}>{it.value}</div>
            </div>
          ))}
        </div>
        {card.note && <p className="mt-2 text-xs text-gray-400">{card.note}</p>}
      </div>
    );
  }
  if (card.kind === "lines") {
    return (
      <div>
        {card.title && (
          <p className="mb-2 font-medium text-white">{card.title}</p>
        )}
        <div className="space-y-1.5">
          {card.rows.map((r) => (
            <div
              key={r.label}
              className="flex items-baseline justify-between gap-4 border-b border-white/[0.05] pb-1.5 last:border-0"
            >
              <div>
                <span className={r.strong ? "text-white" : "text-gray-400"}>
                  {r.label}
                </span>
                {r.sub && (
                  <div className="text-[11px] text-gray-500">{r.sub}</div>
                )}
              </div>
              <span
                className={
                  r.strong
                    ? "font-bold text-cyan-400"
                    : "font-medium text-white"
                }
              >
                {r.value}
              </span>
            </div>
          ))}
        </div>
        {card.note && <p className="mt-2 text-xs text-gray-400">{card.note}</p>}
      </div>
    );
  }
  if (card.kind === "list") {
    return (
      <div>
        {card.title && (
          <p className="mb-2 font-medium text-white">{card.title}</p>
        )}
        <div className="space-y-2">
          {card.items.map((it) => (
            <div
              key={it.title}
              className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-[13px] font-medium text-white">
                  {it.title}
                </span>
                {it.badge && (
                  <span className="flex-shrink-0 rounded bg-cyan-500/[0.12] px-1.5 py-0.5 text-[10px] font-medium text-cyan-300">
                    {it.badge}
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-xs text-gray-400">{it.detail}</p>
            </div>
          ))}
        </div>
        {card.note && <p className="mt-2 text-xs text-gray-400">{card.note}</p>}
      </div>
    );
  }
  // score
  return (
    <div>
      <div className="flex items-center gap-3">
        <span className={`text-3xl font-bold ${scoreColor(card.score)}`}>
          {card.score}
        </span>
        <span className="text-sm font-medium text-white">
          {card.title}
          <span className="text-gray-500"> / 100</span>
        </span>
      </div>
      <ul className="mt-3 space-y-1">
        {card.findings.map((f) => (
          <li key={f} className="flex gap-2 text-xs text-gray-400">
            <span className="text-cyan-400">•</span>
            {f}
          </li>
        ))}
      </ul>
      {card.note && <p className="mt-2 text-xs text-gray-400">{card.note}</p>}
    </div>
  );
}

interface Msg {
  role: "user" | "assistant";
  text?: string;
  res?: DemoResponse;
}

export default function DemoChat() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: "assistant", res: matchDemo("") },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, typing]);

  function send(text: string) {
    const q = text.trim();
    if (!q || typing) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setTyping(true);
    // Simulated "thinking" delay so canned answers feel live.
    window.setTimeout(() => {
      setMessages((m) => [...m, { role: "assistant", res: matchDemo(q) }]);
      setTyping(false);
    }, 650);
  }

  return (
    <div className="glass rounded-2xl p-1 shadow-2xl shadow-blue-900/20">
      <div className="flex h-[560px] flex-col rounded-xl bg-[#0d1220]">
        {/* Window chrome */}
        <div className="flex items-center gap-2 border-b border-white/[0.06] px-5 py-3">
          <div className="h-3 w-3 rounded-full bg-red-500/60" />
          <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
          <div className="h-3 w-3 rounded-full bg-green-500/60" />
          <span className="ml-3 text-xs text-gray-500">
            {DEMO_COMPANY} · sample books
          </span>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 space-y-4 overflow-y-auto px-5 py-5"
        >
          {messages.map((msg, i) =>
            msg.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-md rounded-2xl rounded-br-md bg-blue-600/90 px-4 py-2.5 text-sm text-white">
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20">
                  <LogoMark className="h-5 w-5" />
                </div>
                <div className="min-w-0 max-w-lg space-y-2">
                  <div className="rounded-2xl rounded-tl-md bg-[#161d33] px-4 py-3 text-sm text-gray-300">
                    <p
                      className={
                        msg.res?.cards?.length
                          ? "mb-3 text-white"
                          : "text-white"
                      }
                    >
                      {msg.res?.intro}
                    </p>
                    <div className="space-y-3">
                      {msg.res?.cards?.map((c, j) => (
                        <Card key={j} card={c} />
                      ))}
                    </div>
                  </div>
                  {msg.res?.tools && msg.res.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 text-[10px] text-gray-500">
                      {msg.res.tools.map((t) => (
                        <span
                          key={t}
                          className="rounded bg-white/[0.04] px-1.5 py-0.5"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {msg.res?.followups && msg.res.followups.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {msg.res.followups.map((f) => (
                        <button
                          key={f}
                          onClick={() => send(f)}
                          className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[12px] text-gray-300 transition hover:border-cyan-500/30 hover:text-white"
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ),
          )}

          {typing && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20">
                <LogoMark className="h-5 w-5" />
              </div>
              <div className="flex items-center gap-1 rounded-2xl rounded-tl-md bg-[#161d33] px-4 py-3.5">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500" />
              </div>
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-white/[0.06] p-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {DEMO_SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[12px] text-gray-400 transition hover:border-cyan-500/30 hover:text-white"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask ${DEMO_COMPANY}'s books anything…`}
              className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder:text-gray-600 focus:border-cyan-500/40 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || typing}
              className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#0a0e1a] transition hover:bg-slate-200 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
