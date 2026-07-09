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

# TTL for the per-license default-realm cache. The broker's own token cache
# guidance is ~45 minutes; realm changes are rare, so the same TTL is fine.
DEFAULT_REALM_TTL_SECONDS = 45 * 60

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"


# ---------------------------------------------------------------------------
# Default-realm TTL cache
# ---------------------------------------------------------------------------
class DefaultRealmCache:
    """In-process TTL cache: license_key -> default realm id (or None).

    Backed by ``GET {QB_API_URL}/api/license/default-realm?license_key=...``
    (see web/src/app/api/license/default-realm/route.ts). Lookup failures are
    cached as ``None`` for the TTL as well, so a down broker never turns into
    a per-request hot loop; ``get_access_token()`` falls back to the first
    connected company when realm_id is empty.
    """

    def __init__(self, api_url: str = QB_API_URL, ttl: float = DEFAULT_REALM_TTL_SECONDS):
        self._api_url = api_url.rstrip("/")
        self._ttl = ttl
        self._cache: dict[str, tuple[float, Optional[str]]] = {}

    async def get(self, license_key: str) -> Optional[str]:
        now = time.monotonic()
        hit = self._cache.get(license_key)
        if hit and now - hit[0] < self._ttl:
            return hit[1]

        realm: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._api_url}/api/license/default-realm",
                    params={"license_key": license_key},
                )
                if resp.status_code == 200:
                    realm = resp.json().get("realmId") or None
        except Exception as exc:  # network errors are non-fatal
            logger.warning("default-realm lookup failed: %s", exc)

        self._cache[license_key] = (now, realm)
        return realm

    def invalidate(self, license_key: str) -> None:
        self._cache.pop(license_key, None)


_default_realm_cache = DefaultRealmCache()


async def _resolve_default_realm(license_key: str) -> Optional[str]:
    return await _default_realm_cache.get(license_key)


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
        realm_resolver: Optional[Callable[[str], Awaitable[Optional[str]]]] = _resolve_default_realm,
    ):
        self.app = app
        self.jwt_secret = jwt_secret
        self.resource_url = resource_url.rstrip("/")
        self.auth_server_url = auth_server_url.rstrip("/")
        self.realm_resolver = realm_resolver

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
        await send({"type": "http.response.start", "status": status, "headers": headers})
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
        ctx = QBContext(persist_tokens=False, hosted_mode=True)
        ctx.realm_id = realm_id or ""
        # Dynamic attribute — QBContext has no license_key field yet; see the
        # module docstring for the server.py/context.py hook this requires.
        ctx.license_key = license_key  # type: ignore[attr-defined]
        ctx.user_id = claims.get("sub", "")  # type: ignore[attr-defined]

        token = set_ctx(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_ctx(token)


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
    from accountingqb.server import mcp  # noqa: PLC0415

    # Stateless + JSON responses: every request is independent (horizontal
    # scaling, no session affinity) and responses are plain JSON instead of
    # SSE streams. Must be set before streamable_http_app() constructs the
    # session manager. Serves at settings.streamable_http_path (default /mcp).
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    inner = mcp.streamable_http_app()

    return BearerAuthMiddleware(
        inner,
        jwt_secret=MCP_JWT_SECRET,
        resource_url=RESOURCE_URL,
        auth_server_url=AS_URL,
    )


def main() -> None:
    import uvicorn  # noqa: PLC0415

    if not MCP_JWT_SECRET:
        logger.warning(
            "MCP_JWT_SECRET is not set — all /mcp requests will be rejected."
        )

    port = int(os.environ.get("PORT", "8000"))
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
