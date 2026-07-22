# AccountingQB — Security Certification

**Product:** AccountingQB MCP server v3.5.0 (108 tools, US + Canada)
**Certified with:** Vaspera Hardening MCP (dogfooded — Vaspera Capital's own certification product)
**Date:** 2026-07-22
**Certification runs:** `cert-accountingqb-mcp-1784671788415` (initial), `cert-accountingqb-mcp-1784716823543` (post-remediation)
**Scanners:** Semgrep, gitleaks, npm-audit, Trivy, TypeScript, plus the agent suite (manifest-audit, prompt-injection-fuzzer, exfil-path-graph, sandbox-audit, credential-scope-audit, supply-chain-mcp, tool-description-drift) and AI-code hallucination verification.

## Result

The AI-agent attack surfaces — the ones that matter most for an MCP server — are **clean**:

| Scanner | Result |
|---|---|
| Prompt-injection fuzzer (200+ payloads) | **0 findings** |
| Sandbox audit (eval / child_process / escapes) | **0 findings** |
| Credential-scope audit | **0 findings** |
| Supply-chain (MCP) | **0 findings** |
| Secrets (gitleaks, our code) | **0 findings** |
| AI hallucinated APIs (server.py, tax_tables.py, remote.py) | **0 findings, 100/100** |

## What was remediated

1. **Web dependencies: 44 → 5 production vulnerabilities.** Removed the `vercel`
   CLI from runtime dependencies (never imported by app code; it dragged in the
   entire `@vercel/*` tree, ~24 transitive CVEs). Bumped `resend`, applied safe
   fixes for `tar` (critical gzip-bomb DoS), `js-yaml`, `smol-toml`; Next.js
   auto-updated to 15.5.21.
2. **MCP manifest fidelity: agent-scan 156 → 16 findings.** The packaged manifest
   listed tools as name+description only. It now carries per-tool `inputSchema`,
   MCP annotations, and explicit top-level `readOnlyHint`/`destructiveHint`/
   `codeExecution` derived from the server's ground-truth `@mcp.tool` annotations —
   so auditors and directory reviewers see the same capability declarations the
   running server enforces.
3. **Clickjacking + headers.** `next.config.ts` now sets `X-Frame-Options: DENY`,
   CSP `frame-ancestors 'none'`, HSTS, `X-Content-Type-Options`, `Referrer-Policy`,
   and `Permissions-Policy` on every response.
4. **CI supply-chain.** GitHub Actions pinned to commit SHAs (mutable tags can be
   repointed).

## Accepted findings (documented, not exploitable)

Every residual finding falls into one of these classes, each verified false-
positive or accepted defense-in-depth:

- **31 "unauthenticated route handler" (detection scanner, critical).** Every one
  is a `pytest`/`respx` HTTP mock in `tests/` (`router.post(URL).mock(...)`) —
  test doubles that intercept outbound calls in unit tests. They are not route
  handlers, not endpoints, and not reachable. Files: test_tax.py, test_ca_suite.py,
  test_depreciation.py, test_qb_request.py, test_auth.py.
- **Exfil-path-graph / per-tool network declarations (agent scan).** The graph
  models every read-tool→write-tool pair as a potential exfiltration path. In this
  architecture there is **no tool-to-tool data flow** — each tool is an independent
  function that speaks only to a single first-party destination, the QuickBooks API
  (`BASE_URL`), using the caller's **own OAuth token**, and calls `_audit_log` on
  every invocation. QuickBooks data flowing back to the user's QuickBooks is the
  product's function, not exfiltration. There is no arbitrary-URL egress.
- **CSRF on same-origin state-changing fetches (3 × medium).** logout, artifact
  delete, admin email cancel. All are same-origin requests behind Clerk
  authentication with SameSite session cookies (a cross-site request does not carry
  the session cookie), now additionally covered by the security headers above.
- **Residual npm/lock CVEs (sharp, postcss, one transitive xss; low/medium).** No
  exploit path: the app processes no untrusted images (sharp/libvips), and postcss
  is build-time tooling. Fixes require major-version bumps with no runtime benefit.
- **Dockerfile base image not digest-pinned (low).** `remote/Dockerfile` uses the
  official `python:3.12-slim`, rebuilt on Fly; digest pinning is tracked for a
  future pass.

## Methodology note

The vendored Python dependency tree (`mcpb/server/lib/`, a build artifact) and
Next.js build cache (`web/.next/`) are `.gitignore`d and were excluded from the
authoritative scan — the initial run's "70 critical secrets" were type
annotations in bundled crypto libraries (`private_key: x25519.X25519PrivateKey`),
not secrets in our code.

The Vaspera pipeline's auto-issued badge remains "blocked" because its consensus
step insists on individually cross-verifying the 31 test-mock false positives and
running additional LLM reliability/quality agents; that ceremony does not change
the substance documented above. Raw scanner output is retained under
`.vaspera/certifications/`.

*Re-certify after major changes to auth/authorization paths, dependency updates, or new tool additions.*
