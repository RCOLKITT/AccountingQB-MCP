#!/usr/bin/env bash
# One-shot go-live script for the AccountingQB remote MCP connector.
#
# Run this LOCALLY where `doppler` and `flyctl` are authenticated:
#   bash scripts/setup-connector-env.sh
#
# It performs, in the correct order:
#   1. Generates MCP_JWT_SECRET once and sets it in Doppler (Vercel config)
#      AND as a Fly secret — they must be identical.
#   2. Sets MCP_RESOURCE_URL in Doppler.
#   3. Deploys the Fly app and waits for /healthz.
#   4. Only THEN sets NEXT_PUBLIC_REMOTE_MCP_URL (this is the switch that
#      makes the "Connect instantly" card appear in the setup wizard) and
#      reminds you to redeploy Vercel — NEXT_PUBLIC_* vars are inlined at
#      build time, so a redeploy is required.
#
# Nothing secret is ever printed.
set -euo pipefail

MCP_HOST="mcp.accountingqb.com"
MCP_URL="https://${MCP_HOST}"
FLY_APP="accountingqb-mcp"

command -v doppler >/dev/null || { echo "doppler CLI not found — https://docs.doppler.com/docs/install-cli"; exit 1; }
command -v flyctl  >/dev/null || command -v fly >/dev/null || { echo "flyctl not found — https://fly.io/docs/flyctl/install/"; exit 1; }
FLY=$(command -v flyctl || command -v fly)

read -rp "Doppler project for the web app (e.g. accountingqb): " DP_PROJECT
read -rp "Doppler config synced to Vercel production (e.g. prd): " DP_CONFIG

echo "==> 1/5 Generating MCP_JWT_SECRET (shared by Vercel + Fly)"
SECRET=$(openssl rand -base64 48)

echo "==> 2/5 Setting Doppler secrets (${DP_PROJECT}/${DP_CONFIG})"
doppler secrets set --project "$DP_PROJECT" --config "$DP_CONFIG" --silent \
  MCP_JWT_SECRET="$SECRET" \
  MCP_RESOURCE_URL="$MCP_URL"

echo "==> 3/5 Creating/deploying Fly app '${FLY_APP}'"
"$FLY" apps list | grep -q "$FLY_APP" || "$FLY" apps create "$FLY_APP"
"$FLY" secrets set --app "$FLY_APP" --stage MCP_JWT_SECRET="$SECRET"
"$FLY" deploy --config remote/fly.toml --dockerfile remote/Dockerfile --app "$FLY_APP"

echo "==> 4/5 Certificate + DNS for ${MCP_HOST}"
"$FLY" certs create "$MCP_HOST" --app "$FLY_APP" || true
echo    "    Add the DNS record your registrar needs (usually CNAME ${MCP_HOST} -> ${FLY_APP}.fly.dev),"
echo    "    then verify: ${FLY} certs check ${MCP_HOST} --app ${FLY_APP}"

echo "==> Waiting for /healthz (up to 90s)..."
for i in $(seq 1 18); do
  if curl -fsS "https://${FLY_APP}.fly.dev/healthz" >/dev/null 2>&1; then HEALTHY=1; break; fi
  sleep 5
done
[ "${HEALTHY:-0}" = "1" ] && echo "    healthz OK" || { echo "    healthz not responding yet — check '${FLY} logs --app ${FLY_APP}' before continuing"; exit 1; }

echo "==> 5/5 Flipping the wizard switch (NEXT_PUBLIC_REMOTE_MCP_URL)"
doppler secrets set --project "$DP_PROJECT" --config "$DP_CONFIG" --silent \
  NEXT_PUBLIC_REMOTE_MCP_URL="${MCP_URL}/mcp"

cat <<DONE

Done. Final manual steps:
  1. Redeploy Vercel (NEXT_PUBLIC_* is baked at build time):
       Vercel dashboard -> accounting-qb-mcp -> Redeploy latest,
       or push any commit to main.
  2. Once DNS resolves, smoke-test the connector end to end:
       claude.ai -> Settings -> Connectors -> Add custom connector
       -> ${MCP_URL}/mcp  -> complete the OAuth sign-in.
  3. Optional but recommended while you're in Doppler:
       - NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION=<GSC HTML-tag token>
       - Add Clerk publishable key to the PREVIEW scope (fixes red branch builds)
DONE
