# AccountingQB Remote MCP Service

Stateless streamable-HTTP MCP server at `https://mcp.accountingqb.com/mcp`,
serving the same tool surface as the local extension. Authentication is a
15-minute HS256 JWT minted by the OAuth 2.1 authorization server built into
the Next.js app at `https://accountingqb.com` (see `web/src/app/api/oauth2/`).

Source: `mcpb/src/accountingqb/remote.py` (entry: `python -m accountingqb.remote`).

## Endpoints

| Path | Auth | Purpose |
|------|------|---------|
| `POST /mcp` | Bearer JWT | MCP streamable HTTP (stateless, JSON responses) |
| `GET /.well-known/oauth-protected-resource` | none | RFC 9728 metadata pointing at the authorization server |
| `GET /healthz` | none | Liveness/health check |

## Environment

| Var | Default | Notes |
|-----|---------|-------|
| `MCP_JWT_SECRET` | (required) | Shared HS256 secret; must equal the web app's `MCP_JWT_SECRET` |
| `RESOURCE_URL` | `https://mcp.accountingqb.com` | JWT audience + RFC 9728 `resource` |
| `AS_URL` | `https://accountingqb.com` | Advertised authorization server |
| `QB_API_URL` | `https://accountingqb.com` | Token broker + default-realm lookup |
| `PORT` | `8000` | uvicorn bind port |

## Deploy (Fly.io)

```bash
# 1. First-time launch (reuses this fly.toml; run from the repo root)
cd remote
fly launch --copy-config --no-deploy   # creates the app "accountingqb-mcp"

# 2. Secrets (generate one secret and set the SAME value in Vercel for web/)
fly secrets set MCP_JWT_SECRET="$(openssl rand -hex 32)"
fly secrets set QB_API_URL="https://accountingqb.com"

# 3. Deploy (from the repo root so the Docker build context includes mcpb/)
cd ..
fly deploy --config remote/fly.toml --dockerfile remote/Dockerfile

# 4. DNS + TLS cert
fly certs add mcp.accountingqb.com
# Then create a CNAME:  mcp.accountingqb.com -> accountingqb-mcp.fly.dev

# 5. Smoke test
curl https://mcp.accountingqb.com/healthz                              # -> ok
curl https://mcp.accountingqb.com/.well-known/oauth-protected-resource # -> JSON
curl -i -X POST https://mcp.accountingqb.com/mcp                       # -> 401 + WWW-Authenticate
```

Prerequisites on the web side (Vercel):

1. Apply `web/migrations/2026-07-mcp-oauth.sql` in Supabase.
2. Set `MCP_JWT_SECRET` (same value as above) and `MCP_RESOURCE_URL=https://mcp.accountingqb.com`.
3. Set `NEXT_PUBLIC_REMOTE_MCP_URL=https://mcp.accountingqb.com/mcp` to surface
   the "Connect instantly" option in the setup wizard.

## Claude directory submission

Once deployed and smoke-tested, submit the connector to the Claude directory:
https://docs.claude.com/en/docs/agents-and-tools/remote-mcp-servers — the
server already satisfies the requirements (OAuth 2.1 + PKCE + dynamic client
registration via `/.well-known/oauth-protected-resource` discovery, stateless
streamable HTTP, HTTPS-only). Include the connector URL
`https://mcp.accountingqb.com/mcp` in the submission form.
