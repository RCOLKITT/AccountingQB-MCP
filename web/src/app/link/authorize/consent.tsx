"use client";

import { useState } from "react";

const PEER_LABEL: Record<string, string> = { coffer: "Coffer" };

/**
 * The approve/deny buttons for the "Connect AccountingQB" consent screen. On approve we POST to
 * /api/link/authorize (which mints the PKCE-bound code) and follow the returned redirect back to
 * the peer's callback. On deny we bounce back with ?error=access_denied so the peer can clean up.
 */
export default function Consent({
  peer,
  redirectUri,
  state,
  codeChallenge,
}: {
  peer: string;
  redirectUri: string;
  state: string;
  codeChallenge: string;
}) {
  const [busy, setBusy] = useState<"" | "allow" | "deny">("");
  const [err, setErr] = useState("");
  const label = PEER_LABEL[peer] || peer;

  async function allow() {
    setBusy("allow");
    setErr("");
    try {
      const r = await fetch("/api/link/authorize", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ peer, redirectUri, state, codeChallenge }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.redirectUrl) {
        setErr(j.error || "Could not complete the link. Please try again.");
        setBusy("");
        return;
      }
      window.location.href = j.redirectUrl;
    } catch {
      setErr("Network error. Please try again.");
      setBusy("");
    }
  }

  function deny() {
    setBusy("deny");
    const u = new URL(redirectUri);
    u.searchParams.set("error", "access_denied");
    if (state) u.searchParams.set("state", state);
    window.location.href = u.toString();
  }

  return (
    <div style={{ marginTop: 24 }}>
      {err ? (
        <p style={{ color: "#f87171", fontSize: 14, marginBottom: 12 }}>{err}</p>
      ) : null}
      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={allow}
          disabled={!!busy}
          style={{
            flex: 1,
            padding: "12px 16px",
            borderRadius: 10,
            border: "none",
            background: "#22d3ee",
            color: "#0a0e1a",
            fontWeight: 700,
            fontSize: 15,
            cursor: busy ? "default" : "pointer",
            opacity: busy && busy !== "allow" ? 0.5 : 1,
          }}
        >
          {busy === "allow" ? "Linking…" : `Allow & connect ${label}`}
        </button>
        <button
          onClick={deny}
          disabled={!!busy}
          style={{
            padding: "12px 16px",
            borderRadius: 10,
            border: "1px solid #334155",
            background: "transparent",
            color: "#cbd5e1",
            fontWeight: 600,
            fontSize: 15,
            cursor: busy ? "default" : "pointer",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
