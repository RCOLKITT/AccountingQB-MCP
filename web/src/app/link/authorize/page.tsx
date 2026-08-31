import Link from "next/link";
import { currentUser } from "@clerk/nextjs/server";
import { getSupabase } from "@/lib/supabase";
import { isAllowedRedirectUri } from "@/lib/link";
import Consent from "./consent";

export const dynamic = "force-dynamic";

const PEER_LABEL: Record<string, string> = { coffer: "Coffer" };

function first(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v || "").trim();
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#0a0e1a",
        color: "#e5e7eb",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 460,
          background: "#0f1629",
          border: "1px solid #1e293b",
          borderRadius: 16,
          padding: 32,
        }}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * GET /link/authorize?peer=coffer&redirect_uri=…&state=…&code_challenge=…&code_challenge_method=S256
 *
 * The "Connect AccountingQB" consent screen. Middleware requires a Clerk session, so an
 * un-signed-in user is bounced to sign-in / sign-up and returns here — the "log in, boom connected"
 * step. We validate the redirect_uri + challenge, confirm the account has a plan, then render the
 * consent card. Approval mints the code and returns to the peer (see ./consent + /api/link/authorize).
 */
export default async function AuthorizePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const peer = first(sp.peer) || "coffer";
  const redirectUri = first(sp.redirect_uri);
  const state = first(sp.state);
  const codeChallenge = first(sp.code_challenge);
  const method = (first(sp.code_challenge_method) || "S256").toUpperCase();
  const label = PEER_LABEL[peer] || peer;

  // Validate the request before showing anything trust-bearing.
  if (peer !== "coffer") {
    return (
      <Shell>
        <h1 style={{ fontSize: 20, margin: 0 }}>Unsupported app</h1>
        <p style={{ color: "#94a3b8", fontSize: 14 }}>
          AccountingQB can’t link “{peer}”.
        </p>
      </Shell>
    );
  }
  if (
    !isAllowedRedirectUri(redirectUri) ||
    !codeChallenge ||
    method !== "S256"
  ) {
    return (
      <Shell>
        <h1 style={{ fontSize: 20, margin: 0 }}>Invalid link request</h1>
        <p style={{ color: "#94a3b8", fontSize: 14 }}>
          This connection link is malformed or came from an untrusted source.
          Start the connection again from inside {label}.
        </p>
      </Shell>
    );
  }

  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress?.toLowerCase() || "";

  // Must have a plan — you can't link a product you don't hold.
  const supabase = getSupabase();
  const { data: lics } = email
    ? await supabase
        .from("licenses")
        .select("key")
        .eq("email", email)
        .in("status", ["active", "trialing"])
        .limit(1)
    : { data: null };

  if (!email || !lics || lics.length === 0) {
    return (
      <Shell>
        <div
          style={{
            fontSize: 13,
            letterSpacing: 1,
            color: "#22d3ee",
            fontWeight: 700,
          }}
        >
          ACCOUNTINGQB
        </div>
        <h1 style={{ fontSize: 21, margin: "8px 0 6px" }}>
          An AccountingQB plan is required
        </h1>
        <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.5 }}>
          You’re signed in as{" "}
          <strong style={{ color: "#e5e7eb" }}>{email || "an account"}</strong>,
          but it has no active AccountingQB plan. Start a free trial, then
          connect {label}.
        </p>
        <Link
          href="/pricing"
          style={{
            display: "inline-block",
            marginTop: 16,
            padding: "11px 18px",
            borderRadius: 10,
            background: "#22d3ee",
            color: "#0a0e1a",
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          Start free trial
        </Link>
      </Shell>
    );
  }

  return (
    <Shell>
      <div
        style={{
          fontSize: 13,
          letterSpacing: 1,
          color: "#22d3ee",
          fontWeight: 700,
        }}
      >
        ACCOUNTINGQB
      </div>
      <h1 style={{ fontSize: 21, margin: "8px 0 6px" }}>Connect {label}</h1>
      <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.55 }}>
        <strong style={{ color: "#e5e7eb" }}>{label}</strong> wants to link to
        your AccountingQB account{" "}
        <strong style={{ color: "#e5e7eb" }}>{email}</strong>. Once linked,{" "}
        {label} can request your business figures (owner draws, tax set-aside)
        and send flagged expenses here to book — always with your confirmation.
        Nothing about your books is stored on our servers.
      </p>
      <Consent
        peer={peer}
        redirectUri={redirectUri}
        state={state}
        codeChallenge={codeChallenge}
      />
      <p style={{ color: "#64748b", fontSize: 12, marginTop: 18 }}>
        You can disconnect any time from Settings. Returns to{" "}
        <span style={{ color: "#94a3b8" }}>{new URL(redirectUri).host}</span>.
      </p>
    </Shell>
  );
}
