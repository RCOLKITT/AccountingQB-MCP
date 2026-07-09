"""Per-connection QuickBooks auth state.

All mutable per-connection state (tokens, active realm, hosted-company list)
lives in a :class:`QBContext` carried by a :class:`~contextvars.ContextVar`.

For the classic single-tenant deployments (Claude Desktop extension, local
``python server.py``) nothing changes: a single module-level default context
is initialized from the environment at import time and every request uses it.

A future multi-tenant remote service can call :func:`set_ctx` with a fresh
``QBContext`` at the start of each request; because ``ContextVar`` values are
task-local, concurrent requests are fully isolated from each other.

Configuration *inputs* (``QB_CLIENT_ID``, ``QB_CLIENT_SECRET``,
``QB_LICENSE_KEY``, ``QB_API_URL``, environment/base URL, ...) are not per
connection and stay as module constants in ``server.py``.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class QBContext:
    """Mutable per-connection QuickBooks auth state."""

    # OAuth token cache
    access_token: Optional[str] = None
    token_expiry: Optional[datetime] = None  # always timezone-aware UTC
    refresh_token: str = ""

    # Active company
    realm_id: str = ""

    # Hosted mode (tokens brokered by the AccountingQB API)
    hosted_mode: bool = False
    hosted_companies: list = field(default_factory=list)
    # True once the company list has been fetched from the broker (or loaded
    # from the offline cache) — hosted-company fetching is lazy.
    hosted_loaded: bool = False

    # realm_id -> region/country code cache (reserved for future use, e.g.
    # per-region tax handling)
    region_cache: dict = field(default_factory=dict)

    # Whether tokens may be cached (encrypted) on local disk. True for the
    # default single-tenant context; a multi-tenant remote service must set
    # this to False on the per-request contexts it creates.
    persist_tokens: bool = True


# The default context used by single-tenant deployments. server.py populates
# it from the environment at import time.
_default_ctx = QBContext()

_qb_ctx: ContextVar[QBContext] = ContextVar("qb_ctx", default=_default_ctx)


def get_ctx() -> QBContext:
    """Return the QBContext for the current task/connection."""
    return _qb_ctx.get()


def set_ctx(ctx: QBContext) -> Token:
    """Install ``ctx`` as the current task's context.

    Returns the ContextVar token, which can be passed to :func:`reset_ctx`
    to restore the previous context.
    """
    return _qb_ctx.set(ctx)


def reset_ctx(token: Token) -> None:
    """Restore the context that was active before the matching set_ctx()."""
    _qb_ctx.reset(token)
