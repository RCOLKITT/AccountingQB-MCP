#!/usr/bin/env bash
# Theater scan (VASPERA-SPINE §3): no mocks/stubs/fakes/placeholders in production paths.
#
# A hit is allowed only when it is one of:
#   - inside a test file (tests are supposed to mock),
#   - a UI input placeholder — Tailwind `placeholder-*` / `placeholder:` or HTML `placeholder=`
#     (that's a different meaning of the word: a form-field hint, not fake data),
#   - the DECLARED demo mode — canned QuickBooks data served to reviewers who don't have a
#     QuickBooks connection. It is flag-gated (`_demo_active`), logs "DEMO MODE" to the user, and
#     is documented in the README. Its canned data is a labeled feature, not hidden theater.
#   - explicitly annotated `SAFE:` with a justification.
#
# Anything else — a new mock/stub/fake/dummy sneaking into a real code path — fails the gate.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

hits=$(grep -rInE "\b(mock|stub|placeholder|fake|dummy)\b" \
        --include=*.py --include=*.ts --include=*.tsx --include=*.js \
        mcpb/src accountingqb-local web/src scripts 2>/dev/null \
      | grep -viE "/tests?/|test_|\.test\.|\.spec\.|__tests__" \
      | grep -viE "placeholder[-=:]" \
      | grep -viE "demo[ _-]?mode|demo:|_demo_active|DEMO_|demo fallback|demo data|demo company" \
      | grep -vF "SAFE:" || true)

if [ -n "$hits" ]; then
  echo "❌ theater scan: unannotated mock/stub/fake/placeholder/dummy in a production path:"
  echo "$hits"
  echo
  echo "Remove it, or if it is legitimate annotate the line with 'SAFE: <why>'."
  exit 1
fi
echo "✅ theater scan clean"
