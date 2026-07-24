"use client";

import { useState } from "react";

interface Draft {
  subject: string;
  preheader: string;
  headline: string;
  body: string; // paragraphs separated by blank lines
  bullets: string; // one per line
  ctaText: string;
  ctaUrl: string;
  signoff: string;
}

const EMPTY: Draft = {
  subject: "",
  preheader: "",
  headline: "",
  body: "",
  bullets: "",
  ctaText: "",
  ctaUrl: "",
  signoff: "— Ryan, AccountingQB",
};

const COHORTS = [
  { key: "active", label: "Active (paying)" },
  { key: "trialing", label: "Trialing" },
  { key: "stuck", label: "Stuck (no QB)" },
  { key: "canceled", label: "Cancelled (win-back)" },
  { key: "all", label: "Everyone" },
];

function toContent(d: Draft) {
  return {
    subject: d.subject,
    preheader: d.preheader || undefined,
    headline: d.headline || undefined,
    paragraphs: d.body.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean),
    bullets: d.bullets.split("\n").map((b) => b.trim()).filter(Boolean),
    ctaText: d.ctaText || undefined,
    ctaUrl: d.ctaUrl || undefined,
    signoff: d.signoff || undefined,
  };
}

export default function ComposePage() {
  const [goal, setGoal] = useState("");
  const [cohort, setCohort] = useState("active");
  const [tone, setTone] = useState("");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [drafting, setDrafting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [perHour, setPerHour] = useState(60);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setDraft((d) => ({ ...d, [k]: e.target.value }));

  const aiDraft = async () => {
    if (!goal.trim()) { setStatus("Describe the campaign goal first."); return; }
    setDrafting(true); setStatus(null);
    try {
      const res = await fetch("/api/admin/compose/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, cohort, tone }),
      });
      const data = await res.json();
      if (!res.ok) { setStatus(data.error || "Draft failed."); return; }
      const c = data.draft;
      setDraft({
        subject: c.subject || "",
        preheader: c.preheader || "",
        headline: c.headline || "",
        body: (c.paragraphs || []).join("\n\n"),
        bullets: (c.bullets || []).join("\n"),
        ctaText: c.ctaText || "",
        ctaUrl: c.ctaUrl || "",
        signoff: c.signoff || "— Ryan, AccountingQB",
      });
      setStatus("Draft ready — edit, preview, then test before sending.");
    } catch { setStatus("Network error."); }
    finally { setDrafting(false); }
  };

  const call = async (mode: "test" | "dryRun" | "send") => {
    setBusy(true); setStatus(null);
    try {
      const res = await fetch("/api/admin/compose/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: toContent(draft), cohort, mode, perHour }),
      });
      const data = await res.json();
      if (!res.ok) { setStatus(data.error || "Failed."); return; }
      if (mode === "test") setStatus(`✓ Test sent to ${data.to}. Check your inbox.`);
      else if (mode === "dryRun") setStatus(`${data.eligible} eligible recipients in "${cohort}" (${data.suppressed} unsubscribed, excluded).`);
      else setStatus(`✓ Scheduled ${data.scheduled} emails to "${cohort}" — sending ~${perHour}/hr over ~${data.approxHours}h.`);
    } catch { setStatus("Network error."); }
    finally { setBusy(false); }
  };

  const schedule = async () => {
    const dry = await fetch("/api/admin/compose/send", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: toContent(draft), cohort, mode: "dryRun", perHour }),
    }).then((r) => r.json());
    if (!dry.eligible) { setStatus("No eligible recipients."); return; }
    if (!window.confirm(`Send this to ${dry.eligible} people in "${cohort}"? They'll go out ~${perHour}/hr. This is a real send.`)) return;
    call("send");
  };

  const content = toContent(draft);
  const ready = !!draft.subject && content.paragraphs.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Compose Campaign</h1>
        <p className="text-gray-400 mt-1">
          Draft with AI, edit, preview, test — then schedule. Test accounts &amp;
          unsubscribers are auto-excluded; every send carries a compliant footer.
        </p>
      </div>

      {/* AI prompt row */}
      <div className="bg-[#131a2e] rounded-xl border border-cyan-500/20 p-5 space-y-3">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="What's the campaign? e.g. 'Announce the new Cowork plugin — one-click dashboard in Claude. Win back cancelled users by showing what's new.'"
          rows={2}
          className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-gray-500 focus:border-cyan-500/50 focus:outline-none"
        />
        <div className="flex flex-col sm:flex-row gap-3">
          <select value={cohort} onChange={(e) => setCohort(e.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white focus:outline-none">
            {COHORTS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <input value={tone} onChange={(e) => setTone(e.target.value)}
            placeholder="Tone / notes (optional)"
            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-gray-500 focus:outline-none" />
          <button onClick={aiDraft} disabled={drafting}
            className="rounded-lg bg-cyan-500/10 border border-cyan-500/40 px-4 py-2 text-sm font-medium text-cyan-400 hover:bg-cyan-500/20 transition disabled:opacity-50">
            {drafting ? "Drafting…" : "✨ Draft with AI"}
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Editor */}
        <div className="bg-[#131a2e] rounded-xl border border-white/10 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Edit</h2>
          <Field label="Subject"><input value={draft.subject} onChange={set("subject")} className={inp} /></Field>
          <Field label="Preheader"><input value={draft.preheader} onChange={set("preheader")} className={inp} /></Field>
          <Field label="Headline"><input value={draft.headline} onChange={set("headline")} className={inp} /></Field>
          <Field label="Body (blank line = new paragraph)"><textarea value={draft.body} onChange={set("body")} rows={7} className={inp} /></Field>
          <Field label="Bullets (one per line)"><textarea value={draft.bullets} onChange={set("bullets")} rows={3} className={inp} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Button text"><input value={draft.ctaText} onChange={set("ctaText")} className={inp} /></Field>
            <Field label="Button URL"><input value={draft.ctaUrl} onChange={set("ctaUrl")} className={inp} /></Field>
          </div>
          <Field label="Sign-off"><input value={draft.signoff} onChange={set("signoff")} className={inp} /></Field>
        </div>

        {/* Preview */}
        <div className="space-y-4">
          <div className="bg-[#0a0e1a] rounded-xl border border-white/10 overflow-hidden">
            <div className="px-4 py-2 border-b border-white/5 text-xs text-gray-500">
              Preview · subject: <span className="text-gray-300">{draft.subject || "—"}</span>
            </div>
            <div className="p-6 text-center">
              <div className="text-lg font-bold mb-4"><span className="text-cyan-400">Accounting</span><span className="text-blue-500">QB</span></div>
              <div className="bg-[#131a2e] rounded-xl border border-white/10 p-6 text-left">
                {draft.headline && <h3 className="text-white text-lg font-semibold mb-3">{draft.headline}</h3>}
                {content.paragraphs.map((p, i) => <p key={i} className="text-gray-300 text-sm mb-3 leading-relaxed">{p}</p>)}
                {content.bullets && content.bullets.length > 0 && (
                  <ul className="text-gray-300 text-sm mb-3 list-disc pl-5 space-y-1">
                    {content.bullets.map((b, i) => <li key={i}>{b}</li>)}
                  </ul>
                )}
                {draft.ctaText && <div className="my-4"><span className="inline-block rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-5 py-2 text-white text-sm font-medium">{draft.ctaText}</span></div>}
                {draft.signoff && <p className="text-gray-400 text-sm mt-4">{draft.signoff}</p>}
              </div>
              <p className="text-[10px] text-gray-600 mt-3">Unsubscribe + mailing address are appended automatically on send.</p>
            </div>
          </div>

          {/* Actions */}
          <div className="bg-[#131a2e] rounded-xl border border-white/10 p-5 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={() => call("test")} disabled={!ready || busy}
                className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white hover:bg-white/10 disabled:opacity-40">
                Send test to me
              </button>
              <button onClick={() => call("dryRun")} disabled={!ready || busy}
                className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white hover:bg-white/10 disabled:opacity-40">
                Check recipients
              </button>
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span>throttle</span>
                <input type="number" min={1} max={500} value={perHour}
                  onChange={(e) => setPerHour(Number(e.target.value))}
                  className="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white" />
                <span>/hr</span>
              </div>
              <button onClick={schedule} disabled={!ready || busy}
                className="rounded-lg bg-cyan-500/10 border border-cyan-500/40 px-4 py-2 text-sm font-medium text-cyan-400 hover:bg-cyan-500/20 disabled:opacity-40">
                {busy ? "Working…" : "Schedule campaign"}
              </button>
            </div>
            {status && <p className="text-xs text-gray-300">{status}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

const inp = "w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-cyan-500/50 focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-gray-400">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
