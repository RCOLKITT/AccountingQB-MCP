#!/usr/bin/env bash
# Deploy the remote connector to Fly, then VERIFY it end-to-end before declaring
# success — the deploy is not "done" until the live host serves the released
# version and self-identifies as the hosted connector through the authenticated
# MCP path. This is the gate that closes the deployment-mode / version-drift class
# of bug (P3 recurred six times because nothing verified the live build).
#
# Usage:  ./scripts/deploy.sh            # deploy + smoke-gate the connector
#         SKIP_DEPLOY=1 ./scripts/deploy.sh   # smoke-only (verify current live)
#
# Requires: flyctl (authed), doppler (project accountingqb-mcp, config prd — it
# injects MCP_JWT_SECRET for the authenticated qb_server_info check).
set -euo pipefail
cd "$(dirname "$0")/.."

EXPECT="$(grep -m1 '^version' mcpb/pyproject.toml | sed 's/.*"\(.*\)".*/\1/')"

if [[ "${SKIP_DEPLOY:-0}" != "1" ]]; then
  echo "▶ Deploying connector v${EXPECT} to Fly…"
  fly deploy --config remote/fly.toml --dockerfile remote/Dockerfile --now
else
  echo "▶ SKIP_DEPLOY=1 — smoke-checking the current live connector (expecting v${EXPECT})"
fi

echo "▶ Waiting for the connector to come up…"
# Retry the smoke test: a fresh machine can take a few seconds to serve /version.
# Fail the deploy if it never comes up matching the released version.
attempt=0
until doppler run -p accountingqb-mcp -c prd -- \
        python3 scripts/deploy-smoke.py --expect-version "$EXPECT"; do
  attempt=$((attempt + 1))
  if [[ $attempt -ge 5 ]]; then
    echo "❌ Deploy smoke test failed after ${attempt} attempts — the live connector"
    echo "   does not match v${EXPECT}. Investigate before considering this deployed."
    exit 1
  fi
  echo "  … smoke not green yet (attempt ${attempt}/5) — retrying in 6s"
  sleep 6
done

echo "✅ Connector v${EXPECT} deployed and verified live."
