#!/usr/bin/env bash
# PII / customer-data scan — BLOCKING in CI (see tests.yml).
#
# This is a PUBLIC repo, and our privacy posture promises customers' books
# data is never retained by us — so no customer name, client company name,
# QuickBooks realm ID, or books detail (vendors, classes, transaction IDs
# tied to a real company) may appear in the tree, ever. Incident→test keeps
# the SHAPE of a report, never the data: fictionalize names before commit.
#
# Two layers:
#   1. Generic rules (always on): QBO realm-ID-shaped numbers, and emails at
#      domains outside the allowlist (our own + documentation domains).
#   2. PII_BLOCKLIST env (CI secret / gitignored local file .pii-blocklist):
#      pipe-separated, case-insensitive regexes of actual customer
#      identifiers. The list itself must NEVER be committed — that would be
#      the leak. Absent blocklist = layer 1 only (warn, don't fail).
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
FILES=$(git ls-files '*.py' '*.ts' '*.tsx' '*.md' '*.json' '*.mjs' '*.yml' '*.yaml' '*.sh' '*.toml' \
  | grep -vE '^(scripts/scan-pii\.sh|package-lock\.json|web/package-lock\.json)$')

# --- Layer 1a: QBO production realm IDs (16 digits, 9341 prefix) -------------
hits=$(echo "$FILES" | xargs grep -nE '9341[0-9]{12}' 2>/dev/null || true)
if [ -n "$hits" ]; then
  echo "❌ pii scan: QuickBooks realm ID(s) in the tree:"
  echo "$hits" | head -10
  fail=1
fi

# --- Layer 1b: emails outside the allowlist ----------------------------------
ALLOW='example\.(com|ca|org)|accountingqb\.com|vasperacapital\.com|anthropic\.com|users\.noreply\.github\.com|intuit\.com|company\.com|acmeconsulting\.com|acme\.com|techstart\.io|greenvalley\.com|metrolegal\.com|sunrisehc\.org|blueocean\.media'
hits=$(echo "$FILES" | xargs grep -hnoE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' 2>/dev/null \
  | grep -viE "@($ALLOW)" \
  | grep -vE ':[a-z]{1,2}@[a-z]{1,2}\.(com|ca|org)$' || true)
if [ -n "$hits" ]; then
  echo "❌ pii scan: email address(es) at non-allowlisted domains:"
  echo "$hits" | head -10
  fail=1
fi

# --- Layer 2: the customer-identifier blocklist (secret) ---------------------
BLOCKLIST="${PII_BLOCKLIST:-}"
if [ -z "$BLOCKLIST" ] && [ -f .pii-blocklist ]; then
  BLOCKLIST=$(tr '\n' '|' < .pii-blocklist | sed 's/|*$//')
fi
if [ -n "$BLOCKLIST" ]; then
  hits=$(echo "$FILES" | xargs grep -inE "$BLOCKLIST" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "❌ pii scan: customer identifier(s) from the blocklist found:"
    echo "$hits" | sed -E 's/(.{120}).*/\1/' | head -10
    fail=1
  fi
else
  echo "⚠️  pii scan: no PII_BLOCKLIST set — generic rules only"
fi

if [ "$fail" -eq 1 ]; then
  echo ""
  echo "Fictionalize before committing: customer/client names, realm IDs, and"
  echo "books data (vendors, classes, txn IDs) must never enter this public repo."
  exit 1
fi
echo "✅ pii scan clean"
