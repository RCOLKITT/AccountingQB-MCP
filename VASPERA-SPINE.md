# VASPERA-SPINE.md — the Vaspera Capital Engineering Standard

**How to use this file:** drop it into any Vaspera Capital repository and tell the
agent working there: *"Bring this repo up to the spine. Follow VASPERA-SPINE.md."*
This file is the complete instruction set. The canonical copy lives in
`vasperacapital-website/docs/VASPERA-SPINE.md`; copies in other repos should note
the version date below.

**Standard version:** 2026-08-26 (v1)

---

## AccountingQB adaptation (repo-local, read first)

- **Repo type:** hybrid — MCP server (`mcpb/`), Next.js/Vercel app (`web/`), remote
  connector (`mcpb/src/accountingqb/remote.py`), Tauri desktop (`accountingqb-desktop-tauri/`
  + `accountingqb-local/`), and a Claude plugin (`cowork-plugin/`). Apply §7 adaptations for
  each surface.
- **Constitution wins.** This is a money/books product with its own `CONSTITUTION.md`. Per §7,
  where the spine and the Constitution conflict, the **Constitution wins** and the conflict is
  reported. The Constitution is the higher law here; the spine adds the uniform engineering
  layer around it.
- **Live audit:** `SPINE-STATUS.md` at the repo root is this repo's honest audit against this
  standard — keep it true, not impressive.

---

## 0. Prime directives (read before doing anything)

1. **AUDIT BEFORE BUILD.** Almost every capability you're asked for already exists in some
   form — built but broken, disabled, or unwired. Prove a thing does not exist before creating
   it. Rebuilding what exists is the #1 agent failure mode in this organization's history.
2. **ZERO THEATER.** No mocks, stubs, placeholders, or fake data anywhere in production paths.
   A gap you cannot close honestly gets DECLARED in the status report — never papered over. A
   declared gap is compliant; a faked gate is the one unforgivable violation of this spec.
3. **VERIFY LIVE BEFORE "DONE."** Nothing is complete until exercised on its real path — a test
   run that hits the real service, a page loaded in a real browser, a cron observed firing.
   Typecheck-passes is not done.
4. **SHADOW-FIRST for anything with side effects.** New automated behavior ships observing/
   logging first, acts second, after its observations are reviewed.
5. **Small PRs, conventional-commit titles** (`feat:`/`fix:`/`chore:`/`docs:`…), merged only
   when local gates are green.

## 1. The deliverable: SPINE-STATUS.md

Your first and last artifact. Create `SPINE-STATUS.md` at the repo root with three sections
(Layers inventory, Gate status, Declared gaps) and keep it truthful as you work. The audit is
**Phase 0** and comes before any fixes.

## 2. The layers inventory

Assess which exist: (1) Presentation, (2) API layer (auth-gated or explicitly-public-with-reason),
(3) Domain/execution, (4) Governance/policy (flags/gates/allowlists/rate limits + registry),
(5) Autonomous response (watchdogs/self-healing; N/A for libs/static), (6) Data (schema
ownership, migrations in VC, integrity checks, backup story — §5.4), (7) Intelligence (AI features
with grounding, injection defense, rerunnable eval; N/A if none), (8) Scheduling & ops (crons:
where they run, what monitors them, what alerts on silence), (9) Secrets & supply chain (§5.1 +
lockfile committed + dependency audit clean/documented).

## 3. Uniform gates (every repo, no exceptions)

Run locally AND in CI (self-hosted runner for per-push). Installed-and-red beats absent.

| Gate | Requirement |
|------|-------------|
| Typecheck | `tsc --noEmit` (or equivalent) exits 0. BLOCKING. |
| Lint | zero errors; warnings budget documented. |
| Format | `--check` clean. |
| Tests | suite runs and passes; no tests = declared gap + starter plan (top 3 riskiest paths). |
| Secret scan | no hardcoded credentials. |
| Theater scan | grep `mock\|stub\|placeholder\|fake\|dummy` outside tests; hits removed or `// SAFE:`-annotated. |
| Branch protection | `main` requires PRs + green checks. Verify in GitHub settings, don't assume. |

## 4. Uniform operational artifacts

Honest minimal versions if absent — never boilerplate that overstates reality:
**README.md** (what/run/deploy), **RUNBOOK.md** (deploy/rollback/restart/3am steps; libs: release),
**INCIDENTS.md** (post-mortem log: timeline, blast radius, all root causes, what detected/responded,
the structural change that kills the CLASS — seed from repo history), **CLAUDE.md** (repo agent
rules + pointer to this spec).

## 5. Infrastructure standards

- **5.1 Secrets** — all in Doppler, injected at runtime; none in git/committed-.env/CI vars when
  Doppler can serve. Scoped, revocable deploy creds (read-only deploy keys, service tokens).
- **5.2 Scheduling** — no prod job depends on a laptop; systemd timers on Vaspera infra, UTC pinned
  (`TZ=UTC`); every job writes a heartbeat; independent alert on silence; external dead-man switch.
- **5.3 Observability** — prod services uptime-monitored + public status page where public-facing;
  alerts verified DELIVERED end-to-end at least once.
- **5.4 Data** — migrations in VC; schema drift detectable by a command; automated off-site backup
  with a RESTORE DRILL done once and written up; no ambiguous nulls (computed-real, declared-gap,
  or integrity-alarmed).
- **5.5 AI features** — grounded only in recorded, user-scoped data; identity server-side; whitelist
  rendering of model output; rerunnable eval rerun before widening any allowlist / changing
  prompt/model.

## 6. Execution order

Phase 0 Audit (fill SPINE-STATUS.md; touch nothing) → Phase 1 Gates (install/repair §3; green what
can be, declare rest) → Phase 2 Artifacts (§4, honest) → Phase 3 Infrastructure (§5 that applies,
shadow-first) → Phase 4 Report (final SPINE-STATUS.md; one PR per phase; owner summary with every
declared gap + cost to close).

## 7. Repo-type adaptations

- **Next.js/Vercel apps** — build with env injected; prod env config verified against the ACTUAL
  host (Vercel env, not just Doppler — they drift); e2e via Playwright with a dedicated test user.
- **MCP servers / CLIs** — publishable artifact installs clean from a fresh env; version bump +
  changelog on every publish; telemetry opt-out documented.
- **Static/marketing sites** — layers 4-8 mostly N/A (say so); gates + §4 artifacts still apply.
- **Trading/money systems** — everything above PLUS their own constitutions govern the money path.
  This spec never overrides a constitution; where they conflict, the constitution wins and the
  conflict gets reported.

## 8. What this spec is for

Vaspera Capital's engineering claim is that AI-built software can carry every layer of
accountability that "enterprise-grade" has ever meant: gates that block, incidents that teach,
monitoring that pages, secrets that rotate, documentation that matches reality. The SPINE-STATUS.md
files across our repos are that claim, auditable by anyone. The job in this repo is to make that
document TRUE — not impressive. Impressive follows.
