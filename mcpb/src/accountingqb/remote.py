"""Remote (multi-tenant) MCP service for AccountingQB.

Serves the same FastMCP tool surface as the local extension over stateless
streamable HTTP at ``https://mcp.accountingqb.com/mcp``.

Architecture
------------
* **Transport**: ``mcp.streamable_http_app()`` with ``stateless_http=True``
  and ``json_response=True`` — every HTTP request is self-contained, so the
  service scales horizontally with no session affinity.
* **AuthN**: each ``/mcp`` request must carry ``Authorization: Bearer <jwt>``.
  The JWT is a short-lived (15 min) HS256 token minted by the AccountingQB
  authorization server (the Next.js app at https://accountingqb.com, see
  ``web/src/app/api/oauth2/token/route.ts``) and verified locally with the
  shared secret ``MCP_JWT_SECRET``. Claims: ``license_key``, ``sub`` (Clerk
  user id), ``aud`` (must equal ``RESOURCE_URL``), ``exp``.
* **Discovery**: ``GET /.well-known/oauth-protected-resource`` (RFC 9728)
  points MCP clients at the authorization server; 401 responses carry a
  ``WWW-Authenticate: Bearer resource_metadata="..."`` challenge so clients
  can bootstrap the OAuth flow.
* **Tenancy**: per request we build a fresh ``QBContext`` (``persist_tokens=
  False`` so nothing is ever written to local disk, ``hosted_mode=True`` so
  QuickBooks tokens are brokered by POST {QB_API_URL}/api/oauth/token) and
  install it with ``context.set_ctx()`` for the duration of the request.
  ``ContextVar`` values are task-local and the MCP session task is spawned
  from within the request task, so concurrent tenants are fully isolated.

NOTE / required hook in server.py
---------------------------------
``get_access_token()`` in ``accountingqb.server`` already talks to the broker
in hosted mode, but it currently reads the *module-level* ``LICENSE_KEY``
constant (seeded from ``QB_LICENSE_KEY`` at import time) instead of a
per-context value. This module sets ``ctx.license_key`` on every per-request
context; ``server.get_access_token()`` (and ``_fetch_hosted_tokens``) must be
updated to prefer ``getattr(ctx, "license_key", "") or LICENSE_KEY`` for
multi-tenant token brokering to work. Until that hook lands, all remote
requests would broker with the process-wide QB_LICENSE_KEY (i.e. remote mode
is not multi-tenant yet). See the Phase 6 report.

Default realm
-------------
The active company for a license is looked up (with a ~45 min in-process TTL
cache) from ``GET {QB_API_URL}/api/license/default-realm?license_key=...``.
When unset/unreachable we leave ``ctx.realm_id`` empty and
``get_access_token()`` falls back to the first connected company — matching
the local extension's historic behavior.

Running
-------
    MCP_JWT_SECRET=... python -m accountingqb.remote     # uvicorn on $PORT (8000)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Awaitable, Callable, Optional

import httpx
import jwt as pyjwt

from accountingqb.context import QBContext, reset_ctx, set_ctx

logger = logging.getLogger("accountingqb.remote")

# ---------------------------------------------------------------------------
# Configuration (env)
# ---------------------------------------------------------------------------
RESOURCE_URL = os.environ.get("RESOURCE_URL", "https://mcp.accountingqb.com")
AS_URL = os.environ.get("AS_URL", "https://accountingqb.com")
MCP_JWT_SECRET = os.environ.get("MCP_JWT_SECRET", "")
QB_API_URL = os.environ.get("QB_API_URL", "https://accountingqb.com")

# Success-TTL for the per-license default-realm + read-only cache. This is a
# BURST ABSORBER, not a freshness policy: the realm is resolved once per MCP
# request (middleware pins it into the request context), and this TTL only
# coalesces same-moment requests into one broker GET. It must stay TINY — a
# company switch persists the new realm to the broker, but with >1 warm machine
# only the machine that served the switch gets the write-through; every OTHER
# machine serves the OLD company until its cache expires. At 60s that meant a
# user who switched and immediately asked a question got the previous company's
# numbers (observed live, 2026-10-30: three switch retries, wrong-company
# responses for 40–65s). 2s makes the cross-machine window shorter than any
# human (or model) round-trip.
DEFAULT_REALM_TTL_SECONDS = 2.0

# When the broker lookup FAILS, serve the last-known realm/read-only values and
# don't retry for this long — a down broker must not become a per-request hot
# loop, and stale-but-real values beat resetting to None/False (the old code
# cached read_only=False on failure, silently disabling read-only protection
# for the TTL).
REALM_FAILURE_BACKOFF_SECONDS = 30.0

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"

# --- 2026-07-28 MCP spec adoption (edge layer) -----------------------------
# We are already stateless (streamable-HTTP, no session affinity) and use NONE
# of the deprecated features (Roots/Sampling/Logging — SEP-2577), so the 12-month
# deprecation clock does not touch us. This edge layer advertises spec-currency
# and adds the two client-visible 2026-07-28 affordances without an SDK change:
#   * cacheable tools/list results (ttlMs/cacheScope — SEP-2549), and
#   * MCP-Protocol-Version advertising + a capability-discovery endpoint.
# Header-based routing (Mcp-Method/Mcp-Name — SEP-2243) needs nothing here: the
# transport already accepts arbitrary request headers, so any load balancer can
# route/meter on them. Full protocol compliance (no-initialize, native
# server/discover) lands when FastMCP 4.0 leaves beta.
SPEC_PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_PROTOCOL_VERSIONS = ["2026-07-28", "2025-11-25", "2025-06-18"]
# tools/list changes only on deploy, so it is safely cacheable for a while.
TOOLS_LIST_TTL_MS = 60 * 60 * 1000  # 1 hour
MCP_CAPABILITIES_PATH = "/.well-known/mcp-capabilities"


def _augment_tools_list(body: bytes) -> bytes:
    """Inject ttlMs/cacheScope into a JSON-RPC tools/list result (SEP-2549).

    Only touches a response whose ``result`` carries a ``tools`` array — every
    other response is returned byte-for-byte. Forward-compatible: pre-2026-07-28
    clients ignore the extra fields."""
    try:
        obj = json.loads(body)
    except (ValueError, TypeError):
        return body

    # Read-only mode (client-selected): hide every write tool from tools/list so
    # Claude only ever sees reports. Defense-in-depth — server-side gating still
    # refuses a write even if one were called directly (server._apply_readonly_gating).
    read_only = False
    try:
        from .context import get_ctx  # noqa: PLC0415

        read_only = bool(getattr(get_ctx(), "read_only", False))
    except Exception:
        read_only = False

    changed = False

    def _aug(o: object) -> None:
        nonlocal changed
        if isinstance(o, dict):
            res = o.get("result")
            if isinstance(res, dict) and isinstance(res.get("tools"), list):
                if read_only:
                    from accountingqb import server as _srv  # noqa: PLC0415

                    allow = _srv.READ_ONLY_TOOLS
                    res["tools"] = [
                        t
                        for t in res["tools"]
                        if isinstance(t, dict) and t.get("name") in allow
                    ]
                    changed = True
                res.setdefault("ttlMs", TOOLS_LIST_TTL_MS)
                res.setdefault("cacheScope", "public")
                changed = True

    if isinstance(obj, list):
        for o in obj:
            _aug(o)
    else:
        _aug(obj)

    if not changed:
        return body
    return json.dumps(obj, separators=(",", ":")).encode()


# ---------------------------------------------------------------------------
# Default-realm TTL cache
# ---------------------------------------------------------------------------
class DefaultRealmCache:
    """Near-fresh resolver: license_key -> (default realm id, read-only flag).

    Backed by ``GET {QB_API_URL}/api/license/default-realm?license_key=...``
    (see web/src/app/api/license/default-realm/route.ts). Semantics:

    * SUCCESS is cached only for a tiny burst window (``ttl``, ~2s) — each MCP
      request effectively resolves the realm fresh, so a company switch takes
      effect on the user's next request on EVERY machine, not just the one that
      served the switch (the 60s TTL made switching look broken cross-machine).
    * FAILURE serves the LAST-KNOWN values and backs off (``failure_backoff``)
      — a down broker never hot-loops, and never resets read_only to False
      (that would silently disable read-only protection) or the realm to None.
    * ``get_access_token()`` falls back to the first connected company when the
      resolved realm is empty.
    """

    def __init__(
        self,
        api_url: str = QB_API_URL,
        ttl: float = DEFAULT_REALM_TTL_SECONDS,
        failure_backoff: float = REALM_FAILURE_BACKOFF_SECONDS,
    ):
        self._api_url = api_url.rstrip("/")
        self._ttl = ttl
        self._backoff = failure_backoff
        # license_key -> (ts, realm, read_only, fetch_ok)
        self._cache: dict[str, tuple[float, Optional[str], bool, bool]] = {}

    async def _fetch(self, license_key: str) -> tuple[Optional[str], bool, bool]:
        """One broker call fetching BOTH the default realm and the read-only
        flag. Returns (realm, read_only, ok) — ok=False on any network error or
        non-200, so the caller can keep last-known values instead."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._api_url}/api/license/default-realm",
                    params={"license_key": license_key},
                )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("realmId") or None, bool(data.get("readOnly")), True
            logger.warning("default-realm lookup HTTP %s", resp.status_code)
        except Exception as exc:  # network errors are non-fatal
            logger.warning("default-realm lookup failed: %s", exc)
        return None, False, False

    async def _resolve(self, license_key: str) -> tuple[Optional[str], bool]:
        now = time.monotonic()
        hit = self._cache.get(license_key)
        if hit:
            age = now - hit[0]
            window = self._ttl if hit[3] else self._backoff
            if age < window:
                return hit[1], hit[2]

        realm, read_only, ok = await self._fetch(license_key)
        if ok:
            self._cache[license_key] = (now, realm, read_only, True)
            return realm, read_only

        # Fetch failed: keep serving the last-known values (stale beats wrong —
        # especially read_only, which must not fail open) and start the backoff.
        prev_realm = hit[1] if hit else None
        prev_read_only = hit[2] if hit else False
        self._cache[license_key] = (now, prev_realm, prev_read_only, False)
        return prev_realm, prev_read_only

    async def get(self, license_key: str) -> Optional[str]:
        realm, _ = await self._resolve(license_key)
        return realm

    async def read_only(self, license_key: str) -> bool:
        _, read_only = await self._resolve(license_key)
        return read_only

    def invalidate(self, license_key: str) -> None:
        self._cache.pop(license_key, None)

    def set_realm(self, license_key: str, realm_id: Optional[str]) -> None:
        """Write-through after a company switch: update this process's cache to
        the new realm immediately (preserving the cached read-only flag) so the
        next request on THIS machine resumes on the switched-to company. Other
        machines re-resolve within the (tiny) success TTL."""
        prev = self._cache.get(license_key)
        read_only = prev[2] if prev else False
        self._cache[license_key] = (time.monotonic(), realm_id, read_only, True)


_default_realm_cache = DefaultRealmCache()


async def _resolve_default_realm(license_key: str) -> Optional[str]:
    return await _default_realm_cache.get(license_key)


def note_default_realm(license_key: str, realm_id: Optional[str]) -> None:
    """Called by qb_switch_company (remote mode) right after it persists the new
    active company, so this connector process reflects the switch on the next
    request instead of serving the stale cached realm for the full TTL."""
    _default_realm_cache.set_realm(license_key, realm_id)


async def _resolve_read_only(license_key: str) -> bool:
    return await _default_realm_cache.read_only(license_key)


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------
# Pure-ASGI (not BaseHTTPMiddleware) so contextvars set here are visible to
# the downstream app *in the same task* — required for set_ctx()/reset_ctx()
# to scope the QBContext to exactly this request.
class BearerAuthMiddleware:
    """Handles /healthz, RFC 9728 metadata, and Bearer-JWT auth for /mcp.

    Any HTTP request other than the two public paths must present a valid
    HS256 JWT. On success a fresh, non-persisting hosted-mode ``QBContext``
    is installed for the duration of the request.
    """

    def __init__(
        self,
        app,
        *,
        jwt_secret: str,
        resource_url: str = RESOURCE_URL,
        auth_server_url: str = AS_URL,
        realm_resolver: Optional[
            Callable[[str], Awaitable[Optional[str]]]
        ] = _resolve_default_realm,
        read_only_resolver: Optional[
            Callable[[str], Awaitable[bool]]
        ] = _resolve_read_only,
        version: str = "",
        tool_count: int = 0,
        tax_data: Optional[dict] = None,
    ):
        self.app = app
        self.jwt_secret = jwt_secret
        self.resource_url = resource_url.rstrip("/")
        self.auth_server_url = auth_server_url.rstrip("/")
        self.realm_resolver = realm_resolver
        self.read_only_resolver = read_only_resolver
        self.version = version
        self.tool_count = tool_count
        self.tax_data = tax_data or {}

    # -- small ASGI response helpers (no Starlette Response objects needed,
    # but plain dict sends keep this middleware dependency-light) ----------
    async def _send_response(
        self, send, status: int, body: bytes, content_type: str, extra_headers=()
    ) -> None:
        headers = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
            *extra_headers,
        ]
        await send(
            {"type": "http.response.start", "status": status, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body})

    async def _send_401(self, send, description: str) -> None:
        challenge = (
            f'Bearer resource_metadata="{self.resource_url}'
            f'{PROTECTED_RESOURCE_PATH}", error="invalid_token"'
        )
        body = json.dumps(
            {"error": "invalid_token", "error_description": description}
        ).encode()
        await self._send_response(
            send,
            401,
            body,
            "application/json",
            extra_headers=[(b"www-authenticate", challenge.encode())],
        )

    def _verify_bearer(self, scope) -> dict:
        """Return verified JWT claims or raise ValueError with a description."""
        auth = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                auth = value.decode("latin-1")
                break
        if not auth:
            raise ValueError("Missing Authorization header")
        parts = auth.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Authorization header must be 'Bearer <token>'")
        if not self.jwt_secret:
            # Fail closed: a deployment without MCP_JWT_SECRET must not
            # accept any token.
            raise ValueError("Server is not configured for token verification")
        try:
            claims = pyjwt.decode(
                parts[1],
                self.jwt_secret,
                algorithms=["HS256"],
                audience=self.resource_url,
                options={"require": ["exp", "aud"]},
            )
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except pyjwt.InvalidAudienceError:
            raise ValueError("Token audience mismatch")
        except pyjwt.PyJWTError as exc:
            raise ValueError(f"Invalid token: {exc}")
        if not claims.get("license_key"):
            raise ValueError("Token is missing the license_key claim")
        return claims

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # lifespan / websocket: pass straight through
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path == "/healthz":
            await self._send_response(send, 200, b"ok", "text/plain")
            return

        if path == "/version":
            # Public deploy-verification endpoint: lets a smoke test confirm the
            # LIVE build matches the released tag (and that it self-identifies as
            # the hosted connector) without a JWT — catches stale/failed deploys
            # and the deployment-mode class of bug in one unauthenticated call.
            body = json.dumps(
                {
                    "version": self.version,
                    "tools": self.tool_count,
                    "deployment": "hosted connector (token-brokered)",
                }
            ).encode()
            await self._send_response(send, 200, body, "application/json")
            return

        if path == "/tax-data":
            # Public tax-data provenance (version, ledger status, per-table sources,
            # concrete highlights) — statutory facts only, no taxpayer data. Built
            # from the live registry so it can't drift; powers the marketing site's
            # provenance card. Cacheable.
            headers = [(b"cache-control", b"public, max-age=600")]
            body = json.dumps(self.tax_data).encode()
            await self._send_response(
                send, 200, body, "application/json", extra_headers=headers
            )
            return

        if path == PROTECTED_RESOURCE_PATH:
            body = json.dumps(
                {
                    "resource": self.resource_url,
                    "authorization_servers": [self.auth_server_url],
                    "bearer_methods_supported": ["header"],
                }
            ).encode()
            await self._send_response(send, 200, body, "application/json")
            return

        if path == MCP_CAPABILITIES_PATH:
            # Public capability discovery: advertise 2026-07-28 spec-currency,
            # the stateless transport, cacheable tools/list, and — notably — that
            # we use zero deprecated features.
            body = json.dumps(
                {
                    "protocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
                    "capabilities": {"tools": {"listChanged": False}},
                    "deprecatedFeaturesUsed": [],
                    "transport": {"type": "streamable-http", "stateless": True},
                    "cacheable": {
                        "tools/list": {
                            "ttlMs": TOOLS_LIST_TTL_MS,
                            "cacheScope": "public",
                        }
                    },
                    "headerRouting": {
                        "supported": True,
                        "headers": ["Mcp-Method", "Mcp-Name"],
                    },
                }
            ).encode()
            await self._send_response(send, 200, body, "application/json")
            return

        # Everything else (/mcp and any future endpoint) requires a Bearer JWT.
        try:
            claims = self._verify_bearer(scope)
        except ValueError as exc:
            await self._send_401(send, str(exc))
            return

        license_key = claims["license_key"]

        realm_id: Optional[str] = None
        if self.realm_resolver is not None:
            try:
                realm_id = await self.realm_resolver(license_key)
            except Exception as exc:  # never fail the request on realm lookup
                logger.warning("realm resolver failed: %s", exc)

        # Fresh per-request tenant context. persist_tokens=False: the remote
        # host must never write tenant tokens to its local disk.
        # Client-selected read-only mode (licenses.read_only), resolved per request
        # (cached with the realm — one broker call). Server-side gating refuses every
        # write tool when this is set; tools/list is filtered to read tools too.
        read_only = False
        if self.read_only_resolver is not None:
            try:
                read_only = bool(await self.read_only_resolver(license_key))
            except Exception as exc:  # never fail the request on this lookup
                logger.warning("read-only lookup failed: %s", exc)

        ctx = QBContext(persist_tokens=False, hosted_mode=True)
        ctx.realm_id = realm_id or ""
        ctx.license_key = license_key
        ctx.read_only = read_only
        ctx.user_id = claims.get("sub", "")  # type: ignore[attr-defined]

        token = set_ctx(ctx)
        try:
            await self.app(scope, receive, self._augmenting_send(send))
        finally:
            reset_ctx(token)

    def _augmenting_send(self, send):
        """Wrap the downstream ASGI send to (1) advertise the 2026-07-28
        protocol version on every response and (2) inject ttlMs/cacheScope into
        a JSON tools/list result. JSON responses are buffered so content-length
        stays correct; streaming (SSE) responses pass straight through."""
        state = {"start": None, "json": False, "passthrough": False, "body": b""}

        async def wrapped(message):
            mtype = message["type"]
            if mtype == "http.response.start":
                headers = list(message.get("headers") or [])
                ctype = b""
                for k, v in headers:
                    if k.lower() == b"content-type":
                        ctype = v
                        break
                if b"application/json" in ctype:
                    state["json"] = True
                    state["start"] = message
                else:
                    # Non-JSON / streaming: forward now, just add the version header.
                    state["passthrough"] = True
                    headers.append(
                        (b"mcp-protocol-version", SPEC_PROTOCOL_VERSION.encode())
                    )
                    await send({**message, "headers": headers})
                return

            if mtype == "http.response.body":
                if state["passthrough"]:
                    await send(message)
                    return
                state["body"] += message.get("body", b"")
                if message.get("more_body"):
                    return
                body = _augment_tools_list(state["body"])
                start = state["start"]
                new_headers = [
                    (k, v)
                    for (k, v) in start.get("headers") or []
                    if k.lower() != b"content-length"
                ]
                new_headers.append((b"content-length", str(len(body)).encode()))
                new_headers.append(
                    (b"mcp-protocol-version", SPEC_PROTOCOL_VERSION.encode())
                )
                await send({**start, "headers": new_headers})
                await send(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )
                return

            await send(message)

        return wrapped


# ---------------------------------------------------------------------------
# App assembly
# ---------------------------------------------------------------------------
def create_app():
    """Build the ASGI app: auth middleware wrapping the stateless MCP app.

    Imported lazily so tests can exercise BearerAuthMiddleware without
    importing accountingqb.server (which reads env at import time).
    """
    # Importing accountingqb.server registers all tools on the shared
    # FastMCP instance.
    from accountingqb import server as _srv  # noqa: PLC0415

    mcp = _srv.mcp
    # Mark this process as the hosted connector so qb_server_info reports the
    # deployment mode unconditionally (not from the QuickBooks session state).
    _srv._HOSTED_CONNECTOR = True

    # Stateless + JSON responses: every request is independent (horizontal
    # scaling, no session affinity) and responses are plain JSON instead of
    # SSE streams. Must be set before streamable_http_app() constructs the
    # session manager. Serves at settings.streamable_http_path (default /mcp).
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    # Configure the MCP transport's host/origin allow-list explicitly. The SDK's
    # DNS-rebinding protection (mcp >= 1.29 enables it by default with a
    # localhost-only allow-list) would otherwise reject every request to
    # mcp.accountingqb.com with "421 Invalid Host header". DNS-rebinding is a
    # browser-origin attack; this service is not browser-facing, sits behind the
    # Fly proxy, and already enforces Bearer-JWT auth via BearerAuthMiddleware —
    # so we pin the allow-list to the known host instead of relying on the
    # SDK's version-dependent default (which changed under us and caused an
    # outage). Override with MCP_ALLOWED_HOSTS (comma-separated) if needed.
    from urllib.parse import urlparse  # noqa: PLC0415

    from mcp.server.transport_security import TransportSecuritySettings  # noqa: PLC0415

    _host = urlparse(RESOURCE_URL).netloc or "mcp.accountingqb.com"
    _allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "")
    hosts = [h.strip() for h in _allowed_hosts.split(",") if h.strip()] or [
        _host,
        f"{_host}:*",
    ]
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=[RESOURCE_URL, f"{RESOURCE_URL}/*"],
    )

    inner = mcp.streamable_http_app()

    try:
        from accountingqb import __version__ as _ver  # noqa: PLC0415
    except Exception:
        _ver = ""
    try:
        _tools = len(mcp._tool_manager._tools)
    except Exception:
        _tools = 0
    try:
        from accountingqb.tax_tables import public_tax_data  # noqa: PLC0415

        _tax_data = public_tax_data()  # computed once at startup (static per deploy)
    except Exception:
        _tax_data = {}

    return BearerAuthMiddleware(
        inner,
        jwt_secret=MCP_JWT_SECRET,
        resource_url=RESOURCE_URL,
        auth_server_url=AS_URL,
        version=_ver,
        tool_count=_tools,
        tax_data=_tax_data,
    )


def main() -> None:
    import uvicorn  # noqa: PLC0415

    if not MCP_JWT_SECRET:
        logger.warning(
            "MCP_JWT_SECRET is not set — all /mcp requests will be rejected."
        )

    port = int(os.environ.get("PORT", "8000"))
    logging.basicConfig(level=logging.INFO)
    # httpx logs every outbound request URL at INFO — for QuickBooks calls that
    # is the realm id + /query SQL. Keep customer data and realm ids out of logs.
    for _noisy in ("httpx", "httpcore"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
