#!/usr/bin/env bash
# Fail the build if tracked files contain a secret or a live QuickBooks realm id.
# The realm-id-in-a-public-doc leak that motivated this is exactly the class of
# thing code review misses. Runs in CI (.github/workflows/tests.yml). Curated for
# high confidence + low false positives; extend the scans as the surface grows.
# Uses `git grep` (tracked files only, portable).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1

# Exclude this scanner, lockfiles, and the placeholder env file from scanning.
EXCLUDES=(':!scripts/scan-secrets.sh' ':!*package-lock.json' ':!web/.env.example')
# tests/ legitimately carry synthetic realm-id / JWT-shaped fixtures; secrets
# (live keys, private-key blocks) are still scanned there.
NO_FIXTURES=("${EXCLUDES[@]}" ':!tests/*')

fail=0
scan() {  # label  regex  [extra pathspec excludes...]
  local label="$1" re="$2"; shift 2
  local hits
  hits=$(git grep -nEI "$re" -- "$@" 2>/dev/null)
  if [ -n "$hits" ]; then
    echo "❌ potential ${label}:"
    echo "$hits"
    echo
    fail=1
  fi
}

scan "Stripe live secret key"  'sk_live_[0-9A-Za-z]{10,}'                                   "${EXCLUDES[@]}"
scan "private key block"       'BEGIN[A-Z ]*PRIVATE KEY'                                    "${EXCLUDES[@]}"
scan "QuickBooks realm id"     'realm[_ ]?id[^0-9]{0,16}[0-9]{15,16}'                       "${NO_FIXTURES[@]}"
scan "Supabase/JWT secret"     'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}' "${NO_FIXTURES[@]}"

if [ "$fail" -ne 0 ]; then
  echo "Secret scan FAILED — move internal docs to private-docs/ (gitignored)"
  echo "and rotate any real secret that was committed."
  exit 1
fi
echo "✅ secret scan clean"
