# accountingqb-local — Door 2 shim (Phase 2a)

A **localhost-only** HTTP server that wraps the AccountingQB MCP connector so the product
can run as a **downloadable local app** rendered in the browser, without depending on the
Cowork bridge. This is the "second door" (Door 1 = Claude Desktop / Cowork; both stay).

Ported from the sibling repo `Hearth` (`hearth-local/serve.js`); Python here because the
connector is Python/FastMCP.

## Run (dev)

```bash
python accountingqb-local/serve.py
# → http://127.0.0.1:8788  (auto-opens your browser)
```

Env:
- `ACCOUNTINGQB_PORT` / `PORT` — fixed port (default: first free of 8788/8789/8790).
- `ACCOUNTINGQB_DATA_DIR` — config/token dir (default `~/.accountingqb`).
- `ACCOUNTINGQB_NO_OPEN=1` — don't auto-open the browser (used by the Tauri sidecar).
- `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` — BYO-key chat (or set the key in the UI).
- Connector `QB_*` vars pass through unchanged.

## Endpoints

| Route | Purpose |
|-------|---------|
| `GET /` | Minimal status shell (Phase 2b replaces with tabbed Chat + Dashboard) |
| `GET /healthz` | Liveness (the Tauri shell polls this before opening the window) |
| `GET /api/status` | version, tool count, connected?, hasAnthropicKey, realmId |
| `GET /api/tools` | list of tool names + one-line descriptions |
| `POST /api/config` | persist Anthropic key / Intuit creds / license locally |
| `POST /mcp` | `{tool, args}` → invoke a connector tool **in-process** → `{ok, result}` |
| `POST /sample` | BYO-key Claude relay (`{system, messages}`) — **no proxy** |
| `GET /oauth/start` → `GET /callback` | Connect QuickBooks |

## Security (matches the local-first invariant)

- Binds **127.0.0.1 only**, with a Host allowlist (`127.0.0.1`/`localhost`) and Origin
  allowlist (`+tauri.localhost`) — defeats DNS-rebinding and cross-site POSTs.
- The Anthropic key lives only in `~/.accountingqb`; chat calls go **machine → Anthropic**
  directly. Nothing AI-related touches our servers.
- Book data flows QuickBooks → your machine via the connector, exactly as in Door 1.

## QuickBooks connection modes

- **Hosted broker (default, low-friction):** no Intuit developer app needed. `/oauth/start`
  hands off to the AccountingQB web connect flow; the connector runs in hosted mode.
- **Local (BYO Intuit app, max-local):** set `QB_CLIENT_ID`/`QB_CLIENT_SECRET` (or save them
  in the UI). `/oauth/start` runs a loopback consent and `/callback` exchanges the code for a
  refresh token, encrypted to `~/.accountingqb`. Register `http://localhost:<PORT>/callback`
  as a redirect URI in your Intuit app.

## What's next

- **Phase 2b** — replace `GET /` with the tabbed Chat + Dashboard artifact (shared with the
  Cowork plugin), wiring the Chat tab to `/mcp` + `/sample` and the Dashboard to `/mcp`.
- **Phase 2c** — a signed Tauri desktop app that spawns this shim as a **PyInstaller** sidecar
  (Apple notarize + Azure sign, reusing Hearth's release CI).
