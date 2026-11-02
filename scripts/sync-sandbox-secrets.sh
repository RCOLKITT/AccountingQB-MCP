#!/usr/bin/env bash
# Sync the sandbox-canary credentials from Doppler (source of truth) to GitHub
# Actions secrets, then fire the first sandbox-canary run.
#
# Flow: the owner fills the four SANDBOX_* values in Doppler (project
# accountingqb-mcp, config dev) from the Intuit developer portal —
# Development keys + OAuth 2.0 Playground refresh token/realm — then runs:
#
#   bash scripts/sync-sandbox-secrets.sh
#
# Refuses to sync placeholders (values seeded as PENDING_*), so running it
# early is harmless.
set -euo pipefail

PROJECT=accountingqb-mcp
CONFIG=dev
NAMES=(SANDBOX_QB_CLIENT_ID SANDBOX_QB_CLIENT_SECRET SANDBOX_REALM_ID SANDBOX_REFRESH_TOKEN)

for name in "${NAMES[@]}"; do
  value="$(doppler secrets get "$name" --project "$PROJECT" --config "$CONFIG" --plain)"
  if [ -z "$value" ] || [[ "$value" == PENDING_* ]]; then
    echo "✗ $name is still a placeholder in Doppler ($PROJECT/$CONFIG) — fill it first."
    exit 1
  fi
  printf '%s' "$value" | gh secret set "$name"
  echo "✓ $name synced to GitHub secrets"
done

echo "→ dispatching the first sandbox-canary run…"
gh workflow run sandbox-canary.yml
echo "Watch it: gh run watch \$(gh run list --workflow=sandbox-canary.yml --limit 1 --json databaseId -q '.[0].databaseId')"
