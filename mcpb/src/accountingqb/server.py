"""
QuickBooks Online MCP Server — Production Edition

A comprehensive MCP server for sole proprietors and small businesses.
Covers all QuickBooks Online entity types: transactions (purchases, deposits,
transfers, journal entries, bills, payments), reports (P&L, balance sheet,
cash flow, general ledger, AP/AR aging, trial balance), and entity management
(vendors, customers, accounts, items).

Built with FastMCP using flat parameters (required for Claude Desktop compatibility).
"""

import os
import sys
import json
import time
import asyncio
import hashlib
import logging
import functools
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

try:
    from .context import QBContext, get_ctx, set_ctx, reset_ctx, _default_ctx
    from . import tax_tables as _tt
    from .tax_tables import (  # noqa: F401 — the tax-data registry (L2)
        TAX_DATA_VERSION, TAX_DATA_VERIFIED, TABLES, TaxDataError,
        tax_value, tax_value_or_latest, tax_data_footer,
        load_ledger, verify_ledger_chain,
        _US_STATE_TAX, _FED_BRACKETS, _RATES, _SS_WAGE_BASE,
        _SE_NET_EARNINGS_FACTOR, _SE_SS_RATE, _SE_MEDICARE_RATE,
        _TCJA_PHASE_DOWN, _SUV_179_CAP, _280F_LIMITS, _MACRS_5YR,
        _SEC_179_LIMITS, _SEC_195, _HOME_OFFICE_SIMPLIFIED,
        _STD_MILEAGE_CENTS, _RETIREMENT_LIMITS, _1099_NEC_THRESHOLD,
        _GST_QUICK_METHOD_LIMIT, _GST_QUICK_METHOD_CREDIT_BASE,
        _MEALS_ITC_FACTOR, _GST_WORKPAPER_FOOTER,
        _CA_SALES_TAX_REGIME, _CA_PROVINCIAL_AGENCY_HINTS,
        _ca_regime, _ca_regime_describe, _ca_agency_is_provincial,
        _T2125_LINE_MAP, _CCA_CLASSES, _CLASS_10_1_CEILING,
        _CLASS_54_ZEV_CEILING, _AII_START_YEAR, _AII_FIRST_YEAR_FACTOR,
        _T4A_ADMIN_THRESHOLD, _CPP_PARAMS, _CPP_BASIC_EXEMPTION,
        _CPP_RATE_SELF, _CPP2_RATE_SELF, _CA_FED_BRACKETS_APPROX,
        _CA_BPA_APPROX, _CA_PROV_FLAT_APPROX, _CRA_INSTALMENT_DATES,
        _CRA_INSTALMENT_THRESHOLD, _QUICK_METHOD_REMITTANCE,
    )
except ImportError:  # pragma: no cover — direct script execution (no package)
    from context import QBContext, get_ctx, set_ctx, reset_ctx, _default_ctx
    import tax_tables as _tt
    from tax_tables import (  # noqa: F401
        TAX_DATA_VERSION, TAX_DATA_VERIFIED, TABLES, TaxDataError,
        tax_value, tax_value_or_latest, tax_data_footer,
        load_ledger, verify_ledger_chain,
        _US_STATE_TAX, _FED_BRACKETS, _RATES, _SS_WAGE_BASE,
        _SE_NET_EARNINGS_FACTOR, _SE_SS_RATE, _SE_MEDICARE_RATE,
        _TCJA_PHASE_DOWN, _SUV_179_CAP, _280F_LIMITS, _MACRS_5YR,
        _SEC_179_LIMITS, _SEC_195, _HOME_OFFICE_SIMPLIFIED,
        _STD_MILEAGE_CENTS, _RETIREMENT_LIMITS, _1099_NEC_THRESHOLD,
        _GST_QUICK_METHOD_LIMIT, _GST_QUICK_METHOD_CREDIT_BASE,
        _MEALS_ITC_FACTOR, _GST_WORKPAPER_FOOTER,
        _CA_SALES_TAX_REGIME, _CA_PROVINCIAL_AGENCY_HINTS,
        _ca_regime, _ca_regime_describe, _ca_agency_is_provincial,
        _T2125_LINE_MAP, _CCA_CLASSES, _CLASS_10_1_CEILING,
        _CLASS_54_ZEV_CEILING, _AII_START_YEAR, _AII_FIRST_YEAR_FACTOR,
        _T4A_ADMIN_THRESHOLD, _CPP_PARAMS, _CPP_BASIC_EXEMPTION,
        _CPP_RATE_SELF, _CPP2_RATE_SELF, _CA_FED_BRACKETS_APPROX,
        _CA_BPA_APPROX, _CA_PROV_FLAT_APPROX, _CRA_INSTALMENT_DATES,
        _CRA_INSTALMENT_THRESHOLD, _QUICK_METHOD_REMITTANCE,
    )

mcp = FastMCP("quickbooks")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quickbooks-mcp")

# ---------------------------------------------------------------------------
# Encrypted Credential Storage
# ---------------------------------------------------------------------------
# Tokens at rest are encrypted with a machine-derived key. The key is
# generated once per installation and stored alongside the data directory.
# This prevents tokens from being readable if the file is copied to another
# machine or leaked.

_DATA_DIR = Path(os.environ.get(
    "QB_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qb_data")
))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

def _get_or_create_key() -> bytes:
    """Get or create a machine-local encryption key (Fernet-compatible)."""
    key_file = _DATA_DIR / ".key"
    if key_file.exists():
        try:
            return key_file.read_bytes().strip()
        except OSError:
            pass
    # Generate a new key from machine identity + random salt
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
    except ImportError:
        # Fallback: base64-encoded random bytes (still Fernet-compatible)
        import base64, secrets
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    try:
        key_file.write_bytes(key)
        os.chmod(str(key_file), 0o600)  # owner-only read
    except OSError:
        pass
    return key

def _encrypt_token(token: str) -> str:
    """Encrypt a token string for storage at rest."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        return f.encrypt(token.encode()).decode()
    except ImportError:
        logger.warning("cryptography not installed — tokens stored in plaintext")
        return token

def _decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token. Falls back to plaintext if decryption fails."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        return encrypted
    except Exception:
        # Likely a plaintext token from before encryption was enabled
        return encrypted

def _save_token(token: str, filename: str = "refresh_token.enc") -> None:
    """Encrypt and persist a token to disk."""
    token_path = _DATA_DIR / filename
    try:
        encrypted = _encrypt_token(token)
        token_path.write_text(encrypted)
        os.chmod(str(token_path), 0o600)
    except OSError as e:
        logger.warning(f"Could not save token: {e}")

def _load_token(filename: str = "refresh_token.enc") -> Optional[str]:
    """Load and decrypt a persisted token."""
    token_path = _DATA_DIR / filename
    if not token_path.exists():
        return None
    try:
        encrypted = token_path.read_text().strip()
        if encrypted:
            return _decrypt_token(encrypted)
    except OSError as e:
        logger.warning(f"Could not load token: {e}")
    return None

# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------
# QuickBooks API allows ~500 requests per minute per realm. We enforce a
# conservative local limit to prevent accidental flooding.

_RATE_LIMIT_MAX = int(os.environ.get("QB_RATE_LIMIT", "200"))  # per minute
_RATE_LIMIT_WINDOW = 60  # seconds
_request_timestamps: list[float] = []

def _check_rate_limit() -> None:
    """Raise an error if we're making too many API calls."""
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    # Prune old timestamps
    while _request_timestamps and _request_timestamps[0] < cutoff:
        _request_timestamps.pop(0)
    if len(_request_timestamps) >= _RATE_LIMIT_MAX:
        raise RuntimeError(
            f"Rate limit exceeded: {_RATE_LIMIT_MAX} requests per minute. "
            "Please wait before making additional requests."
        )
    _request_timestamps.append(now)

# ---------------------------------------------------------------------------
# License Gating
# ---------------------------------------------------------------------------
# When distributed as a paid product, tools are split into FREE (always
# available) and PAID (requires valid license). During development and
# self-hosted use, all tools are unlocked by default.

LICENSE_KEY = os.environ.get("QB_LICENSE_KEY", "")
_LICENSE_VALIDATION_URL = os.environ.get(
    "QB_LICENSE_URL", ""  # e.g. https://yourapp.vercel.app/api/validate
)
_license_cache: dict = {}  # {key: {valid: bool, tier: str, expires: float}}
_LICENSE_CACHE_TTL = 86400  # 24 hours

# Tool classification: FREE tools are always available; PAID require license
FREE_TOOLS = {
    "qb_company_info",
    "qb_list_transactions",
    "qb_list_deposits",
    "qb_list_transfers",
    "qb_list_journal_entries",
    "qb_list_bills",
    "qb_list_bill_payments",
    "qb_list_sales_receipts",
    "qb_list_payments",
    "qb_list_invoices",
    "qb_list_accounts",
    "qb_list_vendors",
    "qb_list_customers",
    "qb_list_items",
    "qb_profit_loss",
    "qb_balance_sheet",
    "qb_cash_flow",
    "qb_trial_balance",
    "qb_reconciliation_status",
    "qb_comparative_statements",
    "qb_ar_aging",
    "qb_ap_aging",
    "qb_expense_summary",
    "qb_income_summary",
    "qb_account_balance",
    "qb_list_estimates",
    "qb_search_transactions",
    # Hosted mode management tools (always free)
    "qb_list_companies",
    "qb_switch_company",
    "qb_refresh_connection",
    # Tax-code discovery utilities (always free)
    "qb_list_tax_codes",
    "qb_list_tax_rates",
}  # ~30 read-only / reporting / management tools

def _effective_license_key() -> str:
    """License key for the current connection.

    Single-tenant deployments use the QB_LICENSE_KEY environment value; the
    remote multi-tenant service sets QBContext.license_key per request from
    the verified JWT claim, which takes precedence.
    """
    return get_ctx().license_key or LICENSE_KEY

async def _validate_license(key: str) -> dict:
    """Validate a license key against the remote API (with 24h cache)."""
    if not key:
        return {"valid": False, "tier": "free", "reason": "no_key"}

    # Check cache
    cached = _license_cache.get(key)
    if cached and cached.get("expires", 0) > time.time():
        return cached

    # If no validation URL configured, treat any key as valid (dev mode)
    if not _LICENSE_VALIDATION_URL:
        result = {"valid": True, "tier": "pro", "reason": "dev_mode"}
        result["expires"] = time.time() + _LICENSE_CACHE_TTL
        _license_cache[key] = result
        return result

    # Remote validation
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_LICENSE_VALIDATION_URL, json={"key": key})
            if resp.status_code == 200:
                result = resp.json()
                result["expires"] = time.time() + _LICENSE_CACHE_TTL
                _license_cache[key] = result
                return result
            else:
                # API unreachable — use cached result if available, else allow
                if cached:
                    return cached
                return {"valid": True, "tier": "grace", "reason": "api_unreachable"}
    except Exception as e:
        logger.warning(f"License validation failed: {e}")
        # Offline resilience: if we validated before, trust the cache
        if cached:
            return cached
        return {"valid": True, "tier": "grace", "reason": "offline"}

def require_license(func):
    """Decorator that gates a tool behind license validation.
    Free tools (in FREE_TOOLS set) always pass through.
    When no license system is configured, all tools are unlocked (dev mode)."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        # Free tools always allowed
        if tool_name in FREE_TOOLS:
            return await func(*args, **kwargs)
        # No license system configured = dev/self-hosted mode = all unlocked
        if not _effective_license_key() and not _LICENSE_VALIDATION_URL:
            return await func(*args, **kwargs)
        # Validate license
        result = await _validate_license(_effective_license_key())
        if result.get("valid"):
            return await func(*args, **kwargs)
        return (
            f"⚠️ This tool ({tool_name}) requires a paid license.\n\n"
            f"Your current plan: **{result.get('tier', 'free')}**\n"
            f"Upgrade at: https://accountingqb.com/pricing\n\n"
            f"Free tools available: {', '.join(sorted(FREE_TOOLS))}"
        )
    return wrapper

# ---------------------------------------------------------------------------
# Usage Tracking
# ---------------------------------------------------------------------------
# Reports tool invocations to AccountingQB API for analytics and "time saved"
# calculations. This is non-blocking and fire-and-forget — tool execution is
# never interrupted by tracking failures.

# Strong references to in-flight tracking tasks. asyncio only holds a weak
# reference to tasks created with create_task(), so without this set a
# fire-and-forget task can be garbage-collected before its POST completes.
_usage_tasks: set = set()

async def _track_usage(tool_name: str, license_key: str, realm_id: str | None) -> None:
    """Report tool usage to AccountingQB API (non-blocking, fire-and-forget).
    Silently fails if license key is not set or API is unreachable.

    license_key and realm_id are captured synchronously at call time (see
    track_usage) rather than re-read from the request context here — in the
    stateless-HTTP remote server the request context may already be torn down
    by the time this background task runs."""
    if not license_key:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                USAGE_API_URL,
                json={
                    "licenseKey": license_key,
                    "toolName": tool_name,
                    "realmId": realm_id or None,
                },
            )
    except Exception as e:
        # Non-blocking — don't interrupt tool execution for tracking failures
        logger.debug(f"Usage tracking failed for {tool_name}: {e}")

def track_usage(func):
    """Decorator that tracks tool usage after successful execution.
    Runs tracking in background task to avoid blocking tool response."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        # Capture the effective license + realm NOW, while the request context
        # is live (single-tenant: QB_LICENSE_KEY; remote: per-request JWT claim).
        license_key = _effective_license_key()
        if license_key:
            try:
                realm_id = get_ctx().realm_id
                task = asyncio.create_task(
                    _track_usage(func.__name__, license_key, realm_id)
                )
                _usage_tasks.add(task)
                task.add_done_callback(_usage_tasks.discard)
            except RuntimeError:
                # No running event loop — skip tracking rather than crash.
                pass
        return result
    return wrapper

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID", "")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET", "")
QB_REDIRECT_URI = os.environ.get("QB_REDIRECT_URI", "http://localhost:8080/callback")
QB_REALM_ID = os.environ.get("QB_REALM_ID", "")
QB_REFRESH_TOKEN = os.environ.get("QB_REFRESH_TOKEN", "")

# Hosted mode: fetch tokens from AccountingQB API instead of local storage.
# Per-connection state (tokens, active realm, company list) lives in
# QBContext (see context.py); only configuration inputs stay module-level.
QB_API_URL = os.environ.get("QB_API_URL", "https://accountingqb.com")

# Usage tracking: report tool invocations back to AccountingQB for analytics
USAGE_API_URL = os.environ.get("QB_USAGE_API_URL", f"{QB_API_URL}/api/usage/track")

# Friendly error for hosted users whose license has no connected company yet.
_NO_COMPANY_CONNECTED_MSG = (
    "No QuickBooks company is connected to your AccountingQB account yet. "
    "Connect one at https://accountingqb.com/dashboard, then run "
    "qb_refresh_connection."
)


def _utcnow() -> datetime:
    """Timezone-aware UTC now. All token-expiry math uses aware datetimes."""
    return datetime.now(timezone.utc)


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce a datetime to timezone-aware UTC (naive values are assumed UTC)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_token_expiry(expires_at: Optional[str]) -> datetime:
    """Parse the broker's ISO-8601 expiresAt into aware UTC (1h fallback)."""
    if expires_at:
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return _as_aware_utc(parsed)
        except ValueError:
            logger.warning(f"Unparseable token expiry {expires_at!r}; assuming 1h")
    return _utcnow() + timedelta(hours=1)


def _adopt_hosted_companies(ctx: "QBContext", companies: list) -> None:
    """Install a freshly fetched hosted-company list into the context.

    Selects the first company as active (matching historic behavior of the
    company-list fetch) and caches the list on disk when allowed.
    """
    ctx.hosted_companies = companies
    ctx.hosted_mode = True
    ctx.hosted_loaded = True
    first = companies[0]
    ctx.realm_id = first["realmId"]
    ctx.refresh_token = first["refreshToken"]
    if ctx.persist_tokens:
        # Cache tokens locally for offline resilience
        _save_hosted_tokens(companies)


def _fetch_hosted_tokens(ctx: Optional["QBContext"] = None) -> bool:
    """Fetch OAuth tokens from AccountingQB API using license key.
    Returns True if successful, False otherwise."""
    if ctx is None:
        ctx = get_ctx()

    license_key = ctx.license_key or LICENSE_KEY
    if not license_key:
        return False

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{QB_API_URL}/api/oauth/token",
                json={"licenseKey": license_key}
            )
            if resp.status_code == 200:
                data = resp.json()
                companies = data.get("companies", [])
                if companies:
                    _adopt_hosted_companies(ctx, companies)
                    logger.info(f"Loaded {len(companies)} company(s) from AccountingQB API (hosted mode)")
                    return True
                ctx.hosted_loaded = True  # broker reachable; simply no companies
            elif resp.status_code == 404:
                ctx.hosted_loaded = True
                logger.info("No QuickBooks companies connected yet")
            else:
                logger.warning(f"Failed to fetch tokens from API: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Could not fetch hosted tokens: {e}")
        # Try loading cached hosted tokens
        if _load_hosted_tokens(ctx):
            return True
    return False

def _save_hosted_tokens(companies: list) -> None:
    """Cache hosted tokens locally for offline use."""
    cache_path = _DATA_DIR / "hosted_tokens.json"
    try:
        # Encrypt the entire payload
        payload = json.dumps(companies)
        encrypted = _encrypt_token(payload)
        cache_path.write_text(encrypted)
        os.chmod(str(cache_path), 0o600)
    except Exception as e:
        logger.warning(f"Could not cache hosted tokens: {e}")

def _load_hosted_tokens(ctx: Optional["QBContext"] = None) -> bool:
    """Load cached hosted tokens for offline resilience."""
    if ctx is None:
        ctx = get_ctx()
    if not ctx.persist_tokens:
        return False

    cache_path = _DATA_DIR / "hosted_tokens.json"
    if not cache_path.exists():
        return False
    try:
        encrypted = cache_path.read_text().strip()
        decrypted = _decrypt_token(encrypted)
        companies = json.loads(decrypted)
        if companies:
            ctx.hosted_companies = companies
            ctx.hosted_mode = True
            ctx.hosted_loaded = True
            first = companies[0]
            ctx.realm_id = first["realmId"]
            ctx.refresh_token = first["refreshToken"]
            logger.info(f"Loaded {len(companies)} cached company(s) (offline mode)")
            return True
    except Exception as e:
        logger.warning(f"Could not load cached hosted tokens: {e}")
    return False

# ---------------------------------------------------------------------------
# Default context initialization (single-tenant startup)
# ---------------------------------------------------------------------------
# The default QBContext is seeded from the environment. Hosted mode is now
# LAZY: no network calls happen at import time — the first tool call that
# needs a token fetches the company list from the AccountingQB API.

_default_ctx.realm_id = QB_REALM_ID
_default_ctx.refresh_token = QB_REFRESH_TOKEN

_key_upper = LICENSE_KEY.upper()
_IS_DEMO_KEY = _key_upper == "DEMO" or _key_upper.startswith("LK-DEMO-")

if LICENSE_KEY and not QB_REFRESH_TOKEN and not _IS_DEMO_KEY:
    # Hosted mode: tokens are brokered by the AccountingQB API (lazily).
    _default_ctx.hosted_mode = True
else:
    # Fallback: Prefer persisted encrypted token, then legacy plaintext, then env var
    _encrypted_token = _load_token("refresh_token.enc")
    if _encrypted_token:
        _default_ctx.refresh_token = _encrypted_token
        logger.info("Loaded encrypted refresh token from disk")
    else:
        # Check for legacy plaintext token file and migrate it
        _legacy_token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qb_refresh_token")
        if os.path.exists(_legacy_token_file):
            try:
                with open(_legacy_token_file) as _f:
                    _saved = _f.read().strip()
                if _saved:
                    _default_ctx.refresh_token = _saved
                    # Migrate to encrypted storage
                    _save_token(_saved)
                    logger.info("Migrated legacy token to encrypted storage")
                    try:
                        os.remove(_legacy_token_file)
                    except OSError:
                        pass
            except OSError:
                pass

QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")

# Intuit is migrating all report responses to a modernized service on
# Aug 31, 2026. Setting QB_REPORTS_V2_TEST=1 routes report requests
# through it today (via Intuit's temporary _testing_migration parameter)
# so parsing drift can be caught before the forced cutover.
QB_REPORTS_V2_TEST = os.environ.get("QB_REPORTS_V2_TEST", "").lower() in ("1", "true", "yes")

BASE_URL = (
    "https://quickbooks.api.intuit.com" if QB_ENVIRONMENT == "production"
    else "https://sandbox-quickbooks.api.intuit.com"
)
AUTH_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# ---------------------------------------------------------------------------
# Demo Mode
# ---------------------------------------------------------------------------
# Demo mode returns mock data for reviewers who don't have QuickBooks access.
# Activated by license keys starting with "LK-DEMO-" or the exact key "DEMO".

def _is_demo_mode() -> bool:
    """Check if we're running in demo mode (for reviewers without QuickBooks)."""
    if not LICENSE_KEY:
        return False
    key_upper = LICENSE_KEY.upper()
    return key_upper == "DEMO" or key_upper.startswith("LK-DEMO-")

_DEMO_MODE = _is_demo_mode()


def _demo_active() -> bool:
    """Per-request demo check. Local mode: the QB_LICENSE_KEY env var
    (module-level _DEMO_MODE). Hosted mode: the per-request ctx.license_key
    set by remote.py — a reviewer signing in with an LK-DEMO- license gets
    mock data through the remote connector too."""
    if _DEMO_MODE:
        return True
    key = (getattr(get_ctx(), "license_key", "") or "").upper()
    return key == "DEMO" or key.startswith("LK-DEMO-")

# Demo company info
DEMO_COMPANY = {
    "CompanyName": "Acme Consulting LLC",
    "LegalName": "Acme Consulting LLC",
    "CompanyAddr": {
        "Line1": "123 Main Street",
        "City": "San Francisco",
        "CountrySubDivisionCode": "CA",
        "PostalCode": "94102"
    },
    "Email": {"Address": "hello@acmeconsulting.com"},
    "PrimaryPhone": {"FreeFormNumber": "(415) 555-0123"},
    "FiscalYearStartMonth": "January",
    "Country": "US",
    "EmployerId": "12-3456789"
}

# Demo vendors
DEMO_VENDORS = [
    {"Id": "1", "DisplayName": "Amazon Web Services", "Balance": 2847.50, "Active": True},
    {"Id": "2", "DisplayName": "Google Workspace", "Balance": 0, "Active": True},
    {"Id": "3", "DisplayName": "WeWork", "Balance": 1500.00, "Active": True},
    {"Id": "4", "DisplayName": "Zoom Communications", "Balance": 149.90, "Active": True},
    {"Id": "5", "DisplayName": "Staples Office Supplies", "Balance": 0, "Active": True},
    {"Id": "6", "DisplayName": "United Airlines", "Balance": 0, "Active": True},
    {"Id": "7", "DisplayName": "Uber for Business", "Balance": 0, "Active": True},
    {"Id": "8", "DisplayName": "Adobe Creative Cloud", "Balance": 599.88, "Active": True},
]

# Demo customers
DEMO_CUSTOMERS = [
    {"Id": "1", "DisplayName": "TechStart Inc", "Balance": 15000.00, "Active": True, "PrimaryEmailAddr": {"Address": "ap@techstart.io"}},
    {"Id": "2", "DisplayName": "Green Valley Farms", "Balance": 7500.00, "Active": True, "PrimaryEmailAddr": {"Address": "billing@greenvalley.com"}},
    {"Id": "3", "DisplayName": "Metro Legal Services", "Balance": 0, "Active": True, "PrimaryEmailAddr": {"Address": "accounts@metrolegal.com"}},
    {"Id": "4", "DisplayName": "Sunrise Healthcare", "Balance": 22500.00, "Active": True, "PrimaryEmailAddr": {"Address": "finance@sunrisehc.org"}},
    {"Id": "5", "DisplayName": "Blue Ocean Media", "Balance": 4200.00, "Active": True, "PrimaryEmailAddr": {"Address": "pay@blueocean.media"}},
]

# Demo accounts (Chart of Accounts)
DEMO_ACCOUNTS = [
    {"Id": "1", "Name": "Checking", "AccountType": "Bank", "CurrentBalance": 47523.84, "Active": True, "FullyQualifiedName": "Checking"},
    {"Id": "2", "Name": "Savings", "AccountType": "Bank", "CurrentBalance": 125000.00, "Active": True, "FullyQualifiedName": "Savings"},
    {"Id": "3", "Name": "Accounts Receivable", "AccountType": "Accounts Receivable", "CurrentBalance": 49200.00, "Active": True, "FullyQualifiedName": "Accounts Receivable"},
    {"Id": "4", "Name": "Accounts Payable", "AccountType": "Accounts Payable", "CurrentBalance": 5097.28, "Active": True, "FullyQualifiedName": "Accounts Payable"},
    {"Id": "5", "Name": "Consulting Revenue", "AccountType": "Income", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Consulting Revenue"},
    {"Id": "6", "Name": "Software Revenue", "AccountType": "Income", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Software Revenue"},
    {"Id": "7", "Name": "Office Supplies", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Office Supplies"},
    {"Id": "8", "Name": "Software & Subscriptions", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Software & Subscriptions"},
    {"Id": "9", "Name": "Travel", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Travel"},
    {"Id": "10", "Name": "Rent", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Rent"},
    {"Id": "11", "Name": "Professional Services", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Professional Services"},
    {"Id": "12", "Name": "Advertising", "AccountType": "Expense", "CurrentBalance": 0, "Active": True, "FullyQualifiedName": "Advertising"},
    {"Id": "13", "Name": "Owner's Equity", "AccountType": "Equity", "CurrentBalance": 77876.56, "Active": True, "FullyQualifiedName": "Owner's Equity"},
]

# Demo transactions (recent expenses)
DEMO_TRANSACTIONS = [
    {"Id": "101", "TxnDate": "2026-03-25", "TotalAmt": 149.90, "EntityRef": {"name": "Zoom Communications"}, "AccountRef": {"name": "Software & Subscriptions"}, "PaymentType": "CreditCard", "Line": [{"Description": "Zoom Pro Annual"}]},
    {"Id": "102", "TxnDate": "2026-03-22", "TotalAmt": 1500.00, "EntityRef": {"name": "WeWork"}, "AccountRef": {"name": "Rent"}, "PaymentType": "Check", "Line": [{"Description": "March coworking space"}]},
    {"Id": "103", "TxnDate": "2026-03-20", "TotalAmt": 847.50, "EntityRef": {"name": "Amazon Web Services"}, "AccountRef": {"name": "Software & Subscriptions"}, "PaymentType": "CreditCard", "Line": [{"Description": "AWS monthly hosting"}]},
    {"Id": "104", "TxnDate": "2026-03-18", "TotalAmt": 234.56, "EntityRef": {"name": "Staples Office Supplies"}, "AccountRef": {"name": "Office Supplies"}, "PaymentType": "CreditCard", "Line": [{"Description": "Office supplies"}]},
    {"Id": "105", "TxnDate": "2026-03-15", "TotalAmt": 425.00, "EntityRef": {"name": "United Airlines"}, "AccountRef": {"name": "Travel"}, "PaymentType": "CreditCard", "Line": [{"Description": "Flight to Chicago client meeting"}]},
    {"Id": "106", "TxnDate": "2026-03-12", "TotalAmt": 2000.00, "EntityRef": {"name": "Amazon Web Services"}, "AccountRef": {"name": "Software & Subscriptions"}, "PaymentType": "CreditCard", "Line": [{"Description": "AWS reserved instances"}]},
    {"Id": "107", "TxnDate": "2026-03-10", "TotalAmt": 599.88, "EntityRef": {"name": "Adobe Creative Cloud"}, "AccountRef": {"name": "Software & Subscriptions"}, "PaymentType": "CreditCard", "Line": [{"Description": "Adobe CC annual"}]},
    {"Id": "109", "TxnDate": "2026-04-15", "TotalAmt": 8500.00, "EntityRef": {"name": "United States Treasury"}, "AccountRef": {"name": "Estimated Tax Payments"}, "PaymentType": "Check", "Line": [{"Description": "Q1 2026 federal estimated tax (Form 1040-ES)"}]},
    {"Id": "108", "TxnDate": "2026-03-05", "TotalAmt": 87.50, "EntityRef": {"name": "Uber for Business"}, "AccountRef": {"name": "Travel"}, "PaymentType": "CreditCard", "Line": [{"Description": "Client transportation"}]},
]

# Demo invoices
DEMO_INVOICES = [
    {"Id": "201", "DocNumber": "1042", "TxnDate": "2026-03-01", "DueDate": "2026-03-31", "CustomerRef": {"name": "TechStart Inc", "value": "1"}, "TotalAmt": 15000.00, "Balance": 15000.00, "Line": [{"Description": "Q1 Consulting Services", "Amount": 15000.00}]},
    {"Id": "202", "DocNumber": "1043", "TxnDate": "2026-03-05", "DueDate": "2026-04-04", "CustomerRef": {"name": "Sunrise Healthcare", "value": "4"}, "TotalAmt": 22500.00, "Balance": 22500.00, "Line": [{"Description": "Software implementation", "Amount": 22500.00}]},
    {"Id": "203", "DocNumber": "1044", "TxnDate": "2026-03-10", "DueDate": "2026-04-09", "CustomerRef": {"name": "Green Valley Farms", "value": "2"}, "TotalAmt": 7500.00, "Balance": 7500.00, "Line": [{"Description": "Website redesign", "Amount": 7500.00}]},
    {"Id": "204", "DocNumber": "1041", "TxnDate": "2026-02-15", "DueDate": "2026-03-15", "CustomerRef": {"name": "Metro Legal Services", "value": "3"}, "TotalAmt": 12000.00, "Balance": 0, "Line": [{"Description": "IT consulting", "Amount": 12000.00}]},
    {"Id": "205", "DocNumber": "1045", "TxnDate": "2026-03-20", "DueDate": "2026-04-19", "CustomerRef": {"name": "Blue Ocean Media", "value": "5"}, "TotalAmt": 4200.00, "Balance": 4200.00, "Line": [{"Description": "Marketing automation setup", "Amount": 4200.00}]},
]

# Demo P&L data (for reports)
DEMO_PROFIT_LOSS = {
    "Header": {"ReportName": "ProfitAndLoss", "StartPeriod": "2026-01-01", "EndPeriod": "2026-03-28", "Currency": "USD"},
    "Rows": {
        "Row": [
            {"group": "Income", "Summary": {"ColData": [{"value": "Income"}, {"value": "187500.00"}]}, "Rows": {"Row": [
                {"ColData": [{"value": "Consulting Revenue"}, {"value": "145000.00"}]},
                {"ColData": [{"value": "Software Revenue"}, {"value": "42500.00"}]}
            ]}},
            {"group": "COGS", "Summary": {"ColData": [{"value": "Cost of Goods Sold"}, {"value": "0.00"}]}},
            {"group": "GrossProfit", "Summary": {"ColData": [{"value": "Gross Profit"}, {"value": "187500.00"}]}},
            {"group": "Expenses", "Summary": {"ColData": [{"value": "Expenses"}, {"value": "48750.00"}]}, "Rows": {"Row": [
                {"ColData": [{"value": "Software & Subscriptions"}, {"value": "12500.00"}]},
                {"ColData": [{"value": "Rent"}, {"value": "13500.00"}]},
                {"ColData": [{"value": "Travel"}, {"value": "8750.00"}]},
                {"ColData": [{"value": "Office Supplies"}, {"value": "2500.00"}]},
                {"ColData": [{"value": "Professional Services"}, {"value": "7500.00"}]},
                {"ColData": [{"value": "Advertising"}, {"value": "4000.00"}]}
            ]}},
            {"group": "NetIncome", "Summary": {"ColData": [{"value": "Net Income"}, {"value": "138750.00"}]}}
        ]
    }
}

# Demo Balance Sheet
DEMO_BALANCE_SHEET = {
    "Header": {"ReportName": "BalanceSheet", "StartPeriod": "2026-03-28", "EndPeriod": "2026-03-28", "Currency": "USD"},
    "Rows": {
        "Row": [
            {"group": "Assets", "Summary": {"ColData": [{"value": "ASSETS"}, {"value": "221723.84"}]}, "Rows": {"Row": [
                {"group": "CurrentAssets", "Summary": {"ColData": [{"value": "Current Assets"}, {"value": "221723.84"}]}, "Rows": {"Row": [
                    {"ColData": [{"value": "Checking"}, {"value": "47523.84"}]},
                    {"ColData": [{"value": "Savings"}, {"value": "125000.00"}]},
                    {"ColData": [{"value": "Accounts Receivable"}, {"value": "49200.00"}]}
                ]}}
            ]}},
            {"group": "Liabilities", "Summary": {"ColData": [{"value": "LIABILITIES"}, {"value": "5097.28"}]}, "Rows": {"Row": [
                {"ColData": [{"value": "Accounts Payable"}, {"value": "5097.28"}]}
            ]}},
            {"group": "Equity", "Summary": {"ColData": [{"value": "EQUITY"}, {"value": "216626.56"}]}, "Rows": {"Row": [
                {"ColData": [{"value": "Owner's Equity"}, {"value": "77876.56"}]},
                {"ColData": [{"value": "Net Income"}, {"value": "138750.00"}]}
            ]}}
        ]
    }
}

# Demo bills (A/P side, so aging/vendor tools have data)
DEMO_BILLS = [
    {"Id": "301", "TxnDate": "2026-03-01", "DueDate": "2026-03-31",
     "VendorRef": {"name": "Amazon Web Services", "value": "1"},
     "TotalAmt": 2847.50, "Balance": 2847.50,
     "Line": [{"Amount": 2847.50, "DetailType": "AccountBasedExpenseLineDetail",
               "AccountBasedExpenseLineDetail": {"AccountRef": {"name": "Software & Subscriptions"}}}]},
    {"Id": "302", "TxnDate": "2026-03-10", "DueDate": "2026-04-09",
     "VendorRef": {"name": "WeWork", "value": "3"},
     "TotalAmt": 1500.00, "Balance": 1500.00,
     "Line": [{"Amount": 1500.00, "DetailType": "AccountBasedExpenseLineDetail",
               "AccountBasedExpenseLineDetail": {"AccountRef": {"name": "Rent"}}}]},
]

# Entity -> demo rows for the data-layer fallback below
_DEMO_QUERY_DATA = {
    "CompanyInfo": [DEMO_COMPANY],
    "Vendor": DEMO_VENDORS,
    "Customer": DEMO_CUSTOMERS,
    "Account": DEMO_ACCOUNTS,
    "Purchase": DEMO_TRANSACTIONS,
    "Invoice": DEMO_INVOICES,
    "Bill": DEMO_BILLS,
}

# Demo aging reports (QBO AgedReceivables/AgedPayables row shape)
DEMO_AGED_RECEIVABLES = {
    "Header": {"ReportName": "AgedReceivables"},
    "Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Current"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "Blue Ocean Media (Inv #1045)"}, {"value": "4200.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Current"}, {"value": "4200.00"}]}},
        {"Header": {"ColData": [{"value": "31 - 60 days overdue"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "Green Valley Farms (Inv #1044)"}, {"value": "7500.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total 31 - 60"}, {"value": "7500.00"}]}},
        {"Header": {"ColData": [{"value": "61 - 90 days overdue"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "TechStart Inc (Inv #1042)"}, {"value": "15000.00"}]},
            {"ColData": [{"value": "Sunrise Healthcare (Inv #1043)"}, {"value": "22500.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total 61 - 90"}, {"value": "37500.00"}]}},
        {"Summary": {"ColData": [{"value": "TOTAL RECEIVABLES"}, {"value": "49200.00"}]}},
    ]},
}
DEMO_AGED_PAYABLES = {
    "Header": {"ReportName": "AgedPayables"},
    "Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Current"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "Amazon Web Services"}, {"value": "2847.50"}]},
            {"ColData": [{"value": "Adobe Creative Cloud"}, {"value": "599.88"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Current"}, {"value": "3447.38"}]}},
        {"Header": {"ColData": [{"value": "1 - 30 days overdue"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "WeWork"}, {"value": "1500.00"}]},
            {"ColData": [{"value": "Zoom Communications"}, {"value": "149.90"}]},
        ]}, "Summary": {"ColData": [{"value": "Total 1 - 30"}, {"value": "1649.90"}]}},
        {"Summary": {"ColData": [{"value": "TOTAL PAYABLES"}, {"value": "5097.28"}]}},
    ]},
}

# Demo Trial Balance (balances tie to DEMO_ACCOUNTS / DEMO_PROFIT_LOSS)
DEMO_TRIAL_BALANCE = {
    "Header": {"ReportName": "TrialBalance", "StartPeriod": "2026-01-01", "EndPeriod": "2026-06-30"},
    "Rows": {"Row": [
        {"ColData": [{"value": "Checking"}, {"value": "47523.84"}, {"value": ""}]},
        {"ColData": [{"value": "Savings"}, {"value": "125000.00"}, {"value": ""}]},
        {"ColData": [{"value": "Accounts Receivable"}, {"value": "49200.00"}, {"value": ""}]},
        {"ColData": [{"value": "Accounts Payable"}, {"value": ""}, {"value": "5097.28"}]},
        {"ColData": [{"value": "Owner's Equity"}, {"value": ""}, {"value": "77876.56"}]},
        {"ColData": [{"value": "Consulting Revenue"}, {"value": ""}, {"value": "145000.00"}]},
        {"ColData": [{"value": "Software Revenue"}, {"value": ""}, {"value": "42500.00"}]},
        {"ColData": [{"value": "Software & Subscriptions"}, {"value": "12500.00"}, {"value": ""}]},
        {"ColData": [{"value": "Rent"}, {"value": "13500.00"}, {"value": ""}]},
        {"ColData": [{"value": "Travel"}, {"value": "8750.00"}, {"value": ""}]},
        {"ColData": [{"value": "Office Supplies"}, {"value": "2500.00"}, {"value": ""}]},
        {"ColData": [{"value": "Professional Services"}, {"value": "7500.00"}, {"value": ""}]},
        {"ColData": [{"value": "Advertising"}, {"value": "4000.00"}, {"value": ""}]},
        {"Summary": {"ColData": [{"value": "TOTAL"}, {"value": "270473.84"}, {"value": "270473.84"}]}},
    ]},
}

# Demo General Ledger (entries tie to DEMO_TRANSACTIONS / DEMO_INVOICES)
DEMO_GENERAL_LEDGER = {
    "Header": {"ReportName": "GeneralLedger", "StartPeriod": "2026-01-01", "EndPeriod": "2026-06-30"},
    "Rows": {"Row": [
        {"Header": {"ColData": [{"value": "Checking"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "2026-02-15"}, {"value": "Payment — Metro Legal Services #1041"}, {"value": "12000.00"}]},
            {"ColData": [{"value": "2026-03-22"}, {"value": "Check — WeWork March coworking"}, {"value": "-1500.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Checking"}, {"value": "10500.00"}]}},
        {"Header": {"ColData": [{"value": "Software & Subscriptions"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "2026-03-10"}, {"value": "Adobe Creative Cloud annual"}, {"value": "599.88"}]},
            {"ColData": [{"value": "2026-03-20"}, {"value": "AWS monthly hosting"}, {"value": "847.50"}]},
            {"ColData": [{"value": "2026-03-25"}, {"value": "Zoom Pro annual"}, {"value": "149.90"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Software & Subscriptions"}, {"value": "1597.28"}]}},
        {"Header": {"ColData": [{"value": "Owner's Equity"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "2026-02-01"}, {"value": "Owner contribution"}, {"value": "10000.00"}]},
            {"ColData": [{"value": "2026-05-15"}, {"value": "Owner draw"}, {"value": "-6000.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Owner's Equity"}, {"value": "4000.00"}]}},
        {"Header": {"ColData": [{"value": "Consulting Revenue"}]}, "Rows": {"Row": [
            {"ColData": [{"value": "2026-03-01"}, {"value": "Invoice #1042 — TechStart Inc"}, {"value": "15000.00"}]},
            {"ColData": [{"value": "2026-03-05"}, {"value": "Invoice #1043 — Sunrise Healthcare"}, {"value": "22500.00"}]},
        ]}, "Summary": {"ColData": [{"value": "Total Consulting Revenue"}, {"value": "37500.00"}]}},
    ]},
}

_DEMO_REPORTS = {
    "ProfitAndLoss": DEMO_PROFIT_LOSS,
    "BalanceSheet": DEMO_BALANCE_SHEET,
    "AgedReceivables": DEMO_AGED_RECEIVABLES,
    "AgedPayables": DEMO_AGED_PAYABLES,
    "TrialBalance": DEMO_TRIAL_BALANCE,
    "GeneralLedger": DEMO_GENERAL_LEDGER,
}


def _demo_response(method: str, endpoint: str, params: dict = None,
                   json_body: dict = None) -> dict:
    """Data-layer demo fallback: serve mock QBO responses so every tool works
    in demo mode, not just the ones with a hand-written demo branch (those
    short-circuit before reaching qb_request). WHERE clauses are ignored —
    each entity returns its full sample set.
    """
    import re as _re

    if endpoint == "query":
        m = _re.search(r"FROM (\w+)", (params or {}).get("query", ""))
        entity = m.group(1) if m else ""
        return {"QueryResponse": {entity: _DEMO_QUERY_DATA[entity]}
                if entity in _DEMO_QUERY_DATA else {}}

    if endpoint == "preferences":
        return {"Preferences": {
            "TaxPrefs": {"PartnerTaxEnabled": True},
            "CurrencyPrefs": {"MultiCurrencyEnabled": False,
                              "HomeCurrency": {"value": "USD"}},
        }}

    if endpoint.startswith("reports/"):
        name = endpoint.split("/", 1)[1]
        report = _DEMO_REPORTS.get(name)
        if not report:
            return {"Header": {"ReportName": name, "Currency": "USD"},
                    "Rows": {"Row": []}}
        # Prior-period requests get deterministically scaled values (x0.85)
        # so comparative tools demo meaningfully instead of showing 0 deltas.
        from datetime import date as _date
        req_year = str((params or {}).get("start_date", ""))[:4]
        if req_year.isdigit() and int(req_year) < _date.today().year:
            import copy as _copy

            def _scale(node):
                if isinstance(node, dict):
                    if "value" in node and isinstance(node.get("value"), str):
                        try:
                            node["value"] = f"{float(node['value']) * 0.85:.2f}"
                        except ValueError:
                            pass
                    for v in node.values():
                        _scale(v)
                elif isinstance(node, list):
                    for v in node:
                        _scale(v)

            report = _copy.deepcopy(report)
            _scale(report.get("Rows", {}))
        return report

    entity = endpoint.split("/")[0].split("?")[0]
    entity_key = entity[:1].upper() + entity[1:]
    if method == "GET":  # entity read
        rows = _DEMO_QUERY_DATA.get(entity_key) or [{"Id": "9999"}]
        return {entity_key: rows[0]}

    # Writes: echo the payload back with demo identifiers
    return {entity_key: {**(json_body or {}), "Id": "9999",
                         "DocNumber": "DEMO-9999"}}


if _DEMO_MODE:
    logger.info("🎭 Running in DEMO MODE — returning mock data for all tools")


# ---------------------------------------------------------------------------
# Auth & HTTP helpers
# ---------------------------------------------------------------------------
async def get_access_token() -> str:
    ctx = get_ctx()

    # Return cached token if still valid
    if ctx.access_token and ctx.token_expiry and _utcnow() < _as_aware_utc(ctx.token_expiry):
        return ctx.access_token

    # Hosted mode: fetch fresh tokens from AccountingQB API (lazily on first
    # use — nothing is fetched at import time)
    if ctx.hosted_mode:
        logger.debug("Refreshing access token via AccountingQB API...")
        no_companies_connected = False
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{QB_API_URL}/api/oauth/token",
                    json={
                        "licenseKey": ctx.license_key or LICENSE_KEY,
                        "realmId": ctx.realm_id or None,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    companies = data.get("companies", [])
                    if companies:
                        ctx.hosted_companies = companies
                        ctx.hosted_loaded = True
                        if not ctx.realm_id:
                            # First use: default to the first connected company
                            ctx.realm_id = companies[0]["realmId"]
                        if ctx.persist_tokens:
                            _save_hosted_tokens(companies)
                        for company in companies:
                            if company["realmId"] == ctx.realm_id:
                                ctx.access_token = company["accessToken"]
                                ctx.refresh_token = company["refreshToken"]
                                ctx.token_expiry = _parse_token_expiry(company.get("expiresAt"))
                                return ctx.access_token
                    else:
                        # Broker reachable, license valid, but nothing connected
                        ctx.hosted_loaded = True
                        no_companies_connected = True
                elif resp.status_code == 404:
                    ctx.hosted_loaded = True
                    no_companies_connected = True
                if not no_companies_connected:
                    raise ValueError("Could not refresh token from AccountingQB API")
        except Exception as e:
            logger.warning(f"Hosted token refresh failed: {e}")
            # Offline resilience: fall back to cached hosted tokens, then to
            # local refresh if we have credentials
            if not ctx.hosted_companies:
                _load_hosted_tokens(ctx)
        if no_companies_connected:
            raise RuntimeError(_NO_COMPANY_CONNECTED_MSG)

    # Local mode: refresh directly with Intuit
    if not QB_CLIENT_ID or not QB_CLIENT_SECRET or not ctx.refresh_token:
        if ctx.hosted_mode:
            raise ValueError(
                "QuickBooks connection expired. Please reconnect at accountingqb.com"
            )
        raise ValueError(
            "QuickBooks credentials not configured. Set QB_CLIENT_ID, "
            "QB_CLIENT_SECRET, and QB_REFRESH_TOKEN environment variables."
        )

    logger.debug("Refreshing access token directly with Intuit...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(AUTH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": ctx.refresh_token,
            "client_id": QB_CLIENT_ID,
            "client_secret": QB_CLIENT_SECRET,
        }, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

    ctx.access_token = data["access_token"]
    ctx.token_expiry = _utcnow() + timedelta(seconds=data.get("expires_in", 3600) - 60)
    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != ctx.refresh_token:
        ctx.refresh_token = new_refresh
        if ctx.persist_tokens:
            os.environ["QB_REFRESH_TOKEN"] = new_refresh
            _save_token(new_refresh)
            logger.info("Refresh token rotated and saved (encrypted)")
    return ctx.access_token


def _raise_qb_fault(resp: httpx.Response) -> None:
    """Translate a QBO Fault payload into a friendly RuntimeError.

    Returns silently when the body isn't a recognizable QuickBooks Fault so
    the caller can fall back to raise_for_status().
    """
    try:
        fault = resp.json().get("Fault") or {}
        errors = fault.get("Error") or []
        first = errors[0]
        code = str(first.get("code", "")).strip()
        message = (first.get("Message") or "").strip()
        detail = (first.get("Detail") or "").strip()
    except Exception:
        return
    friendly = f"QuickBooks error {code}: {message} — {detail}"
    detail_upper = detail.upper()
    if code == "6000" and ("GST" in detail_upper or "HST" in detail_upper):
        friendly += (
            " Every line on this transaction needs a sales tax code. "
            "Use qb_list_tax_codes to see this company's codes, then pass "
            "tax_code to the create tool."
        )
    raise RuntimeError(friendly)


async def qb_request(method: str, endpoint: str, params: dict = None, json_body: dict = None) -> dict:
    if _demo_active():
        return _demo_response(method, endpoint, params, json_body)
    _check_rate_limit()
    ctx = get_ctx()
    token = await get_access_token()
    if QB_REPORTS_V2_TEST and endpoint.startswith("reports/"):
        params = {**(params or {}), "_testing_migration": "true"}
    url = f"{BASE_URL}/v3/company/{ctx.realm_id}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, params=params, json=json_body, headers=headers)
        if resp.status_code == 401:
            logger.warning("Got 401 — refreshing access token")
            ctx.access_token = None
            token = await get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, url, params=params, json=json_body, headers=headers)
        if resp.status_code == 429:
            logger.warning("QuickBooks API rate limit hit (429)")
            raise RuntimeError(
                "QuickBooks API rate limit reached. Please wait a moment and try again."
            )
        if resp.status_code >= 400:
            _raise_qb_fault(resp)
        resp.raise_for_status()
        return resp.json()


async def qb_query(query: str) -> dict:
    return await qb_request("GET", "query", params={"query": query})


async def qb_query_all(query: str, *, page_size: int = 1000,
                       max_records: int = 40_000) -> dict:
    """Run a QBO query and page through EVERY matching row.

    QuickBooks returns at most 1000 rows per response and paginates with a
    1-based STARTPOSITION cursor; a bare ``MAXRESULTS N`` silently truncates
    a large book, so any tool that totals or reconciles across all rows must
    page or it will understate. This strips whatever trailing
    STARTPOSITION/MAXRESULTS the caller wrote, walks all pages, and merges the
    entity arrays into one ``{"QueryResponse": {<Entity>: [...]}}`` with the
    same shape ``qb_query`` returns. ``max_records`` is a runaway guard.

    Use ``qb_query`` (not this) for deliberately bounded reads: ``MAXRESULTS 1``
    lookups, ``ORDERBY ... DESC`` recent-N previews, and user-controlled
    ``max_results`` limits."""
    import re as _re
    tail = _re.compile(r"\s+(?:STARTPOSITION\s+\d+|MAXRESULTS\s+\d+)\s*$",
                       _re.IGNORECASE)
    base = query.rstrip()
    while True:
        stripped = tail.sub("", base).rstrip()
        if stripped == base:
            break
        base = stripped
    page_size = max(1, min(page_size, 1000))
    merged: dict = {}
    meta: dict = {}
    pos = 1
    while True:
        resp = await qb_query(f"{base} STARTPOSITION {pos} MAXRESULTS {page_size}")
        qr = (resp or {}).get("QueryResponse", {}) or {}
        page_rows = 0
        for key, val in qr.items():
            if isinstance(val, list):
                merged.setdefault(key, []).extend(val)
                page_rows = max(page_rows, len(val))
            elif key not in meta:
                meta[key] = val
        total = sum(len(v) for v in merged.values())
        if page_rows < page_size or total >= max_records:
            break
        pos += page_size
    return {"QueryResponse": {**meta, **merged}}


async def qb_read(entity: str, entity_id: str) -> dict:
    # QBO resource paths are lowercase; "JournalEntry/1" returns a 400.
    return await qb_request("GET", f"{entity.lower()}/{entity_id}")


def _account_ambiguity_msg(name: str, hits: list) -> str:
    listed = ", ".join(
        f"{a.get('Name')} (ID:{a.get('Id')}, {a.get('AccountType')})"
        for a in hits[:10])
    more = "" if len(hits) <= 10 else f" (+{len(hits) - 10} more)"
    return (f"Multiple accounts match '{name}': {listed}{more}. Please be more "
            "specific — use the exact account name or the account ID.")


async def _resolve_account(acct_name: str, *, account_type: str = ""):
    """Resolve an Account by name — safely, never silently guessing.

    Returns ``(account_dict, None)`` on a single confident match, or
    ``(None, error_message)`` when nothing matches or the name is ambiguous.
    Resolution order: exact ``Name``, then exact ``FullyQualifiedName`` (for
    "Parent:Child"), then a ``LIKE`` fallback on the leaf name that REFUSES to
    pick when it matches more than one account. This is the fix for the
    silent-wrong-account bug where "Services" matched "Legal & accounting
    services" and posted revenue into an expense account. Pass ``account_type``
    to constrain the search (e.g. "Expense")."""
    name = (acct_name or "").strip()
    if not name:
        return None, "No account name was provided."
    esc = lambda s: s.replace("'", "\\'")
    tclause = f" AND AccountType = '{esc(account_type)}'" if account_type else ""

    async def _q(where):
        r = await qb_query(f"SELECT * FROM Account WHERE {where}{tclause} MAXRESULTS 25")
        return r.get("QueryResponse", {}).get("Account", [])

    # Exact matches are unambiguous intent — take a unique one immediately.
    for field in ("Name", "FullyQualifiedName"):
        hits = await _q(f"{field} = '{esc(name)}'")
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            return None, _account_ambiguity_msg(name, hits)

    # LIKE fallback on the leaf name — but refuse to guess between many.
    leaf = name.rsplit(":", 1)[-1]
    hits = await _q(f"Name LIKE '%{esc(leaf)}%'")
    if not hits:
        return None, (f"Account '{name}' not found. Use qb_list_accounts to see "
                      "available accounts, or pass the exact name / account ID.")
    if len(hits) == 1:
        return hits[0], None
    # A single case-insensitive exact leaf match wins over partial matches.
    exact = [a for a in hits if (a.get("Name") or "").lower() == leaf.lower()]
    if len(exact) == 1:
        return exact[0], None
    return None, _account_ambiguity_msg(name, hits)


def fmt(amount) -> str:
    if amount is None:
        return "$0.00"
    return f"${float(amount):,.2f}"


def fmt_signed(amount) -> str:
    """Accounting convention: negatives in parentheses, None as em dash."""
    if amount is None:
        return "—"
    v = float(amount)
    return f"(${abs(v):,.2f})" if v < 0 else f"${v:,.2f}"


def _parse_report_rows(rows, lines, indent=0):
    """Recursively parse QuickBooks report row structure."""
    for section in rows:
        header_data = section.get("Header", {})
        if header_data:
            cols = header_data.get("ColData", [])
            if cols:
                prefix = "###" if indent == 0 else "####"
                lines.append(f"\n{prefix} {cols[0].get('value', '')}")

        # Handle rows with ColData directly (leaf rows)
        col_data = section.get("ColData", [])
        if len(col_data) >= 2:
            rname = col_data[0].get("value", "")
            amount = col_data[-1].get("value", "0")
            pad = "  " * (indent + 1)
            try:
                lines.append(f"{pad}{rname}: {fmt(float(amount))}")
            except (ValueError, TypeError):
                lines.append(f"{pad}{rname}: {amount}")

        # Recurse into nested rows
        nested = section.get("Rows", {}).get("Row", [])
        if nested:
            _parse_report_rows(nested, lines, indent + 1)

        summary = section.get("Summary", {})
        if summary:
            cols = summary.get("ColData", [])
            if len(cols) >= 2:
                try:
                    lines.append(f"**{cols[0].get('value', '')}: {fmt(float(cols[-1].get('value', '0')))}**")
                except (ValueError, TypeError):
                    lines.append(f"**{cols[0].get('value', '')}: {cols[-1].get('value', '')}**")


def _fmt_report_cells(vals, ncols, bold=False):
    """Pad/truncate a report row to ncols and render as a markdown table row."""
    out = [str(v).replace("|", "\\|") for v in vals]
    out = (out + [""] * ncols)[:ncols]
    if bold:
        out = [f"**{v}**" if v else "" for v in out]
    return "| " + " | ".join(out) + " |"


def _format_report_table(report, lines, max_rows=400):
    """Render a QuickBooks report as a full multi-column markdown table.

    Unlike _parse_report_rows (which keeps only the first + last column, right
    for summary statements), this preserves every column — needed for detail and
    transaction reports (ProfitAndLossDetail, TransactionList, *BalanceDetail)
    whose value is the per-line columns. Group headers and section summaries are
    bolded; leaf rows are capped at max_rows with a truncation note."""
    cols = [c.get("ColTitle", "") or "—"
            for c in report.get("Columns", {}).get("Column", [])]
    n = len(cols)
    if n < 2:  # no column metadata — fall back to the summary parser
        _parse_report_rows(report.get("Rows", {}).get("Row", []), lines)
        return
    lines.append(_fmt_report_cells(cols, n))
    lines.append("|" + "|".join(["---"] * n) + "|")
    state = {"count": 0, "truncated": False}

    def walk(rows):
        for sec in rows:
            hdr = sec.get("Header", {}).get("ColData", [])
            if hdr and hdr[0].get("value", ""):
                lines.append(_fmt_report_cells([hdr[0].get("value", "")], n, bold=True))
            cd = sec.get("ColData", [])
            if cd:
                if state["count"] >= max_rows:
                    state["truncated"] = True
                else:
                    lines.append(_fmt_report_cells([c.get("value", "") for c in cd], n))
                    state["count"] += 1
            nested = sec.get("Rows", {}).get("Row", [])
            if nested:
                walk(nested)
            summ = sec.get("Summary", {}).get("ColData", [])
            if summ and any(c.get("value", "") for c in summ):
                lines.append(_fmt_report_cells([c.get("value", "") for c in summ], n, bold=True))

    walk(report.get("Rows", {}).get("Row", []))
    if state["truncated"]:
        lines.append(f"\n*Showing the first {max_rows} rows — narrow the date "
                     "range or add a filter to see the rest.*")


# ===================================================================
# REGION / TAX EDITION DETECTION — Canada & global tax editions
# ===================================================================
# US companies use Automated Sales Tax (QBO computes tax; never send
# GlobalTaxCalculation or inject TaxCodeRef). Canadian and other
# global-tax companies REQUIRE a TaxCodeRef on every line of sales and
# purchase documents and accept a GlobalTaxCalculation header.

_US_REGION_INFO = {"region": "US", "home_currency": "USD", "multicurrency": False,
                   "subdivision": ""}

_TAX_CODE_REQUIRED_MSG = (
    "This company requires a sales tax code on every line. "
    "Run qb_list_tax_codes to see available codes (e.g. \"HST ON\"), "
    "then pass tax_code=..."
)


async def _get_region() -> dict:
    """Detect this company's tax edition, cached per realm.

    Returns {"region": "US" | "CA" | "OTHER_GLOBAL", "home_currency": str,
    "multicurrency": bool, "subdivision": str}. "subdivision" is the
    province/state code from the company address ("ON", "TX", ...) or "".
    Cached in the connection's region_cache keyed by realm_id (switching
    companies therefore re-detects naturally). On any API error falls back
    to the US defaults so existing users are never broken.
    """
    ctx = get_ctx()
    key = ctx.realm_id or "_default"
    cached = ctx.region_cache.get(key)
    if cached:
        return cached

    if _demo_active():
        info = dict(_US_REGION_INFO)
        info["subdivision"] = DEMO_COMPANY["CompanyAddr"]["CountrySubDivisionCode"]
        ctx.region_cache[key] = info
        return info

    try:
        result = await qb_query("SELECT * FROM CompanyInfo")
        company = result.get("QueryResponse", {}).get("CompanyInfo", [{}])[0]
        country = (company.get("Country") or "").strip().upper()
    except Exception as e:
        logger.debug(f"Region detection failed (CompanyInfo): {e}")
        return dict(_US_REGION_INFO)  # do not cache failures

    addr = company.get("CompanyAddr") or company.get("LegalAddr") or {}
    subdivision = (
        (company.get("CountrySubDivisionCode") or addr.get("CountrySubDivisionCode") or "")
        .strip().upper()
    )

    info = {"region": "US", "home_currency": "", "multicurrency": False,
            "subdivision": subdivision}
    partner_tax = None
    try:
        prefs = (await qb_request("GET", "preferences")).get("Preferences", {})
        # PartnerTaxEnabled=true means US Automated Sales Tax
        partner_tax = (prefs.get("TaxPrefs") or {}).get("PartnerTaxEnabled")
        currency = prefs.get("CurrencyPrefs") or {}
        info["multicurrency"] = bool(currency.get("MultiCurrencyEnabled"))
        info["home_currency"] = (currency.get("HomeCurrency") or {}).get("value") or ""
    except Exception as e:
        logger.debug(f"Region detection: preferences unavailable: {e}")

    if country == "US" or partner_tax is True:
        info["region"] = "US"
    elif country == "CA":
        info["region"] = "CA"
    elif country:
        info["region"] = "OTHER_GLOBAL"
    else:
        info["region"] = "US"  # indeterminate — safest default

    if not info["home_currency"]:
        info["home_currency"] = "CAD" if info["region"] == "CA" else "USD"

    ctx.region_cache[key] = info
    return info


def require_region(region: str, alternative: str):
    """Decorator factory gating a tool to one tax region (cf. require_license).

    Apply between @mcp.tool and the function definition so the check runs on
    every call, and license gating (_apply_license_gating wraps the registered
    tool.fn at import time) still stacks on top.
    """
    def decorator(func):
        tool_name = func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            detected = (await _get_region())["region"]
            if detected != region:
                return (
                    f"⚠️ {tool_name} is a {region}-tax tool and this QuickBooks "
                    f"company is registered in {detected}. {alternative}"
                )
            return await func(*args, **kwargs)

        return wrapper
    return decorator


async def _resolve_tax_code(name_or_id: str) -> tuple[str, str]:
    """Resolve a tax code Name (or bare numeric Id) to (Id, Name).

    Matches active TaxCodes case-insensitively on exact Name first, then by
    substring. Raises ValueError listing available names when nothing matches.
    """
    result = await qb_query_all(
        "SELECT Id, Name FROM TaxCode WHERE Active = true MAXRESULTS 1000"
    )
    codes = result.get("QueryResponse", {}).get("TaxCode", [])
    wanted = (name_or_id or "").strip()

    if wanted.isdigit():
        for tc in codes:
            if str(tc.get("Id", "")) == wanted:
                return tc["Id"], tc.get("Name", wanted)

    lowered = wanted.lower()
    if lowered:
        for tc in codes:
            if tc.get("Name", "").lower() == lowered:
                return tc["Id"], tc["Name"]
        for tc in codes:
            if lowered in tc.get("Name", "").lower():
                return tc["Id"], tc["Name"]

    names = ", ".join(sorted(tc.get("Name", "?") for tc in codes)) or "(none found)"
    raise ValueError(
        f"Tax code '{name_or_id}' not found. Available tax codes: {names}. "
        "Run qb_list_tax_codes for rates and details."
    )


def _apply_global_tax(body: dict, lines_key: str, detail_key: str,
                      tax_code_id, tax_inclusive: bool, region: str) -> dict:
    """Add GlobalTaxCalculation + per-line TaxCodeRef for non-US tax editions.

    US companies (Automated Sales Tax) are returned unchanged. Lines that
    already carry a TaxCodeRef keep it (setdefault).
    """
    if region == "US":
        return body
    body["GlobalTaxCalculation"] = "TaxInclusive" if tax_inclusive else "TaxExcluded"
    if tax_code_id:
        for line in body.get(lines_key, []):
            if line.get("DetailType") == detail_key and isinstance(line.get(detail_key), dict):
                line[detail_key].setdefault("TaxCodeRef", {"value": str(tax_code_id)})
    return body


async def _line_tax_code_ref(item: dict, region: str, cache: dict):
    """TaxCodeRef for one parsed JSON line item, or None.

    Supports an explicit "TaxCodeRef" dict or a per-line "tax_code" name/Id
    (each distinct name resolved once via `cache`). US region: always None.
    """
    if region == "US" or not isinstance(item, dict):
        return None
    explicit = item.get("TaxCodeRef")
    if isinstance(explicit, dict) and explicit.get("value"):
        return explicit
    name = str(item.get("tax_code", "") or "").strip()
    if not name:
        return None
    if name not in cache:
        cache[name] = (await _resolve_tax_code(name))[0]
    return {"value": cache[name]}


async def _multicurrency_enabled() -> bool:
    """True when this company has multicurrency turned on.

    Reads the per-realm region cache when populated; otherwise detects lazily
    via _get_region() (which caches), so this costs at most one detection per
    session and nothing extra for companies already detected."""
    ctx = get_ctx()
    cached = ctx.region_cache.get(ctx.realm_id or "_default")
    if cached is not None:
        return bool(cached.get("multicurrency"))
    try:
        return bool((await _get_region()).get("multicurrency"))
    except Exception:
        return False


def _txn_currency_tag(txn: dict) -> str:
    """Compact currency suffix (e.g. ' [USD @1.37]') for multicurrency books."""
    code = ((txn.get("CurrencyRef") or {}).get("value") or "").strip()
    if not code:
        return ""
    rate = txn.get("ExchangeRate")
    try:
        if rate not in (None, "") and float(rate) != 1.0:
            return f" [{code} @{float(rate):g}]"
    except (ValueError, TypeError):
        pass
    return f" [{code}]"


# ===================================================================
# HOSTED MODE — Company Management
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_companies() -> str:
    """List all QuickBooks companies connected to your AccountingQB license.
    Only available in hosted mode (when using AccountingQB Desktop Extension)."""
    # Demo mode: show demo company
    if _demo_active():
        return (
            "## Connected QuickBooks Companies\n\n"
            "🎭 *Demo Mode — Sample Data*\n\n"
            "1. **Acme Consulting LLC** ✓ (active)\n"
            "   - Realm ID: `DEMO-123456789`\n\n"
            "*This is a demo account with sample data.*"
        )

    ctx = get_ctx()
    if not ctx.hosted_mode:
        return (
            "This tool is only available in hosted mode.\n\n"
            "If you're using the AccountingQB Desktop Extension, make sure you've "
            "connected your QuickBooks account at accountingqb.com"
        )

    # Lazy hosted mode: fetch the company list on first use
    if not ctx.hosted_loaded:
        _fetch_hosted_tokens(ctx)

    if not ctx.hosted_companies:
        return (
            "No QuickBooks companies connected yet.\n\n"
            "Visit accountingqb.com to connect your QuickBooks account."
        )

    lines = ["## Connected QuickBooks Companies\n"]
    for i, company in enumerate(ctx.hosted_companies):
        current = " ✓ (active)" if company["realmId"] == ctx.realm_id else ""
        name = company.get("companyName") or company["realmId"]
        lines.append(f"{i + 1}. **{name}**{current}")
        lines.append(f"   - Realm ID: `{company['realmId']}`")

    lines.append(f"\n*Use `qb_switch_company` to switch between companies.*")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_switch_company(realm_id: str) -> str:
    """Switch to a different QuickBooks company. Use qb_list_companies to see available companies.
    Only available in hosted mode (when using AccountingQB Desktop Extension)."""
    ctx = get_ctx()
    if not ctx.hosted_mode:
        return "This tool is only available in hosted mode."

    # Lazy hosted mode: fetch the company list on first use
    if not ctx.hosted_loaded:
        _fetch_hosted_tokens(ctx)

    # Find the company
    for company in ctx.hosted_companies:
        if company["realmId"] == realm_id:
            ctx.realm_id = company["realmId"]
            ctx.refresh_token = company["refreshToken"]
            ctx.access_token = company.get("accessToken")
            if ctx.access_token:
                ctx.token_expiry = _parse_token_expiry(company.get("expiresAt"))
            else:
                ctx.token_expiry = None
            name = company.get("companyName") or realm_id
            # Remote (stateless) mode: persist the choice so the next request
            # — which gets a fresh QBContext — resumes on the same company.
            if not ctx.persist_tokens and ctx.license_key:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"{QB_API_URL}/api/license/default-realm",
                            json={"license_key": ctx.license_key, "realmId": realm_id},
                        )
                except Exception as e:
                    logger.warning(f"Could not persist default realm: {e}")
                    return (
                        f"✓ Switched to **{name}** (Realm ID: `{realm_id}`) for this "
                        f"request, but the choice could not be saved — it may reset "
                        f"on your next message."
                    )
            return f"✓ Switched to **{name}** (Realm ID: `{realm_id}`)"

    return f"Company with realm ID `{realm_id}` not found. Use `qb_list_companies` to see available companies."


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_refresh_connection() -> str:
    """Refresh the connection to AccountingQB servers. Use this if you've connected
    new QuickBooks companies or if you're having connection issues."""
    if not _effective_license_key():
        return "No license key configured. This tool is only available in hosted mode."

    ctx = get_ctx()
    ctx.region_cache.clear()  # force re-detection of tax edition per realm
    if _fetch_hosted_tokens(ctx):
        count = len(ctx.hosted_companies)
        return f"✓ Connection refreshed. {count} company(s) connected."
    else:
        return (
            "Could not refresh connection. Please check:\n"
            "- Your internet connection\n"
            "- Your license key is valid\n"
            "- You've connected QuickBooks at accountingqb.com"
        )


# ===================================================================
# COMPANY INFO
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_company_info() -> str:
    """Get QuickBooks company information including name, address, fiscal year, and subscription status."""
    # Demo mode: return mock company data
    if _demo_active():
        info = DEMO_COMPANY
        lines = ["## QuickBooks Company Info\n", "🎭 *Demo Mode — Sample Data*\n"]
    else:
        result = await qb_query("SELECT * FROM CompanyInfo")
        info = result.get("QueryResponse", {}).get("CompanyInfo", [{}])[0]
        lines = ["## QuickBooks Company Info\n"]
    lines.append(f"- **Company:** {info.get('CompanyName', 'N/A')}")
    lines.append(f"- **Legal Name:** {info.get('LegalName', 'N/A')}")
    # Canadian companies call their federal tax id a Business Number (BN)
    tax_id_label = (
        "Business Number (BN)"
        if (info.get("Country") or "").strip().upper() == "CA" else "EIN"
    )
    lines.append(f"- **{tax_id_label}:** {info.get('EmployerId', info.get('EIN', 'N/A'))}")
    lines.append(f"- **Industry:** {info.get('IndustryType', 'Consulting')}")
    lines.append(f"- **Fiscal Year Start:** {info.get('FiscalYearStartMonth', 'N/A')}")
    addr = info.get("CompanyAddr", {})
    if addr:
        lines.append(f"- **Address:** {addr.get('Line1', '')} {addr.get('City', '')}, {addr.get('CountrySubDivisionCode', '')} {addr.get('PostalCode', '')}")
    email = info.get("Email", {}).get("Address", "")
    if email:
        lines.append(f"- **Email:** {email}")
    phone = info.get("PrimaryPhone", {}).get("FreeFormNumber", "")
    if phone:
        lines.append(f"- **Phone:** {phone}")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Purchases / Expenses
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_transactions(start_date: str, end_date: str, vendor_name: str = "", min_amount: float = 0, max_amount: float = 0, max_results: int = 100) -> str:
    """List QuickBooks transactions (purchases, expenses) within a date range. Dates in YYYY-MM-DD format. Optionally filter by vendor_name, min_amount, max_amount."""
    # Demo mode: return mock transactions
    if _demo_active():
        purchases = DEMO_TRANSACTIONS[:max_results]
    else:
        query = (
            f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
            f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
        )
        result = await qb_query(query)
        purchases = result.get("QueryResponse", {}).get("Purchase", [])

    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    show_currency = await _multicurrency_enabled()
    lines = [f"## Transactions: {start_date} to {end_date}\n"]
    total = 0.0
    count = 0
    for p in purchases:
        amt = float(p.get("TotalAmt", 0))
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        date = p.get("TxnDate", "N/A")
        memo = p.get("PrivateNote", "")
        pay_type = p.get("PaymentType", "")
        acct = p.get("AccountRef", {}).get("name", "")

        if min_amount and amt < min_amount:
            continue
        if max_amount and amt > max_amount:
            continue
        if vendor_name and vendor_name.lower() not in vendor.lower():
            continue

        total += amt
        count += 1
        detail_lines = []
        for line in p.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                cat = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
                detail_lines.append(f"  - {cat}: {fmt(line.get('Amount'))}")

        cur = _txn_currency_tag(p) if show_currency else ""
        lines.append(f"**{date}** | {vendor} | {fmt(amt)}{cur} | ID: {p.get('Id', '')}")
        if pay_type or acct:
            lines.append(f"  Payment: {pay_type} via {acct}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.extend(detail_lines)
        lines.append("")

    lines.append(f"\n**Total: {fmt(total)} ({count} transactions)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Deposits
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_deposits(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List deposits (income, owner investments, bank deposits) within a date range. Dates in YYYY-MM-DD (default: current year-to-date). Use this to find income or money deposited into business accounts."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM Deposit WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    deposits = result.get("QueryResponse", {}).get("Deposit", [])

    if not deposits:
        return f"No deposits found between {start_date} and {end_date}."

    lines = [f"## Deposits: {start_date} to {end_date}\n"]
    total = 0.0
    for d in deposits:
        amt = float(d.get("TotalAmt", 0))
        date = d.get("TxnDate", "N/A")
        acct = d.get("DepositToAccountRef", {}).get("name", "Unknown")
        memo = d.get("PrivateNote", "")
        total += amt

        detail_lines = []
        for line in d.get("Line", []):
            detail = line.get("DepositLineDetail", {})
            from_acct = detail.get("AccountRef", {}).get("name", "")
            from_name = detail.get("Entity", {}).get("name", "")
            line_amt = line.get("Amount", 0)
            desc = line.get("Description", "")
            source = from_name or from_acct or "Unknown source"
            detail_lines.append(f"  - {source}: {fmt(line_amt)}" + (f" ({desc})" if desc else ""))

        lines.append(f"**{date}** | {fmt(amt)} → {acct} | ID: {d.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.extend(detail_lines)
        lines.append("")

    lines.append(f"\n**Total Deposits: {fmt(total)} ({len(deposits)} deposits)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Transfers
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_transfers(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List transfers between accounts within a date range. Dates in YYYY-MM-DD (default: current year-to-date). Use this to see money moved between business bank accounts or credit cards."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM Transfer WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    transfers = result.get("QueryResponse", {}).get("Transfer", [])

    if not transfers:
        return f"No transfers found between {start_date} and {end_date}."

    lines = [f"## Transfers: {start_date} to {end_date}\n"]
    total = 0.0
    for t in transfers:
        amt = float(t.get("Amount", 0))
        date = t.get("TxnDate", "N/A")
        from_acct = t.get("FromAccountRef", {}).get("name", "Unknown")
        to_acct = t.get("ToAccountRef", {}).get("name", "Unknown")
        memo = t.get("PrivateNote", "")
        total += amt

        lines.append(f"**{date}** | {fmt(amt)} | {from_acct} → {to_acct} | ID: {t.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.append("")

    lines.append(f"\n**Total Transfers: {fmt(total)} ({len(transfers)} transfers)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Journal Entries
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_journal_entries(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List journal entries (adjustments, reclassifications) within a date range. Dates in YYYY-MM-DD (default: current year-to-date). Useful for finding accounting adjustments, corrections, and manual entries."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM JournalEntry WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    entries = result.get("QueryResponse", {}).get("JournalEntry", [])

    if not entries:
        return f"No journal entries found between {start_date} and {end_date}."

    lines = [f"## Journal Entries: {start_date} to {end_date}\n"]
    for je in entries:
        date = je.get("TxnDate", "N/A")
        total = float(je.get("TotalAmt", 0))
        memo = je.get("PrivateNote", "")
        doc = je.get("DocNumber", "")
        adj = je.get("Adjustment", False)

        lines.append(f"**{date}** | {fmt(total)} | ID: {je.get('Id', '')}" + (f" | Doc#: {doc}" if doc else "") + (" [ADJUSTMENT]" if adj else ""))
        if memo:
            lines.append(f"  Memo: {memo}")

        for line in je.get("Line", []):
            detail = line.get("JournalEntryLineDetail", {})
            acct = detail.get("AccountRef", {}).get("name", "")
            posting = detail.get("PostingType", "")
            amt = line.get("Amount", 0)
            desc = line.get("Description", "")
            entity = detail.get("Entity", {}).get("name", "")
            lines.append(f"  - {posting} {acct}: {fmt(amt)}" + (f" ({entity})" if entity else "") + (f" — {desc}" if desc else ""))
        lines.append("")

    lines.append(f"**{len(entries)} journal entries found**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Bills (Accounts Payable)
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_bills(start_date: str, end_date: str, vendor_name: str = "", max_results: int = 100) -> str:
    """List bills (accounts payable) within a date range. Dates in YYYY-MM-DD. Optionally filter by vendor_name. Shows what you owe to vendors."""
    query = f"SELECT * FROM Bill WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if vendor_name:
        query += f" AND VendorRef LIKE '%{vendor_name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    bills = result.get("QueryResponse", {}).get("Bill", [])

    if not bills:
        return f"No bills found between {start_date} and {end_date}."

    show_currency = await _multicurrency_enabled()
    lines = [f"## Bills: {start_date} to {end_date}\n"]
    total = 0.0
    total_balance = 0.0
    for b in bills:
        amt = float(b.get("TotalAmt", 0))
        balance = float(b.get("Balance", 0))
        vendor = b.get("VendorRef", {}).get("name", "Unknown")
        date = b.get("TxnDate", "N/A")
        due = b.get("DueDate", "N/A")
        memo = b.get("PrivateNote", "")
        total += amt
        total_balance += balance

        status = "PAID" if balance == 0 else f"DUE: {fmt(balance)}"
        cur = _txn_currency_tag(b) if show_currency else ""
        lines.append(f"**{date}** | {vendor} | {fmt(amt)}{cur} | {status} | Due: {due} | ID: {b.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")

        for line in b.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                cat = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
                lines.append(f"  - {cat}: {fmt(line.get('Amount'))}")
        lines.append("")

    lines.append(f"\n**Total Billed: {fmt(total)} | Outstanding: {fmt(total_balance)} ({len(bills)} bills)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Bill Payments
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_bill_payments(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List bill payments within a date range. Dates in YYYY-MM-DD (default: current year-to-date). Shows payments made against bills (accounts payable)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM BillPayment WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    payments = result.get("QueryResponse", {}).get("BillPayment", [])

    if not payments:
        return f"No bill payments found between {start_date} and {end_date}."

    lines = [f"## Bill Payments: {start_date} to {end_date}\n"]
    total = 0.0
    for bp in payments:
        amt = float(bp.get("TotalAmt", 0))
        vendor = bp.get("VendorRef", {}).get("name", "Unknown")
        date = bp.get("TxnDate", "N/A")
        pay_type = bp.get("PayType", "")
        total += amt

        acct_name = ""
        if pay_type == "Check":
            acct_name = bp.get("CheckPayment", {}).get("BankAccountRef", {}).get("name", "")
        elif pay_type == "CreditCard":
            acct_name = bp.get("CreditCardPayment", {}).get("CCAccountRef", {}).get("name", "")

        lines.append(f"**{date}** | {vendor} | {fmt(amt)} | {pay_type} via {acct_name} | ID: {bp.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Paid: {fmt(total)} ({len(payments)} payments)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Sales Receipts
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_sales_receipts(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List sales receipts (direct sales, not invoiced) within a date range. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    receipts = result.get("QueryResponse", {}).get("SalesReceipt", [])

    if not receipts:
        return f"No sales receipts found between {start_date} and {end_date}."

    lines = [f"## Sales Receipts: {start_date} to {end_date}\n"]
    total = 0.0
    for sr in receipts:
        amt = float(sr.get("TotalAmt", 0))
        customer = sr.get("CustomerRef", {}).get("name", "Walk-in")
        date = sr.get("TxnDate", "N/A")
        doc = sr.get("DocNumber", "")
        total += amt

        lines.append(f"**{date}** | {customer} | {fmt(amt)} | ID: {sr.get('Id', '')}" + (f" | #{doc}" if doc else ""))
        for line in sr.get("Line", []):
            desc = line.get("Description", "")
            line_amt = line.get("Amount", 0)
            if desc and line_amt:
                lines.append(f"  - {desc}: {fmt(line_amt)}")
        lines.append("")

    lines.append(f"\n**Total Sales: {fmt(total)} ({len(receipts)} receipts)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Customer Payments
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_payments(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """List customer payments received within a date range. Dates in YYYY-MM-DD (default: current year-to-date). Shows payments applied against invoices."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM Payment WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    payments = result.get("QueryResponse", {}).get("Payment", [])

    if not payments:
        return f"No customer payments found between {start_date} and {end_date}."

    lines = [f"## Customer Payments: {start_date} to {end_date}\n"]
    total = 0.0
    for p in payments:
        amt = float(p.get("TotalAmt", 0))
        customer = p.get("CustomerRef", {}).get("name", "Unknown")
        date = p.get("TxnDate", "N/A")
        deposit_acct = p.get("DepositToAccountRef", {}).get("name", "Undeposited")
        total += amt

        lines.append(f"**{date}** | {customer} | {fmt(amt)} → {deposit_acct} | ID: {p.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Received: {fmt(total)} ({len(payments)} payments)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Invoices
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_invoices(start_date: str, end_date: str, customer_name: str = "", status: str = "", max_results: int = 100) -> str:
    """List invoices within a date range. Dates in YYYY-MM-DD. Filter by customer_name and/or status (Paid, Unpaid, Overdue). Shows accounts receivable."""
    # Demo mode: return mock invoices
    if _demo_active():
        invoices = DEMO_INVOICES[:max_results]
    else:
        query = f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
        query += f" MAXRESULTS {max_results}"
        result = await qb_query(query)
        invoices = result.get("QueryResponse", {}).get("Invoice", [])

    if not invoices:
        return f"No invoices found between {start_date} and {end_date}."

    show_currency = await _multicurrency_enabled()
    lines = [f"## Invoices: {start_date} to {end_date}\n"]
    total = 0.0
    total_balance = 0.0
    count = 0
    for inv in invoices:
        customer = inv.get("CustomerRef", {}).get("name", "Unknown")
        if customer_name and customer_name.lower() not in customer.lower():
            continue

        amt = float(inv.get("TotalAmt", 0))
        balance = float(inv.get("Balance", 0))
        date = inv.get("TxnDate", "N/A")
        due = inv.get("DueDate", "N/A")
        doc = inv.get("DocNumber", "")

        inv_status = "PAID" if balance == 0 else "UNPAID"
        if balance > 0 and due != "N/A":
            try:
                if datetime.strptime(due, "%Y-%m-%d") < datetime.now():
                    inv_status = "OVERDUE"
            except ValueError:
                pass

        # "unpaid" means any open balance — overdue invoices are still unpaid
        want = status.lower()
        if want == "unpaid":
            if balance <= 0:
                continue
        elif want and want != inv_status.lower():
            continue

        total += amt
        total_balance += balance
        count += 1

        cur = _txn_currency_tag(inv) if show_currency else ""
        lines.append(f"**{date}** | #{doc} | {customer} | {fmt(amt)}{cur} | {inv_status} | Due: {due} | ID: {inv.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Invoiced: {fmt(total)} | Outstanding: {fmt(total_balance)} ({count} invoices)**")
    return "\n".join(lines)


# ===================================================================
# UNIVERSAL TRANSACTION SEARCH
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_search_transactions(start_date: str, end_date: str, search_term: str = "", max_results: int = 50) -> str:
    """Search across ALL transaction types (purchases, deposits, transfers, journal entries, bills, payments, invoices, sales receipts) in a date range. Optionally filter by search_term (matches vendor, customer, memo, account names). Dates in YYYY-MM-DD."""
    all_txns = []
    term = search_term.lower()

    entity_configs = [
        ("Purchase", "Purchase", lambda p: {
            "type": "Purchase", "id": p.get("Id"), "date": p.get("TxnDate", ""),
            "amount": float(p.get("TotalAmt", 0)),
            "entity": p.get("EntityRef", {}).get("name", ""),
            "memo": p.get("PrivateNote", ""),
            "account": p.get("AccountRef", {}).get("name", ""),
        }),
        ("Deposit", "Deposit", lambda d: {
            "type": "Deposit", "id": d.get("Id"), "date": d.get("TxnDate", ""),
            "amount": float(d.get("TotalAmt", 0)),
            "entity": ", ".join(
                line.get("DepositLineDetail", {}).get("Entity", {}).get("name", "")
                for line in d.get("Line", []) if line.get("DepositLineDetail", {}).get("Entity", {}).get("name")
            ) or "N/A",
            "memo": d.get("PrivateNote", ""),
            "account": d.get("DepositToAccountRef", {}).get("name", ""),
        }),
        ("Transfer", "Transfer", lambda t: {
            "type": "Transfer", "id": t.get("Id"), "date": t.get("TxnDate", ""),
            "amount": float(t.get("Amount", 0)),
            "entity": f"{t.get('FromAccountRef', {}).get('name', '')} → {t.get('ToAccountRef', {}).get('name', '')}",
            "memo": t.get("PrivateNote", ""),
            "account": "",
        }),
        ("JournalEntry", "JournalEntry", lambda j: {
            "type": "Journal Entry", "id": j.get("Id"), "date": j.get("TxnDate", ""),
            "amount": float(j.get("TotalAmt", 0)),
            "entity": ", ".join(
                line.get("JournalEntryLineDetail", {}).get("AccountRef", {}).get("name", "")
                for line in j.get("Line", []) if line.get("JournalEntryLineDetail", {}).get("AccountRef", {}).get("name")
            ),
            "memo": j.get("PrivateNote", ""),
            "account": "",
        }),
        ("Bill", "Bill", lambda b: {
            "type": "Bill", "id": b.get("Id"), "date": b.get("TxnDate", ""),
            "amount": float(b.get("TotalAmt", 0)),
            "entity": b.get("VendorRef", {}).get("name", ""),
            "memo": b.get("PrivateNote", ""),
            "account": "",
        }),
        ("Invoice", "Invoice", lambda i: {
            "type": "Invoice", "id": i.get("Id"), "date": i.get("TxnDate", ""),
            "amount": float(i.get("TotalAmt", 0)),
            "entity": i.get("CustomerRef", {}).get("name", ""),
            "memo": i.get("PrivateNote", ""),
            "account": "",
        }),
        ("Payment", "Payment", lambda p: {
            "type": "Payment", "id": p.get("Id"), "date": p.get("TxnDate", ""),
            "amount": float(p.get("TotalAmt", 0)),
            "entity": p.get("CustomerRef", {}).get("name", ""),
            "memo": p.get("PrivateNote", ""),
            "account": p.get("DepositToAccountRef", {}).get("name", ""),
        }),
        ("SalesReceipt", "SalesReceipt", lambda s: {
            "type": "Sales Receipt", "id": s.get("Id"), "date": s.get("TxnDate", ""),
            "amount": float(s.get("TotalAmt", 0)),
            "entity": s.get("CustomerRef", {}).get("name", ""),
            "memo": s.get("PrivateNote", ""),
            "account": "",
        }),
    ]

    for qb_entity, response_key, transform in entity_configs:
        try:
            q = f"SELECT * FROM {qb_entity} WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
            res = await qb_query(q)
            items = res.get("QueryResponse", {}).get(response_key, [])
            for item in items:
                txn = transform(item)
                if not term or any(term in str(v).lower() for v in txn.values()):
                    all_txns.append(txn)
        except Exception:
            pass  # Some entity types may not be available

    all_txns.sort(key=lambda x: x.get("date", ""), reverse=True)

    if not all_txns:
        msg = f"No transactions found between {start_date} and {end_date}"
        if search_term:
            msg += f" matching '{search_term}'"
        return msg + "."

    lines = [f"## All Transactions: {start_date} to {end_date}"]
    if search_term:
        lines[0] += f" (filter: '{search_term}')"
    lines.append("")

    total = sum(t["amount"] for t in all_txns)
    for txn in all_txns[:max_results]:
        lines.append(f"**{txn['date']}** | [{txn['type']}] {txn['entity']} | {fmt(txn['amount'])} | ID: {txn['id']}")
        if txn.get("memo"):
            lines.append(f"  Memo: {txn['memo']}")

    lines.append(f"\n**{len(all_txns)} transactions | Total: {fmt(total)}**")
    return "\n".join(lines)


# ===================================================================
# EXPENSE SUMMARY
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_expense_summary(start_date: str = "", end_date: str = "") -> str:
    """Get expenses grouped by category/account for a date range. Useful for Schedule C and tax deduction tracking. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    query = (
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    result = await qb_query_all(query)
    purchases = result.get("QueryResponse", {}).get("Purchase", [])

    categories = {}
    vendor_totals = {}
    grand_total = 0.0

    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        for line in p.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "Uncategorized")
                amt = float(line.get("Amount", 0))
                categories.setdefault(acct, 0.0)
                categories[acct] += amt
                vendor_totals.setdefault(vendor, 0.0)
                vendor_totals[vendor] += amt
                grand_total += amt

    lines = [f"## Expense Summary: {start_date} to {end_date}\n"]
    lines.append("### By Category")
    for cat in sorted(categories, key=categories.get, reverse=True):
        lines.append(f"- **{cat}**: {fmt(categories[cat])}")

    lines.append(f"\n### Top Vendors")
    for v in sorted(vendor_totals, key=vendor_totals.get, reverse=True)[:20]:
        lines.append(f"- {v}: {fmt(vendor_totals[v])}")

    lines.append(f"\n**Grand Total: {fmt(grand_total)}**")
    return "\n".join(lines)


# ===================================================================
# REPORTS — Profit & Loss
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_profit_loss(start_date: str = "", end_date: str = "", summarize_by: str = "Total", basis: str = "") -> str:
    """Generate a Profit & Loss (Income Statement) report. Dates in YYYY-MM-DD
    (default: current year-to-date). summarize_by: Total, Month, Quarter, Year.
    basis: '' (QuickBooks default), 'cash', or 'accrual' — CPAs often book on
    accrual but file on cash."""
    start_date, end_date = _ytd_range(start_date, end_date)
    # Demo mode: return mock P&L
    if _demo_active():
        return (
            f"## Profit & Loss: {start_date} to {end_date}\n\n"
            "🎭 *Demo Mode — Sample Data*\n\n"
            "### Income\n"
            "| Category | Amount |\n"
            "|----------|--------|\n"
            "| Consulting Revenue | $145,000.00 |\n"
            "| Software Revenue | $42,500.00 |\n"
            "| **Total Income** | **$187,500.00** |\n\n"
            "### Expenses\n"
            "| Category | Amount |\n"
            "|----------|--------|\n"
            "| Software & Subscriptions | $12,500.00 |\n"
            "| Rent | $13,500.00 |\n"
            "| Travel | $8,750.00 |\n"
            "| Office Supplies | $2,500.00 |\n"
            "| Professional Services | $7,500.00 |\n"
            "| Advertising | $4,000.00 |\n"
            "| **Total Expenses** | **$48,750.00** |\n\n"
            "### Net Income: **$138,750.00**"
        )

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "summarize_column_by": summarize_by,
    }
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    header = report.get("Header", {})
    basis_note = f" · {method} basis" if method else ""
    lines = [f"## Profit & Loss: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}{basis_note}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Balance Sheet
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_balance_sheet(as_of_date: str = "", basis: str = "") -> str:
    """Generate a Balance Sheet report as of a specific date. Date in YYYY-MM-DD
    format (defaults to today). basis: '' (QuickBooks default), 'cash', or
    'accrual'."""
    as_of_date = _as_of_or_today(as_of_date)
    # Demo mode: return mock balance sheet
    if _demo_active():
        return (
            f"## Balance Sheet as of {as_of_date}\n\n"
            "🎭 *Demo Mode — Sample Data*\n\n"
            "### ASSETS\n"
            "| Account | Balance |\n"
            "|---------|--------|\n"
            "| **Current Assets** | |\n"
            "| Checking | $47,523.84 |\n"
            "| Savings | $125,000.00 |\n"
            "| Accounts Receivable | $49,200.00 |\n"
            "| **Total Assets** | **$221,723.84** |\n\n"
            "### LIABILITIES\n"
            "| Account | Balance |\n"
            "|---------|--------|\n"
            "| Accounts Payable | $5,097.28 |\n"
            "| **Total Liabilities** | **$5,097.28** |\n\n"
            "### EQUITY\n"
            "| Account | Balance |\n"
            "|---------|--------|\n"
            "| Owner's Equity | $77,876.56 |\n"
            "| Net Income | $138,750.00 |\n"
            "| **Total Equity** | **$216,626.56** |\n\n"
            "**Total Liabilities + Equity: $221,723.84**"
        )

    params = {"date_macro": "", "start_date": as_of_date, "end_date": as_of_date}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/BalanceSheet", params=params)

    basis_note = f" · {method} basis" if method else ""
    lines = [f"## Balance Sheet as of {as_of_date}{basis_note}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Cash Flow Statement
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_cash_flow(start_date: str = "", end_date: str = "") -> str:
    """Generate a Statement of Cash Flows report. Dates in YYYY-MM-DD (default: current year-to-date). Shows operating, investing, and financing cash activities."""
    start_date, end_date = _ytd_range(start_date, end_date)
    report = await qb_request("GET", "reports/CashFlow", params={
        "start_date": start_date,
        "end_date": end_date,
    })

    header = report.get("Header", {})
    lines = [f"## Statement of Cash Flows: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — General Ledger
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_general_ledger(start_date: str, end_date: str, account_name: str = "") -> str:
    """Generate a General Ledger report showing all transactions by account. Dates in YYYY-MM-DD. Optionally filter by account_name."""
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }
    if account_name:
        accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
        acct_list = accounts.get("QueryResponse", {}).get("Account", [])
        if acct_list:
            params["account"] = acct_list[0]["Id"]

    report = await qb_request("GET", "reports/GeneralLedger", params=params)

    header = report.get("Header", {})
    lines = [f"## General Ledger: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    if account_name:
        lines.append(f"Filtered: {account_name}\n")

    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Trial Balance
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_trial_balance(start_date: str = "", end_date: str = "") -> str:
    """Generate a Trial Balance report. Dates in YYYY-MM-DD (default: current year-to-date). Shows all account debits and credits to verify books are balanced."""
    start_date, end_date = _ytd_range(start_date, end_date)
    report = await qb_request("GET", "reports/TrialBalance", params={
        "start_date": start_date,
        "end_date": end_date,
    })

    header = report.get("Header", {})
    lines = [f"## Trial Balance: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Tier-1 native reports (sales / detail / open items)
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_sales_by_customer(start_date: str = "", end_date: str = "", basis: str = "") -> str:
    """Total sales (income) by customer for a date range — who your biggest
    customers are. Dates YYYY-MM-DD (default: current year-to-date). basis: ''
    (QuickBooks default), 'cash', or 'accrual'."""
    start_date, end_date = _ytd_range(start_date, end_date)
    params = {"start_date": start_date, "end_date": end_date,
              "summarize_column_by": "Total"}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/SalesByCustomer", params=params)
    h = report.get("Header", {})
    basis_note = f" · {method} basis" if method else ""
    lines = [f"## Sales by Customer: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}{basis_note}\n"]
    _parse_report_rows(report.get("Rows", {}).get("Row", []), lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_sales_by_product(start_date: str = "", end_date: str = "", basis: str = "") -> str:
    """Sales by product/service (item) for a date range — what's actually
    selling, with quantity and amount. Dates YYYY-MM-DD (default: current
    year-to-date). basis: '' (QuickBooks default), 'cash', or 'accrual'."""
    start_date, end_date = _ytd_range(start_date, end_date)
    params = {"start_date": start_date, "end_date": end_date,
              "summarize_column_by": "Total"}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/SalesByProduct", params=params)
    h = report.get("Header", {})
    basis_note = f" · {method} basis" if method else ""
    lines = [f"## Sales by Product/Service: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}{basis_note}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_profit_loss_detail(start_date: str = "", end_date: str = "", basis: str = "") -> str:
    """Profit & Loss DETAIL — every transaction behind each P&L line, grouped by
    account. Use this to drill into a number from qb_profit_loss. Dates YYYY-MM-DD
    (default: current year-to-date). basis: '' (QuickBooks default), 'cash',
    or 'accrual'."""
    start_date, end_date = _ytd_range(start_date, end_date)
    params = {"start_date": start_date, "end_date": end_date}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/ProfitAndLossDetail", params=params)
    h = report.get("Header", {})
    basis_note = f" · {method} basis" if method else ""
    lines = [f"## Profit & Loss Detail: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}{basis_note}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_transaction_list(start_date: str = "", end_date: str = "") -> str:
    """A flexible transaction register — every transaction (date, type, num, name,
    account, amount) in a date range, the workhorse for 'show me everything that
    hit the books.' Dates YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    report = await qb_request("GET", "reports/TransactionList", params={
        "start_date": start_date, "end_date": end_date})
    h = report.get("Header", {})
    lines = [f"## Transaction List: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_customer_balance_detail(as_of_date: str = "") -> str:
    """Open invoices per customer with line detail (date, invoice #, due date,
    amount, open balance) — the drill-down behind qb_ar_aging. as_of_date:
    YYYY-MM-DD (defaults to today)."""
    as_of_date = _as_of_or_today(as_of_date)
    report = await qb_request("GET", "reports/CustomerBalanceDetail",
                              params={"report_date": as_of_date})
    lines = [f"## Customer Balance Detail — as of {as_of_date}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_vendor_balance_detail(as_of_date: str = "") -> str:
    """Open bills per vendor with line detail (date, bill #, due date, amount,
    open balance) — the drill-down behind qb_ap_aging. as_of_date: YYYY-MM-DD
    (defaults to today)."""
    as_of_date = _as_of_or_today(as_of_date)
    report = await qb_request("GET", "reports/VendorBalanceDetail",
                              params={"report_date": as_of_date})
    lines = [f"## Vendor Balance Detail — as of {as_of_date}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Tier-2 (class / department dimensions + inventory)
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_classes() -> str:
    """List QuickBooks classes (the segment tags used for class tracking, e.g.
    program, product line, location). Empty if the company doesn't use classes."""
    res = await qb_query_all("SELECT * FROM Class MAXRESULTS 1000")
    classes = res.get("QueryResponse", {}).get("Class", [])
    if not classes:
        return ("No classes found. Turn on class tracking in QuickBooks "
                "(Account and Settings → Advanced → Categories) to use "
                "class-based reports like qb_sales_by_class.")
    lines = [f"## Classes ({len(classes)})\n", "| Class | Status |", "|---|---|"]
    for c in sorted(classes, key=lambda x: x.get("FullyQualifiedName") or x.get("Name", "")):
        name = c.get("FullyQualifiedName") or c.get("Name", "?")
        lines.append(f"| {name} | {'Active' if c.get('Active') else 'Inactive'} |")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_departments() -> str:
    """List QuickBooks departments/locations (the Location-tracking dimension).
    Empty if the company doesn't use location tracking."""
    res = await qb_query_all("SELECT * FROM Department MAXRESULTS 1000")
    depts = res.get("QueryResponse", {}).get("Department", [])
    if not depts:
        return ("No departments/locations found. Turn on location tracking in "
                "QuickBooks (Account and Settings → Advanced → Categories) to use "
                "location-based reports like qb_sales_by_department.")
    lines = [f"## Departments / Locations ({len(depts)})\n", "| Department | Status |", "|---|---|"]
    for d in sorted(depts, key=lambda x: x.get("FullyQualifiedName") or x.get("Name", "")):
        name = d.get("FullyQualifiedName") or d.get("Name", "?")
        lines.append(f"| {name} | {'Active' if d.get('Active') else 'Inactive'} |")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_sales_by_class(start_date: str = "", end_date: str = "", basis: str = "") -> str:
    """Sales broken out by class for a date range — segment/program performance.
    Dates YYYY-MM-DD (default: current year-to-date). basis: '' (QuickBooks
    default), 'cash', or 'accrual'. Requires class tracking (see qb_list_classes)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    params = {"start_date": start_date, "end_date": end_date}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/SalesByClassSummary", params=params)
    rows = report.get("Rows", {}).get("Row", [])
    if not rows:
        return ("No class-based sales found for this period. This report needs "
                "QuickBooks class tracking enabled and classes on your sales.")
    h = report.get("Header", {})
    lines = [f"## Sales by Class: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_sales_by_department(start_date: str = "", end_date: str = "", basis: str = "") -> str:
    """Sales broken out by department/location for a date range. Dates YYYY-MM-DD
    (default: current year-to-date). basis: '' (QuickBooks default), 'cash', or
    'accrual'. Requires location tracking (see qb_list_departments)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    params = {"start_date": start_date, "end_date": end_date}
    method = _accounting_method(basis)
    if method:
        params["accounting_method"] = method
    report = await qb_request("GET", "reports/SalesByDepartment", params=params)
    rows = report.get("Rows", {}).get("Row", [])
    if not rows:
        return ("No location-based sales found for this period. This report needs "
                "QuickBooks location tracking enabled and locations on your sales.")
    h = report.get("Header", {})
    lines = [f"## Sales by Department/Location: {h.get('StartPeriod','')} to {h.get('EndPeriod','')}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_inventory_valuation(as_of_date: str = "") -> str:
    """Inventory valuation as of a date — on-hand quantity, asset value, and
    average cost per inventory item, with the total asset value. as_of_date:
    YYYY-MM-DD (defaults to today). Empty if the company doesn't track inventory."""
    as_of_date = _as_of_or_today(as_of_date)
    report = await qb_request("GET", "reports/InventoryValuationSummary",
                              params={"start_date": as_of_date, "end_date": as_of_date})
    rows = report.get("Rows", {}).get("Row", [])
    if not rows:
        return ("No inventory found. This report needs inventory-tracked items "
                "in QuickBooks (items with 'I track quantity on hand' enabled).")
    lines = [f"## Inventory Valuation — as of {as_of_date}\n"]
    _format_report_table(report, lines)
    return "\n".join(lines)


# ===================================================================
# CPA WORKBOOK SUPPORT — reconciliation, comparatives, tax payments, draws
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_reconciliation_status(as_of_date: str = "") -> str:
    """Bank and credit-card tie-out summary for CPA handoff: per-account book
    balance, most recent transaction date, and the Undeposited Funds balance.
    as_of_date: YYYY-MM-DD (defaults to today). Note: the QuickBooks API does
    not expose reconciliation/cleared status — this is a book-side summary."""
    from datetime import date as _date
    as_of_date = _validate_date(as_of_date, "as_of_date") if as_of_date \
        else _date.today().isoformat()

    accounts = (await qb_query(
        "SELECT * FROM Account WHERE AccountType IN ('Bank', 'Credit Card') "
        "MAXRESULTS 50")).get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return "No bank or credit-card accounts found."

    # Latest activity per account from recent purchases + deposits
    last_activity = {}
    for entity in ("Purchase", "Deposit"):
        result = await qb_query(
            f"SELECT * FROM {entity} WHERE TxnDate <= '{as_of_date}' "
            f"ORDERBY TxnDate DESC MAXRESULTS 200")
        for txn in result.get("QueryResponse", {}).get(entity, []):
            ref = (txn.get("AccountRef") or txn.get("DepositToAccountRef") or {})
            name = ref.get("name", "")
            d = txn.get("TxnDate", "")
            if name and d and d > last_activity.get(name, ""):
                last_activity[name] = d

    lines = [f"## Reconciliation Status — as of {as_of_date}\n",
             "| Account | Type | Book balance | Last transaction |",
             "|---|---|---|---|"]
    for a in accounts:
        name = a.get("Name", "?")
        bal = float(a.get("CurrentBalance", 0) or 0)
        lines.append(f"| {name} | {a.get('AccountType', '')} | {fmt(bal)} | "
                     f"{last_activity.get(name, 'no recent activity')} |")

    all_accounts = (await qb_query_all("SELECT * FROM Account MAXRESULTS 500")) \
        .get("QueryResponse", {}).get("Account", [])
    undeposited = [a for a in all_accounts
                   if "undeposited" in (a.get("Name", "")).lower()]
    for u in undeposited:
        ubal = float(u.get("CurrentBalance", 0) or 0)
        flag = " ⚠️ should be cleared before year-end" if abs(ubal) > 0.01 else " ✅"
        lines.append(f"\n**Undeposited Funds:** {fmt(ubal)}{flag}")

    lines.append(
        "\n⚠️ QuickBooks' API does not expose reconciliation status — verify "
        "each book balance against the bank statement; last-reconciled dates "
        "are visible only in QuickBooks itself."
    )
    _audit_log("RECONCILIATION_STATUS", f"as_of={as_of_date} accounts={len(accounts)}")
    return "\n".join(lines)


def _extract_report_amounts(report: dict) -> dict:
    """Flatten a QBO report's leaf rows into {line name: amount}."""
    out = {}

    def walk(rows):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    out[name] = float(col_data[-1].get("value", "0") or 0)
                except (ValueError, TypeError):
                    pass
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                walk(nested)
            summary = section.get("Summary", {})
            cols = summary.get("ColData", [])
            if len(cols) >= 2:
                name = cols[0].get("value", "")
                try:
                    out[name] = float(cols[-1].get("value", "0") or 0)
                except (ValueError, TypeError):
                    pass

    walk(report.get("Rows", {}).get("Row", []))
    return out


def _ytd_range(start_date: str = "", end_date: str = "") -> tuple:
    """Resolve a (start, end) date range, defaulting to the current calendar
    year-to-date when either is blank — so report tools can be called with no
    arguments instead of erroring (-32602) on a missing required param."""
    from datetime import date as _d
    today = _d.today()
    start = start_date.strip() if start_date else f"{today.year}-01-01"
    end = end_date.strip() if end_date else today.isoformat()
    return start, end


def _as_of_or_today(as_of_date: str = "") -> str:
    """Resolve an as-of date, defaulting to today when blank."""
    from datetime import date as _d
    return as_of_date.strip() if as_of_date else _d.today().isoformat()


def _accounting_method(basis: str) -> str:
    """Map a 'cash'/'accrual' basis hint to the QBO accounting_method param
    ('' = QuickBooks' default). CPAs often book accrual but file cash."""
    b = (basis or "").strip().lower()
    if b in ("cash", "c"):
        return "Cash"
    if b in ("accrual", "a"):
        return "Accrual"
    return ""


def _merge_line_order(cur_keys: list, prior_keys: list) -> list:
    """Order the union of two report line sequences so a line that exists only
    in the prior year is placed next to its section siblings — right after the
    shared line it followed in the prior report — instead of being dumped at the
    end (after Net Income). Preserves the current report's order as the spine."""
    cur_set = set(cur_keys)
    # Group each prior-only line under the last shared line that preceded it.
    anchored: dict = {}
    last_shared = None
    for k in prior_keys:
        if k in cur_set:
            last_shared = k
        else:
            anchored.setdefault(last_shared, []).append(k)
    result = list(anchored.get(None, []))  # prior-only lines before any shared line
    for ck in cur_keys:
        result.append(ck)
        result.extend(anchored.get(ck, []))
    return result


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_comparative_statements(statement: str = "pl", year: int = 0) -> str:
    """Two-year comparative statement — the format CPAs read first. Renders
    current vs prior year side by side with dollar and percent change, and
    flags swings over ±30%. statement: 'pl' (Profit & Loss) or 'bs'
    (Balance Sheet). year: the CURRENT year of the pair (default: this year;
    year-to-date vs the same era isn't attempted — prior year is full-year)."""
    from datetime import date as _date
    statement = statement.lower().strip()
    if statement not in ("pl", "bs"):
        return "statement must be 'pl' (Profit & Loss) or 'bs' (Balance Sheet)."
    year = int(year) or _date.today().year
    today = _date.today()
    cur_end = today.isoformat() if year == today.year else f"{year}-12-31"

    if statement == "pl":
        cur = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": f"{year}-01-01", "end_date": cur_end,
            "summarize_column_by": "Total"})
        prior = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": f"{year-1}-01-01", "end_date": f"{year-1}-12-31",
            "summarize_column_by": "Total"})
        title = "Comparative Profit & Loss"
        period_note = (f"{year} through {cur_end}" if year == today.year
                       else str(year)) + f" vs {year-1} (full year)"
    else:
        cur = await qb_request("GET", "reports/BalanceSheet", params={
            "start_date": cur_end, "end_date": cur_end})
        prior = await qb_request("GET", "reports/BalanceSheet", params={
            "start_date": f"{year-1}-12-31", "end_date": f"{year-1}-12-31"})
        title = "Comparative Balance Sheet"
        period_note = f"as of {cur_end} vs {year-1}-12-31"

    cur_amts = _extract_report_amounts(cur)
    prior_amts = _extract_report_amounts(prior)
    if not cur_amts and not prior_amts:
        return f"No data available for either period ({year} / {year-1})."

    lines = [f"## {title}", f"**Periods:** {period_note}\n",
             f"| Line | {year} | {year-1} | Δ | Δ% |",
             "|---|---|---|---|---|"]
    flagged = []
    seen = _merge_line_order(list(cur_amts), list(prior_amts))
    for name in seen:
        c = cur_amts.get(name)
        p = prior_amts.get(name)
        delta = (c or 0) - (p or 0)
        if p not in (None, 0):
            pct = delta / abs(p) * 100
            pct_s = f"{pct:+.0f}%"
            if abs(pct) > 30 and abs(delta) > 100:
                pct_s += " ⚠️"
                flagged.append((name, pct))
        else:
            pct_s = "new" if c not in (None, 0) else "—"
        bold = "**" if name.lower().startswith(("total", "net ", "gross")) else ""
        lines.append(f"| {bold}{name}{bold} | {fmt_signed(c)} | {fmt_signed(p)} | "
                     f"{fmt_signed(delta)} | {pct_s} |")

    if flagged:
        lines.append("\n### Swings your CPA will ask about (>±30%)")
        for name, pct in flagged[:8]:
            lines.append(f"- **{name}**: {pct:+.0f}% year over year")

    lines.append("\n*Prior year is the full calendar year; the current column "
                 "is year-to-date until Dec 31.*")
    _audit_log("COMPARATIVE_STATEMENTS", f"stmt={statement} year={year}")
    return "\n".join(lines)


# Payees/memos that indicate income-tax payments to a tax authority.
_TAX_AUTHORITY_HINTS = (
    "irs", "internal revenue", "eftps", "united states treasury", "us treasury",
    "u.s. treasury", "franchise tax", "department of revenue", "dept of revenue",
    "estimated tax", "1040-es",
    "cra", "canada revenue", "receiver general", "revenu quebec",
    "revenu québec", "minister of finance",
)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_tax_payments_made(tax_year: str = "") -> str:
    """What you actually PAID the IRS/CRA this year — the first thing a CPA
    asks. Finds payments to tax authorities (by payee/memo) plus TaxPayment
    records (CA), totals them, and compares against the quarterly estimate.
    tax_year: YYYY, defaults to the current year."""
    from datetime import date as _date
    if not tax_year:
        tax_year = str(_date.today().year)
    start, end = f"{tax_year}-01-01", f"{tax_year}-12-31"

    found = []
    for entity in ("Purchase",):
        result = await qb_query_all(
            f"SELECT * FROM {entity} WHERE TxnDate >= '{start}' "
            f"AND TxnDate <= '{end}' MAXRESULTS 1000")
        for txn in result.get("QueryResponse", {}).get(entity, []):
            payee = (txn.get("EntityRef") or {}).get("name", "")
            memo = str(txn.get("PrivateNote", "")) + " " + " ".join(
                str((l.get("Description") or "")) for l in txn.get("Line", []))
            blob = (payee + " " + memo).lower()
            if any(h in blob for h in _TAX_AUTHORITY_HINTS):
                found.append({
                    "date": txn.get("TxnDate", "?"),
                    "payee": payee or "(no payee)",
                    "amount": float(txn.get("TotalAmt", 0) or 0),
                })

    # CA/AU/UK: TaxPayment entity records payments against filed returns
    try:
        tp = await qb_query_all("SELECT * FROM TaxPayment MAXRESULTS 300")
        for t in tp.get("QueryResponse", {}).get("TaxPayment", []):
            d = t.get("PaymentDate") or t.get("TxnDate") or ""
            if start <= d <= end:
                found.append({"date": d, "payee": "Tax agency (TaxPayment)",
                              "amount": float(t.get("PaymentAmount",
                                                    t.get("TotalAmt", 0)) or 0)})
    except Exception as e:
        logger.debug(f"TaxPayment query failed: {e}")

    lines = [f"## Tax Payments Made — {tax_year}\n"]
    if not found:
        lines.append("No payments to tax authorities found in the books for "
                     f"{tax_year}. If you paid the IRS/CRA from an account "
                     "outside QuickBooks, tell your CPA the amounts and dates.")
    else:
        found.sort(key=lambda x: x["date"])
        lines.append("| Date | Payee | Amount |")
        lines.append("|---|---|---|")
        total = 0.0
        for f_ in found:
            lines.append(f"| {f_['date']} | {f_['payee']} | {fmt(f_['amount'])} |")
            total += f_["amount"]
        lines.append(f"| **Total paid** | | **{fmt(total)}** |")

    lines.append("\n*Verify against your IRS online account / CRA My Account — "
                 "payments made outside QuickBooks won't appear here. "
                 "Run qb_estimate_quarterly_tax to compare against what the "
                 "estimator suggests per quarter.*")
    _audit_log("TAX_PAYMENTS_MADE", f"year={tax_year} found={len(found)}")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_owner_draws(year: int = 0) -> str:
    """Owner's draws and contributions for the year — equity movement a CPA
    always asks about for Schedule C / T2125 filers. Summarizes activity in
    every Equity-type account. year: defaults to the current year."""
    from datetime import date as _date
    year = int(year) or _date.today().year
    start, end = f"{year}-01-01", f"{year}-12-31"

    all_accounts = (await qb_query_all("SELECT * FROM Account MAXRESULTS 500")) \
        .get("QueryResponse", {}).get("Account", [])
    equity = [a for a in all_accounts
              if (a.get("AccountType") or "").lower() == "equity"]
    if not equity:
        return "No equity accounts found in the chart of accounts."

    lines = [f"## Owner's Draws & Contributions — {year}\n"]
    net = 0.0
    any_rows = False
    for acct in equity:
        report = await qb_request("GET", "reports/GeneralLedger", params={
            "start_date": start, "end_date": end, "account": acct.get("Id")})

        # Collect leaf rows belonging to THIS account's section (the live API
        # filters by account; demo returns the full GL, so match the header).
        acct_rows = []

        def collect(sections):
            for s in sections:
                hdr = ((s.get("Header", {}).get("ColData") or [{}])[0]
                       .get("value", ""))
                nested = s.get("Rows", {}).get("Row", [])
                if hdr == acct.get("Name") and nested:
                    for leaf in nested:
                        cd = leaf.get("ColData", [])
                        if len(cd) >= 2:
                            try:
                                amt = float(cd[-1].get("value", "0") or 0)
                            except (ValueError, TypeError):
                                continue
                            desc = cd[1].get("value", "") if len(cd) >= 3 else ""
                            acct_rows.append((cd[0].get("value", ""), desc, amt))
                elif nested:
                    collect(nested)

        collect(report.get("Rows", {}).get("Row", []))
        if not acct_rows:
            continue
        any_rows = True
        lines.append(f"### {acct.get('Name', '?')}")
        for d, desc, v in acct_rows:
            direction = "contribution" if v > 0 else "draw"
            label = f"{d} — {desc}" if desc else d
            lines.append(f"  {label}: {fmt_signed(v)} ({direction})")
            net += v
    if not any_rows:
        lines.append("No equity activity recorded this year. Draws taken "
                     "outside QuickBooks should be reported to your CPA "
                     "directly.")
    else:
        label = "net contribution" if net >= 0 else "net draw"
        lines.append(f"\n**Net owner activity: {fmt_signed(net)}** ({label})")

    lines.append("\n*Draws are not business expenses — they reduce owner's "
                 "equity. Your CPA reconciles this against the balance sheet.*")
    _audit_log("OWNER_DRAWS", f"year={year} net={fmt(net)}")
    return "\n".join(lines)



# ===================================================================
# REPORTS — Accounts Receivable Aging
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_ar_aging(as_of_date: str = "") -> str:
    """Generate an Accounts Receivable Aging report. Date in YYYY-MM-DD (defaults to today). Shows what customers owe you, grouped by how overdue."""
    as_of_date = _as_of_or_today(as_of_date)
    report = await qb_request("GET", "reports/AgedReceivables", params={
        "date_macro": "",
        "start_date": as_of_date,
        "end_date": as_of_date,
    })

    lines = [f"## Accounts Receivable Aging as of {as_of_date}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Accounts Payable Aging
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_ap_aging(as_of_date: str = "") -> str:
    """Generate an Accounts Payable Aging report. Date in YYYY-MM-DD (defaults to today). Shows what you owe vendors, grouped by how overdue."""
    as_of_date = _as_of_or_today(as_of_date)
    report = await qb_request("GET", "reports/AgedPayables", params={
        "date_macro": "",
        "start_date": as_of_date,
        "end_date": as_of_date,
    })

    lines = [f"## Accounts Payable Aging as of {as_of_date}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Tax Summary (Schedule C)
# ===================================================================

# ---------------------------------------------------------------------------
# Shared Schedule C expense mapping. Word-boundary matching with specific rules
# FIRST, so accounts are never mis-mapped by substring — the bugs this fixes:
# "car" inside "Credit Card" -> Line 9, "tax" inside "Taxis" -> Line 23, and
# generic "interest" swallowing mortgage vs. credit-card interest. Both
# qb_schedule_c and qb_schedule_c_detailed use this so they can never disagree,
# and both read P&L period activity (not balance-sheet balances).
# ---------------------------------------------------------------------------
import re as _re  # re is otherwise imported lazily deeper in this module

# (regex, IRS Schedule C line, description). ORDER MATTERS — first match wins,
# so specific rules precede generic (mortgage before interest).
_SCHEDULE_C_RULES = [
    (r"mortgage", "16a", "Mortgage interest"),
    (r"advertis|marketing", "8", "Advertising"),
    (r"cars?\b|truck|vehicle|automobile|mileage", "9", "Car and truck expenses"),
    (r"commission", "10", "Commissions and fees"),
    (r"contract labou?r|subcontractor|contractor|freelancer", "11", "Contract labor"),
    (r"depreciation|amortization", "13", "Depreciation and section 179"),
    (r"insurance", "15", "Insurance (other than health)"),
    (r"interest|finance charge", "16b", "Other interest"),
    (r"legal|professional|accounting|bookkeep|consult", "17",
     "Legal and professional services"),
    (r"rent|lease", "20b", "Rent or lease (other business property)"),
    (r"repair|maintenance", "21", "Repairs and maintenance"),
    (r"office", "18", "Office expense"),
    (r"supplies|stationery", "22", "Supplies"),
    (r"tax(?:es)?\b|licen[cs]e|permit", "23", "Taxes and licenses"),
    (r"travel|hotel|lodging|airfare|airline|flight|taxi|rideshare|ride ?share|"
     r"uber|lyft", "24a", "Travel"),
    (r"meals?|restaurant|dining|entertainment", "24b", "Deductible meals"),
    (r"utilit(y|ies)|electric|water|internet|phone|telephone|cell|communication",
     "25", "Utilities"),
    (r"wages?|salar|payroll", "26", "Wages"),
    (r"software|subscription|hosting|cloud|saas|education|training|"
     r"bank (charge|fee)|processing|merchant|dues|shipping|postage|freight",
     "27a", "Other expenses"),
]
# Leading word boundary only, so stems match inflections ("advertis" ->
# "Advertising", "electric" -> "Electricity"). The two genuinely-ambiguous
# short stems (car, tax) carry their own trailing \b inside the pattern so
# "Card" and "Taxis" don't match.
_SCHEDULE_C_COMPILED = [
    (_re.compile(r"\b(?:" + pat + r")", _re.IGNORECASE), line, desc)
    for pat, line, desc in _SCHEDULE_C_RULES
]
# Personal / home-office hints that belong on Form 8829, not a direct Schedule
# C line — flagged for review (still counted so totals reconcile to the P&L).
_HOME_8829_HINTS = _re.compile(
    r"\b(home office|home-office|homeowner|home utilit|home insurance)\b",
    _re.IGNORECASE)


def _match_schedule_c_line(account_name: str):
    """(line, desc) for an expense account, or None if it maps to 'Other'.
    Word-boundary + specific-first: 'Credit Card' never hits Line 9,
    'Taxis' never hits Line 23."""
    name = account_name or ""
    for pat, line, desc in _SCHEDULE_C_COMPILED:
        if pat.search(name):
            return line, desc
    return None


def _extract_pl_expense_accounts(pl_result: dict) -> dict:
    """{account_name: amount} for every LEAF row in the P&L Expenses section
    (period activity, not balances). Shared so both Schedule C tools use the
    same numbers and reconcile to the P&L."""
    out: dict = {}

    def walk(rows):
        for section in rows or []:
            nested = section.get("Rows", {}).get("Row", [])
            col = section.get("ColData", [])
            if not nested and len(col) >= 2:
                name = col[0].get("value", "")
                try:
                    val = float(col[-1].get("value", "0") or 0)
                except (ValueError, TypeError):
                    val = 0.0
                if name and val != 0:
                    out[name] = out.get(name, 0.0) + val
            if nested:
                walk(nested)

    for section in pl_result.get("Rows", {}).get("Row", []):
        header = section.get("Header", {}).get("ColData", [{}])
        if header and "expense" in header[0].get("value", "").lower():
            walk(section.get("Rows", {}).get("Row", []))
    return out


def _pl_expense_total(pl_result: dict) -> float:
    """Total from the P&L Expenses section summary row — the reconciliation
    target for Schedule C Line 28."""
    for section in pl_result.get("Rows", {}).get("Row", []):
        summary = section.get("Summary", {}).get("ColData", [])
        if len(summary) >= 2 and "expense" in summary[0].get("value", "").lower():
            try:
                return abs(float(summary[-1].get("value", "0") or 0))
            except (ValueError, TypeError):
                return 0.0
    return 0.0


def _map_expenses_to_schedule_c(expense_accounts: dict):
    """Map {name: amount} -> ordered dict {line_key: {'amount', 'accounts',
    'home': bool}}, routing anything unmatched to Line 27a so NOTHING is
    dropped (Line 28 total == sum of expense accounts == P&L expenses)."""
    from collections import defaultdict
    sc = defaultdict(lambda: {"amount": 0.0, "accounts": [], "home": False})
    for name, amount in expense_accounts.items():
        m = _match_schedule_c_line(name)
        line, desc = m if m else ("27a", "Other expenses")
        key = f"Line {line} — {desc}"
        sc[key]["amount"] += abs(amount)
        sc[key]["accounts"].append((name, abs(amount)))
        if _HOME_8829_HINTS.search(name or ""):
            sc[key]["home"] = True
    return sc


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "For Canadian books use qb_t2125_summary.")
async def qb_tax_summary(start_date: str = "", end_date: str = "") -> str:
    """Generate a tax-oriented summary mapping QuickBooks data to Schedule C lines. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    report = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date,
        "end_date": end_date,
        "summarize_column_by": "Total",
    })

    lines = [f"## Tax Summary (Schedule C): {start_date} to {end_date}\n"]
    schedule_c = {}

    # Expense accounts only (period activity), word-boundary mapped — the same
    # shared logic qb_schedule_c uses, so 'Credit Card'/'Taxis'-style substring
    # mis-maps can't happen here either.
    for rname, amount in _extract_pl_expense_accounts(report).items():
        m = _match_schedule_c_line(rname)
        line, desc = m if m else ("27a", "Other expenses")
        mapped = f"Line {line} - {desc}"
        schedule_c.setdefault(mapped, [])
        schedule_c[mapped].append((rname, abs(amount)))

    for sc_line in sorted(schedule_c.keys()):
        items = schedule_c[sc_line]
        total = sum(a for _, a in items)
        lines.append(f"### {sc_line}: {fmt(total)}")
        for rname, a in items:
            lines.append(f"  - {rname}: {fmt(a)}")
        lines.append("")

    grand = sum(sum(a for _, a in items) for items in schedule_c.values())
    lines.append(f"\n**Total Deductible Expenses: {fmt(grand)}**")
    return "\n".join(lines)


# ===================================================================
# ENTITY MANAGEMENT — Accounts
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_accounts(max_results: int = 100) -> str:
    """List all chart of accounts (expense categories, income accounts, etc.) in QuickBooks."""
    # Demo mode: return mock accounts
    if _demo_active():
        accounts = DEMO_ACCOUNTS[:max_results]
    else:
        query = f"SELECT * FROM Account MAXRESULTS {max_results}"
        result = await qb_query(query)
        accounts = result.get("QueryResponse", {}).get("Account", [])

    if not accounts:
        return "No accounts found."

    grouped = {}
    for a in accounts:
        atype = a.get("AccountType", "Other")
        grouped.setdefault(atype, []).append(a)

    lines = ["## Chart of Accounts\n"]
    for atype in sorted(grouped.keys()):
        lines.append(f"### {atype}")
        for a in grouped[atype]:
            aname = a.get("FullyQualifiedName", a.get("Name", "Unknown"))
            balance = fmt(a.get("CurrentBalance", 0))
            sub = a.get("AccountSubType", "")
            lines.append(f"- {aname} (ID: {a.get('Id')}) | {sub} | Balance: {balance}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# ENTITY MANAGEMENT — Vendors
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_vendors(name: str = "", max_results: int = 50) -> str:
    """List vendors/suppliers in QuickBooks. Optionally filter by name."""
    # Demo mode: return mock vendors
    if _demo_active():
        vendors = DEMO_VENDORS[:max_results]
        if name:
            vendors = [v for v in vendors if name.lower() in v.get("DisplayName", "").lower()]
    else:
        query = "SELECT * FROM Vendor"
        if name:
            query += f" WHERE DisplayName LIKE '%{name}%'"
        query += f" MAXRESULTS {max_results}"
        result = await qb_query(query)
        vendors = result.get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        return "No vendors found."

    lines = [f"## Vendors ({len(vendors)} found)\n"]
    for v in vendors:
        vname = v.get("DisplayName", "Unknown")
        balance = fmt(v.get("Balance", 0))
        active = "Active" if v.get("Active", True) else "Inactive"
        email = v.get("PrimaryEmailAddr", {}).get("Address", "")
        lines.append(f"- **{vname}** (ID: {v.get('Id')}) | Balance: {balance} | {active}" + (f" | {email}" if email else ""))
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_vendor(display_name: str, email: str = "", phone: str = "", company_name: str = "") -> str:
    """Create a new vendor/supplier in QuickBooks. display_name is required. Optionally include email, phone, company_name."""
    vendor_body = {"DisplayName": display_name}
    if email:
        vendor_body["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        vendor_body["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        vendor_body["CompanyName"] = company_name

    result = await qb_request("POST", "vendor", json_body=vendor_body)
    v = result.get("Vendor", {})
    return (
        f"Vendor created!\n"
        f"- Name: {v.get('DisplayName')}\n"
        f"- ID: {v.get('Id')}\n"
        f"- Balance: {fmt(v.get('Balance', 0))}"
    )


# ===================================================================
# ENTITY MANAGEMENT — Customers
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_customers(name: str = "", max_results: int = 50) -> str:
    """List customers in QuickBooks. Optionally filter by name."""
    # Demo mode: return mock customers
    if _demo_active():
        customers = DEMO_CUSTOMERS[:max_results]
        if name:
            customers = [c for c in customers if name.lower() in c.get("DisplayName", "").lower()]
    else:
        query = "SELECT * FROM Customer"
        if name:
            query += f" WHERE DisplayName LIKE '%{name}%'"
        query += f" MAXRESULTS {max_results}"
        result = await qb_query(query)
        customers = result.get("QueryResponse", {}).get("Customer", [])

    if not customers:
        return "No customers found."

    lines = [f"## Customers ({len(customers)} found)\n"]
    for c in customers:
        cname = c.get("DisplayName", "Unknown")
        balance = fmt(c.get("Balance", 0))
        active = "Active" if c.get("Active", True) else "Inactive"
        email = c.get("PrimaryEmailAddr", {}).get("Address", "")
        lines.append(f"- **{cname}** (ID: {c.get('Id')}) | Balance: {balance} | {active}" + (f" | {email}" if email else ""))
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_customer(display_name: str, email: str = "", phone: str = "", company_name: str = "") -> str:
    """Create a new customer in QuickBooks. display_name is required. Optionally include email, phone, company_name."""
    customer_body = {"DisplayName": display_name}
    if email:
        customer_body["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        customer_body["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        customer_body["CompanyName"] = company_name

    result = await qb_request("POST", "customer", json_body=customer_body)
    c = result.get("Customer", {})
    return (
        f"Customer created!\n"
        f"- Name: {c.get('DisplayName')}\n"
        f"- ID: {c.get('Id')}\n"
        f"- Balance: {fmt(c.get('Balance', 0))}"
    )


# ===================================================================
# ENTITY MANAGEMENT — Items / Products & Services
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_items(name: str = "", max_results: int = 100) -> str:
    """List products and services (items) in QuickBooks. Optionally filter by name. Items are used on invoices and sales receipts."""
    query = "SELECT * FROM Item"
    if name:
        query += f" WHERE Name LIKE '%{name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    items = result.get("QueryResponse", {}).get("Item", [])

    if not items:
        return "No items found."

    lines = [f"## Items/Products ({len(items)} found)\n"]
    for item in items:
        iname = item.get("Name", "Unknown")
        itype = item.get("Type", "")
        price = fmt(item.get("UnitPrice", 0))
        active = "Active" if item.get("Active", True) else "Inactive"
        income_acct = item.get("IncomeAccountRef", {}).get("name", "")
        expense_acct = item.get("ExpenseAccountRef", {}).get("name", "")

        lines.append(f"- **{iname}** (ID: {item.get('Id')}) | {itype} | Price: {price} | {active}")
        if income_acct:
            lines.append(f"  Income account: {income_acct}")
        if expense_acct:
            lines.append(f"  Expense account: {expense_acct}")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION CREATION — Expenses / Purchases
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_expense(vendor_name: str, amount: float, account_name: str, date: str, description: str = "", payment_method: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a new expense/purchase in QuickBooks. vendor_name: payee, amount: total, account_name: expense category, date: YYYY-MM-DD, description: memo, payment_method: bank/card account name.
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; tax_inclusive=True when amount already includes tax."""
    # Demo mode: simulate success
    if _demo_active():
        return (
            f"🎭 *Demo Mode* — Expense simulated!\n\n"
            f"- ID: DEMO-{hash(vendor_name + date) % 10000}\n"
            f"- Vendor: {vendor_name}\n"
            f"- Amount: {fmt(amount)}\n"
            f"- Category: {account_name}\n"
            f"- Date: {date}\n\n"
            f"*In production, this would create a real expense in QuickBooks.*"
        )
    vendors = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
    vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
    if not vendor_list:
        return f"Vendor '{vendor_name}' not found. Use qb_list_vendors to find existing vendors, or qb_create_vendor to create one."
    vendor = vendor_list[0]

    account, err = await _resolve_account(account_name, account_type="Expense")
    if err:
        return err

    purchase_body = {
        "PaymentType": "Cash",
        "TxnDate": date,
        "EntityRef": {"value": vendor["Id"], "name": vendor["DisplayName"]},
        "Line": [{
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": amount,
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"value": account["Id"], "name": account["Name"]}
            },
            "Description": description or ""
        }],
    }
    if description:
        purchase_body["PrivateNote"] = description

    region = (await _get_region())["region"]
    if region != "US":
        if not tax_code:
            return _TAX_CODE_REQUIRED_MSG
        try:
            tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)
        _apply_global_tax(purchase_body, "Line", "AccountBasedExpenseLineDetail",
                          tax_id, tax_inclusive, region)

    if payment_method:
        pay_acct, pay_err = await _resolve_account(payment_method)
        if pay_err:
            return f"Payment method: {pay_err}"
        purchase_body["AccountRef"] = {"value": pay_acct["Id"], "name": pay_acct["Name"]}

    result = await qb_request("POST", "purchase", json_body=purchase_body)
    p = result.get("Purchase", {})
    return (
        f"Expense created!\n"
        f"- ID: {p.get('Id')}\n"
        f"- Vendor: {vendor['DisplayName']}\n"
        f"- Amount: {fmt(amount)}\n"
        f"- Category: {account['Name']}\n"
        f"- Date: {date}"
    )


# ===================================================================
# TRANSACTION CREATION — Invoices
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_invoice(customer_name: str, line_items: str, due_date: str = "", memo: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a customer invoice. line_items is a JSON string: [{"description": "...", "amount": 100}]. due_date in YYYY-MM-DD.
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; per-line override via 'tax_code' key in line_items JSON; tax_inclusive=True when amounts already include tax."""
    # Demo mode: simulate success
    if _demo_active():
        items = json.loads(line_items) if isinstance(line_items, str) else line_items
        total = sum(item.get("amount", 0) for item in items)
        return (
            f"🎭 *Demo Mode* — Invoice simulated!\n\n"
            f"- Invoice #: DEMO-{1046 + hash(customer_name) % 100}\n"
            f"- Customer: {customer_name}\n"
            f"- Total: {fmt(total)}\n"
            f"- Due: {due_date or 'Net 30'}\n\n"
            f"*In production, this would create a real invoice in QuickBooks.*"
        )
    customers = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 1")
    customer_list = customers.get("QueryResponse", {}).get("Customer", [])
    if not customer_list:
        return f"Customer '{customer_name}' not found. Use qb_list_customers or qb_create_customer."
    customer = customer_list[0]

    items = json.loads(line_items) if isinstance(line_items, str) else line_items

    region = (await _get_region())["region"]
    default_tax_id = None
    tax_cache: dict = {}
    if region != "US" and tax_code:
        try:
            default_tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)

    inv_lines = []
    for item in items:
        line = {
            "DetailType": "SalesItemLineDetail",
            "Amount": item.get("amount", 0),
            "Description": item.get("description", ""),
            "SalesItemLineDetail": {
                "Qty": item.get("quantity", 1),
                "UnitPrice": item.get("amount", 0) / max(item.get("quantity", 1), 1),
            }
        }
        try:
            line_tax = await _line_tax_code_ref(item, region, tax_cache)
        except ValueError as e:
            return str(e)
        if line_tax:
            line["SalesItemLineDetail"]["TaxCodeRef"] = line_tax
        inv_lines.append(line)

    if region != "US" and not default_tax_id and not any(
        "TaxCodeRef" in l["SalesItemLineDetail"] for l in inv_lines
    ):
        return _TAX_CODE_REQUIRED_MSG

    invoice_body = {
        "CustomerRef": {"value": customer["Id"]},
        "Line": inv_lines,
    }
    if due_date:
        invoice_body["DueDate"] = due_date
    if memo:
        invoice_body["CustomerMemo"] = {"value": memo}
    _apply_global_tax(invoice_body, "Line", "SalesItemLineDetail",
                      default_tax_id, tax_inclusive, region)

    result = await qb_request("POST", "invoice", json_body=invoice_body)
    inv = result.get("Invoice", {})
    return (
        f"Invoice created!\n"
        f"- Invoice #: {inv.get('DocNumber', 'N/A')}\n"
        f"- Customer: {customer['DisplayName']}\n"
        f"- Total: {fmt(inv.get('TotalAmt'))}\n"
        f"- Due: {inv.get('DueDate', 'N/A')}"
    )


# ===================================================================
# TRANSACTION CREATION — Journal Entries (Reclassify)
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_journal_entry(date: str, lines_json: str, memo: str = "") -> str:
    """Create a journal entry for reclassifications or adjustments. date: YYYY-MM-DD. lines_json is a JSON string: [{"account_name": "...", "amount": 100.00, "type": "Debit"}, {"account_name": "...", "amount": 100.00, "type": "Credit"}]. Debits and credits must balance."""
    entries = json.loads(lines_json) if isinstance(lines_json, str) else lines_json

    je_lines = []
    total_debit = 0.0
    total_credit = 0.0
    _allowed_keys = {"account_name", "account_id", "amount", "type", "description"}

    for i, entry in enumerate(entries, 1):
        unknown = set(entry) - _allowed_keys
        if unknown:
            return (f"Journal line {i} has unrecognized field(s): "
                    f"{', '.join(sorted(unknown))}. Allowed per line: account_name "
                    "(or account_id), amount, type ('Debit' or 'Credit'), description.")
        posting_type = entry.get("type", "Debit")
        if posting_type not in ("Debit", "Credit"):
            return (f"Journal line {i}: type must be 'Debit' or 'Credit' "
                    f"(got '{posting_type}').")
        amount = float(entry.get("amount", 0))

        acct_id = str(entry.get("account_id", "") or "").strip()
        if acct_id:
            acct = (await qb_read("account", acct_id)).get("Account")
            if not acct:
                return f"Journal line {i}: account_id '{acct_id}' not found."
        else:
            acct, err = await _resolve_account(entry.get("account_name", ""))
            if err:
                return f"Journal line {i}: {err}"
        acct_name = acct.get("Name", "")

        # Depreciation must credit an Accumulated Depreciation contra
        # account — crediting the asset itself corrupts its cost basis.
        text = f"{entry.get('description', '')} {memo}".lower()
        if (posting_type == "Credit" and acct.get("AccountType") == "Fixed Asset"
                and acct.get("AccountSubType") != "AccumulatedDepreciation"
                and "deprec" in text):
            return (
                f"This looks like a depreciation entry, but it credits the fixed "
                f"asset '{acct.get('Name')}' directly — that reduces the asset's "
                f"cost basis instead of accumulating depreciation. Use "
                f"qb_record_depreciation, which credits an Accumulated "
                f"Depreciation contra account (created automatically if needed)."
            )

        if posting_type == "Debit":
            total_debit += amount
        else:
            total_credit += amount

        je_lines.append({
            "DetailType": "JournalEntryLineDetail",
            "Amount": amount,
            "Description": entry.get("description", ""),
            "JournalEntryLineDetail": {
                "PostingType": posting_type,
                "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
            }
        })

    if abs(total_debit - total_credit) > 0.01:
        return f"Journal entry does not balance. Debits: {fmt(total_debit)}, Credits: {fmt(total_credit)}. They must be equal."

    je_body = {
        "TxnDate": date,
        "Line": je_lines,
    }
    if memo:
        je_body["PrivateNote"] = memo

    result = await qb_request("POST", "journalentry", json_body=je_body)
    je = result.get("JournalEntry", {})
    return (
        f"Journal entry created!\n"
        f"- ID: {je.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Total: {fmt(total_debit)}\n"
        f"- Lines: {len(je_lines)}" +
        (f"\n- Memo: {memo}" if memo else "")
    )


@mcp.tool(annotations={"destructiveHint": True})
async def qb_record_depreciation(asset_account: str, amount: float, date: str, memo: str = "") -> str:
    """Record period depreciation for a fixed asset the CORRECT way:
    debit Depreciation Expense, credit an Accumulated Depreciation contra
    account (auto-created as a sub-account of the asset if missing) — never
    the asset itself. Requires the asset's cost basis to already be on the
    books. asset_account: fixed-asset account name. date: YYYY-MM-DD."""
    amount = _validate_amount(amount, "amount")
    date = _validate_date(date, "date")

    asset, err = await _resolve_account(asset_account)
    if err:
        return err
    if asset.get("AccountType") != "Fixed Asset":
        return (f"'{asset.get('Name')}' is a {asset.get('AccountType')} account, "
                f"not a Fixed Asset — depreciation applies to fixed assets only.")
    if asset.get("AccountSubType") == "AccumulatedDepreciation":
        return (f"'{asset.get('Name')}' is itself an Accumulated Depreciation "
                f"account — pass the asset's cost account instead.")

    # Cost basis must be on the books before depreciating against it
    basis = float(asset.get("CurrentBalance", 0) or 0)
    if basis <= 0:
        return (
            f"'{asset.get('Name')}' has no cost basis on the books (balance "
            f"{fmt(basis)}). Record the asset purchase first (qb_create_expense "
            f"or a journal entry debiting the asset account), then depreciate."
        )

    # Find or create the Accumulated Depreciation contra sub-account
    accum_name = f"Accumulated Depreciation - {asset.get('Name')}"
    accum, _ = await _resolve_account(accum_name)
    created_accum = False
    if not accum or accum.get("AccountSubType") != "AccumulatedDepreciation":
        result = await qb_request("POST", "account", json_body={
            "Name": accum_name,
            "AccountType": "Fixed Asset",
            "AccountSubType": "AccumulatedDepreciation",
            "SubAccount": True,
            "ParentRef": {"value": asset["Id"]},
        })
        accum = result.get("Account", {})
        if not accum.get("Id"):
            return "Failed to create the Accumulated Depreciation sub-account."
        created_accum = True

    # Find or create Depreciation Expense
    expense, _ = await _resolve_account("Depreciation Expense")
    created_exp = False
    if not expense or expense.get("AccountType") != "Expense":
        result = await qb_request("POST", "account", json_body={
            "Name": "Depreciation Expense",
            "AccountType": "Other Expense",
            "AccountSubType": "Depreciation",
        })
        expense = result.get("Account", {})
        if not expense.get("Id"):
            return "Failed to create the Depreciation Expense account."
        created_exp = True

    je_body = {
        "TxnDate": date,
        "PrivateNote": memo or f"Depreciation — {asset.get('Name')}",
        "Line": [
            {"DetailType": "JournalEntryLineDetail", "Amount": amount,
             "Description": f"Depreciation expense — {asset.get('Name')}",
             "JournalEntryLineDetail": {"PostingType": "Debit",
                                        "AccountRef": {"value": expense["Id"]}}},
            {"DetailType": "JournalEntryLineDetail", "Amount": amount,
             "Description": f"Accumulated depreciation — {asset.get('Name')}",
             "JournalEntryLineDetail": {"PostingType": "Credit",
                                        "AccountRef": {"value": accum["Id"]}}},
        ],
    }
    result = await qb_request("POST", "journalentry", json_body=je_body)
    je = result.get("JournalEntry", {})

    _audit_log("RECORD_DEPRECIATION", f"asset={asset.get('Name')} amount={fmt(amount)} je={je.get('Id')}")
    notes = []
    if created_accum:
        notes.append(f"created contra account '{accum_name}'")
    if created_exp:
        notes.append("created 'Depreciation Expense' account")
    return (
        f"Depreciation recorded (JE #{je.get('Id')}, {date})\n"
        f"- Debit: Depreciation Expense {fmt(amount)}\n"
        f"- Credit: {accum_name} {fmt(amount)}\n"
        f"- Asset cost basis untouched: {fmt(basis)}"
        + (f"\n- Setup: {'; '.join(notes)}" if notes else "")
    )


# ===================================================================
# TRANSACTION CREATION — Deposits
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_deposit(date: str, deposit_to_account: str, lines_json: str, memo: str = "", tax_code: str = "") -> str:
    """Create a bank deposit. date: YYYY-MM-DD. deposit_to_account: name of bank account receiving deposit. lines_json: JSON string [{"account_name": "...", "amount": 100.00, "description": "..."}].
    Canada/global editions: optional tax_code applies a sales tax code to each deposit line, e.g. 'HST ON' (deposits do not require one)."""
    dep_acct, dep_err = await _resolve_account(deposit_to_account)
    if dep_err:
        return dep_err

    entries = json.loads(lines_json) if isinstance(lines_json, str) else lines_json
    dep_lines = []
    for entry in entries:
        acct_name = entry.get("account_name", "")
        amount = float(entry.get("amount", 0))
        desc = entry.get("description", "")

        acct, err = await _resolve_account(acct_name)
        if err:
            return err

        dep_lines.append({
            "DetailType": "DepositLineDetail",
            "Amount": amount,
            "Description": desc,
            "DepositLineDetail": {
                "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
            }
        })

    deposit_body = {
        "TxnDate": date,
        "DepositToAccountRef": {"value": dep_acct["Id"], "name": dep_acct["Name"]},
        "Line": dep_lines,
    }
    if memo:
        deposit_body["PrivateNote"] = memo

    if tax_code:
        region = (await _get_region())["region"]
        if region != "US":
            try:
                tax_id, _ = await _resolve_tax_code(tax_code)
            except ValueError as e:
                return str(e)
            _apply_global_tax(deposit_body, "Line", "DepositLineDetail",
                              tax_id, False, region)

    result = await qb_request("POST", "deposit", json_body=deposit_body)
    dep = result.get("Deposit", {})
    return (
        f"Deposit created!\n"
        f"- ID: {dep.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Total: {fmt(dep.get('TotalAmt'))}\n"
        f"- Deposited to: {dep_acct['Name']}"
    )


# ===================================================================
# TRANSACTION CREATION — Transfers
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_transfer(date: str, from_account: str, to_account: str, amount: float, memo: str = "") -> str:
    """Create a transfer between two accounts. date: YYYY-MM-DD. from_account and to_account are account names. amount is the transfer amount."""
    from_acct, from_err = await _resolve_account(from_account)
    if from_err:
        return f"From account: {from_err}"

    to_acct, to_err = await _resolve_account(to_account)
    if to_err:
        return f"To account: {to_err}"

    transfer_body = {
        "TxnDate": date,
        "Amount": amount,
        "FromAccountRef": {"value": from_acct["Id"], "name": from_acct["Name"]},
        "ToAccountRef": {"value": to_acct["Id"], "name": to_acct["Name"]},
    }
    if memo:
        transfer_body["PrivateNote"] = memo

    result = await qb_request("POST", "transfer", json_body=transfer_body)
    t = result.get("Transfer", {})
    return (
        f"Transfer created!\n"
        f"- ID: {t.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Amount: {fmt(amount)}\n"
        f"- From: {from_acct['Name']} → To: {to_acct['Name']}"
    )


# ===================================================================
# TRANSACTION UPDATE — Generic entity updater
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_update_transaction(entity_type: str, entity_id: str, updates_json: str) -> str:
    """Update an existing transaction. entity_type: Purchase, Deposit, Transfer, JournalEntry, Bill, Invoice, etc. entity_id: the transaction ID. updates_json: JSON string of fields to update (e.g., {"PrivateNote": "new memo", "TxnDate": "2025-01-15"}). Fetches current version first to ensure SyncToken is correct."""
    entity_lower = entity_type.lower()
    current = await qb_read(entity_lower, entity_id)
    entity_data = current.get(entity_type, {})

    if not entity_data:
        return f"{entity_type} with ID {entity_id} not found."

    updates = json.loads(updates_json) if isinstance(updates_json, str) else updates_json
    entity_data.update(updates)

    result = await qb_request("POST", entity_lower, json_body=entity_data)
    updated = result.get(entity_type, {})
    return (
        f"{entity_type} updated!\n"
        f"- ID: {updated.get('Id')}\n"
        f"- SyncToken: {updated.get('SyncToken')}\n"
        f"- Updated fields: {', '.join(updates.keys())}"
    )


# ===================================================================
# TRANSACTION VOID
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_void_transaction(entity_type: str, entity_id: str) -> str:
    """Void a transaction (keeps it in records but zeroes the amount). entity_type: Purchase, Invoice, Payment, SalesReceipt, BillPayment, etc. entity_id: the transaction ID. Note: not all entity types support void."""
    entity_lower = entity_type.lower()
    current = await qb_read(entity_lower, entity_id)
    entity_data = current.get(entity_type, {})

    if not entity_data:
        return f"{entity_type} with ID {entity_id} not found."

    void_body = {
        "Id": entity_data["Id"],
        "SyncToken": entity_data["SyncToken"],
    }

    try:
        result = await qb_request("POST", f"{entity_lower}?operation=void", json_body=void_body)
        voided = result.get(entity_type, {})
        return f"{entity_type} voided!\n- ID: {voided.get('Id')}\n- Original amount: {fmt(entity_data.get('TotalAmt', entity_data.get('Amount')))}"
    except Exception as e:
        return f"Could not void {entity_type} {entity_id}: {str(e)}. Not all transaction types support void."


# ===================================================================
# RECONCILIATION
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_reconcile_invoices(start_date: str, end_date: str, invoice_data: str) -> str:
    """Compare email-extracted invoices against QuickBooks transactions. invoice_data is a JSON string: [{"vendor": "...", "amount": 100.00, "date": "2025-01-15"}]. Dates in YYYY-MM-DD."""
    query = (
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    result = await qb_query_all(query)
    qb_purchases = result.get("QueryResponse", {}).get("Purchase", [])

    qb_by_vendor = {}
    for p in qb_purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown").lower()
        qb_by_vendor.setdefault(vendor, []).append({
            "amount": float(p.get("TotalAmt", 0)),
            "date": p.get("TxnDate", ""),
            "id": p.get("Id", ""),
        })

    try:
        invoices = json.loads(invoice_data) if isinstance(invoice_data, str) else invoice_data
    except json.JSONDecodeError:
        return ('invoice_data must be a JSON array like '
                '[{"vendor": "Acme", "amount": 100.00, "date": "2026-01-15"}].')
    matched = []
    missing = []
    mismatched = []

    for inv in invoices:
        vendor = inv.get("vendor", "").lower()
        amount = float(inv.get("amount", 0))
        date = inv.get("date", "")

        found = False
        for key in qb_by_vendor:
            if vendor in key or key in vendor:
                for qb_txn in qb_by_vendor[key]:
                    if abs(qb_txn["amount"] - amount) < 0.02:
                        matched.append({"vendor": inv["vendor"], "amount": amount, "qb_id": qb_txn["id"]})
                        found = True
                        break
                if not found:
                    qb_total = sum(t["amount"] for t in qb_by_vendor[key])
                    mismatched.append({"vendor": inv["vendor"], "invoice_amount": amount, "qb_total": qb_total})
                    found = True
                break

        if not found:
            missing.append({"vendor": inv["vendor"], "amount": amount, "date": date})

    lines = [f"## Reconciliation: {start_date} to {end_date}\n"]
    lines.append(f"**Matched:** {len(matched)} | **Missing from QB:** {len(missing)} | **Mismatched:** {len(mismatched)}\n")

    if missing:
        lines.append("### Missing from QuickBooks")
        for m in missing:
            lines.append(f"- {m['vendor']}: {fmt(m['amount'])} ({m['date']})")

    if mismatched:
        lines.append("\n### Amount Mismatches")
        for m in mismatched:
            lines.append(f"- {m['vendor']}: Invoice {fmt(m['invoice_amount'])} vs QB {fmt(m['qb_total'])}")

    if matched:
        lines.append(f"\n### Matched ({len(matched)})")
        for m in matched[:10]:
            lines.append(f"- {m['vendor']}: {fmt(m['amount'])}")
        if len(matched) > 10:
            lines.append(f"  ... and {len(matched) - 10} more")

    return "\n".join(lines)


# ===================================================================
# ACCOUNT BALANCE LOOKUP
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_account_balance(account_name: str) -> str:
    """Get the current balance of a specific account by name. Returns account details and balance."""
    accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    acct_list = accounts.get("QueryResponse", {}).get("Account", [])

    if not acct_list:
        return f"No account matching '{account_name}' found."

    lines = [f"## Account Balance: '{account_name}'\n"]
    for a in acct_list:
        lines.append(f"- **{a.get('Name')}** (ID: {a.get('Id')})")
        lines.append(f"  Type: {a.get('AccountType')} / {a.get('AccountSubType', '')}")
        lines.append(f"  Balance: {fmt(a.get('CurrentBalance', 0))}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# SMART FEATURES — Uncategorized / Duplicates / Auto-Categorize
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_uncategorized_transactions(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """Find transactions that are uncategorized or booked to 'Uncategorized Expense/Income/Asset'.
    Useful for cleaning up books. Dates in YYYY-MM-DD format. If omitted, searches all time."""
    # Find uncategorized accounts
    accts = await qb_query("SELECT Id, Name FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    acct_list = accts.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return "No uncategorized accounts found — your books look clean!"

    acct_ids = [a["Id"] for a in acct_list]
    acct_names = {a["Id"]: a["Name"] for a in acct_list}

    # Query purchases hitting those accounts
    date_filter = ""
    if start_date:
        date_filter += f" AND TxnDate >= '{start_date}'"
    if end_date:
        date_filter += f" AND TxnDate <= '{end_date}'"

    all_uncategorized = []
    for acct_id in acct_ids:
        q = f"SELECT * FROM Purchase WHERE AccountRef = '{acct_id}'{date_filter} MAXRESULTS {max_results}"
        try:
            result = await qb_query(q)
            purchases = result.get("QueryResponse", {}).get("Purchase", [])
            for p in purchases:
                all_uncategorized.append({
                    "id": p.get("Id"),
                    "date": p.get("TxnDate"),
                    "amount": float(p.get("TotalAmt", 0)),
                    "vendor": p.get("EntityRef", {}).get("name", "Unknown"),
                    "account": acct_names.get(acct_id, "Uncategorized"),
                    "memo": p.get("PrivateNote", ""),
                })
        except Exception:
            continue

    if not all_uncategorized:
        return "No uncategorized transactions found — everything is categorized!"

    all_uncategorized.sort(key=lambda x: x["date"] or "", reverse=True)
    lines = [f"## Uncategorized Transactions ({len(all_uncategorized)} found)\n"]
    total = 0.0
    for t in all_uncategorized:
        lines.append(f"- **{t['date']}** | {t['vendor']} | {fmt(t['amount'])} | {t['account']} | ID: {t['id']}")
        if t["memo"]:
            lines.append(f"  Memo: {t['memo']}")
        total += t["amount"]
    lines.append(f"\n**Total uncategorized: {fmt(total)}**")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_find_duplicates(start_date: str = "", end_date: str = "", tolerance_days: int = 3, max_results: int = 200) -> str:
    """Find potential duplicate transactions within a date range. Matches by amount and vendor within tolerance_days window. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    result = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    purchases = result.get("QueryResponse", {}).get("Purchase", [])
    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    from collections import defaultdict
    groups = defaultdict(list)
    for p in purchases:
        key = (
            round(float(p.get("TotalAmt", 0)), 2),
            (p.get("EntityRef", {}).get("name", "") or "").lower().strip(),
        )
        groups[key].append(p)

    dupes = []
    for key, txns in groups.items():
        if len(txns) < 2:
            continue
        txns.sort(key=lambda x: x.get("TxnDate", ""))
        for i in range(len(txns)):
            for j in range(i + 1, len(txns)):
                d1 = datetime.strptime(txns[i]["TxnDate"], "%Y-%m-%d")
                d2 = datetime.strptime(txns[j]["TxnDate"], "%Y-%m-%d")
                if abs((d2 - d1).days) <= tolerance_days:
                    dupes.append((txns[i], txns[j]))

    if not dupes:
        return f"No potential duplicates found between {start_date} and {end_date}. Books look clean!"

    lines = [f"## Potential Duplicates ({len(dupes)} pairs found)\n"]
    for a, b in dupes:
        lines.append(f"**{a.get('EntityRef', {}).get('name', 'Unknown')}** — {fmt(float(a.get('TotalAmt', 0)))}:")
        lines.append(f"  1. {a['TxnDate']} (ID: {a['Id']}) — {a.get('PrivateNote', '') or 'no memo'}")
        lines.append(f"  2. {b['TxnDate']} (ID: {b['Id']}) — {b.get('PrivateNote', '') or 'no memo'}")
        lines.append("")
    lines.append("Review each pair and void the duplicate using `qb_void_transaction`.")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_auto_categorize_suggestions(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """Suggest categories for uncategorized transactions based on vendor history.
    Analyzes past categorization patterns to recommend correct accounts. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    # Get uncategorized purchases
    accts = await qb_query("SELECT Id FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    acct_list = accts.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return "No uncategorized accounts found."

    uncategorized = []
    for acct in acct_list:
        q = (f"SELECT * FROM Purchase WHERE AccountRef = '{acct['Id']}' "
             f"AND TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}")
        try:
            result = await qb_query(q)
            uncategorized.extend(result.get("QueryResponse", {}).get("Purchase", []))
        except Exception:
            continue

    if not uncategorized:
        return "No uncategorized transactions found to categorize."

    # Build vendor → account history from categorized purchases
    all_purchases = await qb_query_all(f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500")
    categorized = all_purchases.get("QueryResponse", {}).get("Purchase", [])

    from collections import Counter
    vendor_history = {}
    for p in categorized:
        vendor = (p.get("EntityRef", {}).get("name", "") or "").lower().strip()
        if not vendor:
            continue
        line_items = p.get("Line", [])
        for li in line_items:
            detail = li.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name and "uncategorized" not in acct_name.lower():
                if vendor not in vendor_history:
                    vendor_history[vendor] = Counter()
                vendor_history[vendor][acct_name] += 1

    lines = [f"## Auto-Categorize Suggestions ({len(uncategorized)} transactions)\n"]
    for p in uncategorized:
        vendor = (p.get("EntityRef", {}).get("name", "") or "").lower().strip()
        date = p.get("TxnDate", "")
        amt = float(p.get("TotalAmt", 0))
        suggestion = "No history — manual review needed"
        if vendor in vendor_history:
            top = vendor_history[vendor].most_common(1)
            if top:
                suggestion = f"→ **{top[0][0]}** (based on {top[0][1]} past transactions)"

        lines.append(f"- {date} | {p.get('EntityRef', {}).get('name', 'Unknown')} | {fmt(amt)} | {suggestion} | ID: {p.get('Id')}")

    lines.append("\nUse `qb_update_transaction` to apply the suggested categories.")
    return "\n".join(lines)


# ===================================================================
# BATCH OPERATIONS
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_batch_create_expenses(expenses_json: str, tax_code: str = "") -> str:
    """Create multiple expenses in one call. expenses_json is a JSON array of objects:
    [{"vendor_name": "...", "amount": 100, "account_name": "...", "date": "YYYY-MM-DD", "description": "..."}].
    Useful for importing invoices or bulk expense entry.
    Canada/global editions: tax_code applies a sales tax code to every expense, e.g. 'HST ON'; per-item override via a 'tax_code' key in the JSON objects."""
    try:
        expenses = json.loads(expenses_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON. Provide a JSON array of expense objects."

    if not isinstance(expenses, list):
        return "Error: expenses_json must be a JSON array."

    region = (await _get_region())["region"]
    default_tax_id = None
    tax_cache: dict = {}
    if region != "US" and tax_code:
        try:
            default_tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)

    results = []
    errors = []
    for i, exp in enumerate(expenses):
        try:
            vendor_name = exp.get("vendor_name", "Unknown")
            amount = float(exp.get("amount", 0))
            account_name = exp.get("account_name", "")
            date = exp.get("date", datetime.now().strftime("%Y-%m-%d"))
            description = exp.get("description", "")
            payment_method = exp.get("payment_method", "")

            # Resolve this item's tax code before any create calls
            item_tax_id = default_tax_id
            if region != "US":
                item_code = str(exp.get("tax_code", "") or "").strip()
                if item_code:
                    if item_code not in tax_cache:
                        tax_cache[item_code] = (await _resolve_tax_code(item_code))[0]
                    item_tax_id = tax_cache[item_code]
                if not item_tax_id:
                    errors.append(f"#{i+1}: ❌ {vendor_name} — {_TAX_CODE_REQUIRED_MSG}")
                    continue

            # Look up vendor
            vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
            vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
            if not vendor_list:
                # Create vendor
                new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
                vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
            else:
                vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

            # Look up expense account
            accounts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
            acct_list = accounts.get("QueryResponse", {}).get("Account", [])
            if not acct_list:
                errors.append(f"#{i+1}: Account '{account_name}' not found")
                continue
            acct_ref = {"value": acct_list[0]["Id"], "name": acct_list[0]["Name"]}

            # Look up payment account if specified
            pay_ref = None
            if payment_method:
                pay_accts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{payment_method}%' MAXRESULTS 1")
                pay_list = pay_accts.get("QueryResponse", {}).get("Account", [])
                if pay_list:
                    pay_ref = {"value": pay_list[0]["Id"], "name": pay_list[0]["Name"]}

            body = {
                "PaymentType": "Cash",
                "TxnDate": date,
                "EntityRef": vendor_ref,
                "Line": [{
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
                    "Description": description,
                }],
            }
            if pay_ref:
                body["AccountRef"] = pay_ref
            _apply_global_tax(body, "Line", "AccountBasedExpenseLineDetail",
                              item_tax_id, False, region)

            resp = await qb_request("POST", "purchase", json_body=body)
            txn_id = resp.get("Purchase", {}).get("Id", "?")
            results.append(f"#{i+1}: ✅ {date} | {vendor_name} | {fmt(amount)} → {account_name} (ID: {txn_id})")

        except Exception as e:
            errors.append(f"#{i+1}: ❌ {exp.get('vendor_name', '?')} — {str(e)}")

    lines = [f"## Batch Expense Creation Results\n"]
    lines.append(f"**Succeeded:** {len(results)} | **Failed:** {len(errors)}\n")
    if results:
        lines.append("### Created:")
        lines.extend(results)
    if errors:
        lines.append("\n### Errors:")
        lines.extend(errors)
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_batch_create_bills(bills_json: str, tax_code: str = "") -> str:
    """Create multiple bills (accounts payable) in one call. bills_json is a JSON array:
    [{"vendor_name": "...", "amount": 100, "account_name": "...", "date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD", "description": "..."}].
    Useful for importing vendor invoices from email extraction.
    Canada/global editions: tax_code applies a sales tax code to every bill, e.g. 'HST ON'; per-item override via a 'tax_code' key in the JSON objects."""
    try:
        bills = json.loads(bills_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON. Provide a JSON array of bill objects."

    region = (await _get_region())["region"]
    default_tax_id = None
    tax_cache: dict = {}
    if region != "US" and tax_code:
        try:
            default_tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)

    results = []
    errors = []
    for i, bill in enumerate(bills):
        try:
            vendor_name = bill.get("vendor_name", "Unknown")
            amount = float(bill.get("amount", 0))
            account_name = bill.get("account_name", "")
            date = bill.get("date", datetime.now().strftime("%Y-%m-%d"))
            due_date = bill.get("due_date", date)
            description = bill.get("description", "")

            # Resolve this item's tax code before any create calls
            item_tax_id = default_tax_id
            if region != "US":
                item_code = str(bill.get("tax_code", "") or "").strip()
                if item_code:
                    if item_code not in tax_cache:
                        tax_cache[item_code] = (await _resolve_tax_code(item_code))[0]
                    item_tax_id = tax_cache[item_code]
                if not item_tax_id:
                    errors.append(f"#{i+1}: ❌ {vendor_name} — {_TAX_CODE_REQUIRED_MSG}")
                    continue

            # Look up or create vendor
            vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
            vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
            if not vendor_list:
                new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
                vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
            else:
                vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

            # Look up expense account
            accounts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
            acct_list = accounts.get("QueryResponse", {}).get("Account", [])
            if not acct_list:
                errors.append(f"#{i+1}: Account '{account_name}' not found")
                continue
            acct_ref = {"value": acct_list[0]["Id"], "name": acct_list[0]["Name"]}

            body = {
                "VendorRef": vendor_ref,
                "TxnDate": date,
                "DueDate": due_date,
                "Line": [{
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
                    "Description": description,
                }],
            }
            _apply_global_tax(body, "Line", "AccountBasedExpenseLineDetail",
                              item_tax_id, False, region)

            resp = await qb_request("POST", "bill", json_body=body)
            bill_id = resp.get("Bill", {}).get("Id", "?")
            results.append(f"#{i+1}: ✅ {date} | {vendor_name} | {fmt(amount)} → {account_name} (Bill ID: {bill_id})")

        except Exception as e:
            errors.append(f"#{i+1}: ❌ {bill.get('vendor_name', '?')} — {str(e)}")

    lines = [f"## Batch Bill Creation Results\n"]
    lines.append(f"**Succeeded:** {len(results)} | **Failed:** {len(errors)}\n")
    if results:
        lines.append("### Created:")
        lines.extend(results)
    if errors:
        lines.append("\n### Errors:")
        lines.extend(errors)
    return "\n".join(lines)


# ===================================================================
# ADVANCED REPORTS — Period Comparison, Runway, Burn Rate
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_compare_periods(report_type: str, period1_start: str, period1_end: str, period2_start: str, period2_end: str) -> str:
    """Compare two time periods side-by-side. report_type: 'ProfitAndLoss' or 'BalanceSheet'.
    Shows each period's totals and the dollar/percentage change. Dates in YYYY-MM-DD."""
    if report_type not in ("ProfitAndLoss", "BalanceSheet"):
        return "Error: report_type must be 'ProfitAndLoss' or 'BalanceSheet'."

    def extract_rows(report_data):
        rows = {}
        def _walk(row_list, prefix=""):
            for section in row_list:
                col_data = section.get("ColData", [])
                if len(col_data) >= 2:
                    name = col_data[0].get("value", "")
                    try:
                        val = float(col_data[-1].get("value", "0"))
                    except (ValueError, TypeError):
                        val = 0
                    full_name = f"{prefix}{name}" if prefix else name
                    rows[full_name] = val
                summary = section.get("Summary", {})
                if summary:
                    cols = summary.get("ColData", [])
                    if len(cols) >= 2:
                        try:
                            rows[cols[0].get("value", "")] = float(cols[-1].get("value", "0"))
                        except (ValueError, TypeError):
                            pass
                nested = section.get("Rows", {}).get("Row", [])
                if nested:
                    header = section.get("Header", {}).get("ColData", [{}])
                    group_name = header[0].get("value", "") if header else ""
                    _walk(nested, f"{group_name} > " if group_name else prefix)
            return rows
        report_rows = report_data.get("Rows", {}).get("Row", [])
        _walk(report_rows)
        return rows

    r1 = await qb_request("GET", f"reports/{report_type}", params={
        "start_date": period1_start, "end_date": period1_end
    })
    r2 = await qb_request("GET", f"reports/{report_type}", params={
        "start_date": period2_start, "end_date": period2_end
    })

    rows1 = extract_rows(r1)
    rows2 = extract_rows(r2)
    all_keys = sorted(set(list(rows1.keys()) + list(rows2.keys())))

    lines = [f"## {report_type} Period Comparison\n"]
    lines.append(f"| Account | {period1_start}→{period1_end} | {period2_start}→{period2_end} | Change | % Change |")
    lines.append("|---|---|---|---|---|")

    for key in all_keys:
        v1 = rows1.get(key, 0)
        v2 = rows2.get(key, 0)
        change = v2 - v1
        pct = (change / abs(v1) * 100) if v1 != 0 else 0
        sign = "+" if change >= 0 else ""
        lines.append(f"| {key} | {fmt(v1)} | {fmt(v2)} | {sign}{fmt(change)} | {sign}{pct:.1f}% |")

    return "\n".join(lines)


def _pl_income_expense_totals(pl_result: dict) -> tuple:
    """(total_income, total_expenses) as positive magnitudes from a P&L report.

    Income comes from the **Total Income** section ONLY — summary labels
    containing net/gross/operating (Net Income, Gross Profit, Net Operating
    Income) are excluded, because matching a bare "income" substring on those is
    how the burn/runway tools were silently reading *Net Income* (a negative) as
    revenue and double-counting the burn. Expenses are summed across all expense
    sections. Both are >= 0 so callers compute burn = expenses - income."""
    income = 0.0
    expenses = 0.0
    for section in pl_result.get("Rows", {}).get("Row", []):
        cols = section.get("Summary", {}).get("ColData", [])
        if len(cols) < 2:
            continue
        label = cols[0].get("value", "").lower().strip()
        try:
            val = float(cols[-1].get("value", "0") or 0)
        except (ValueError, TypeError):
            val = 0.0
        if "income" in label and not any(w in label for w in ("net", "gross", "operating")):
            income += val
        elif "expense" in label and "net" not in label:
            expenses += abs(val)
    return max(0.0, income), expenses


async def _bank_cash_on_hand() -> float:
    """Sum of Bank-type account balances (cash on hand). Queries Account
    directly — the balance-sheet 'bank' section-header scan missed nested rows."""
    try:
        r = await qb_query("SELECT * FROM Account WHERE AccountType = 'Bank' MAXRESULTS 50")
        return sum(float(a.get("CurrentBalance", 0) or 0)
                   for a in r.get("QueryResponse", {}).get("Account", []))
    except Exception:
        return 0.0


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_monthly_burn_rate(months_back: int = 6) -> str:
    """Calculate monthly burn rate based on the last N months of expenses.
    Returns monthly totals, average burn, and trend. Useful for runway planning."""
    from datetime import date
    today = date.today()
    monthly_data = []

    for i in range(months_back, 0, -1):
        # Calculate month start/end
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_start = f"{y}-{m:02d}-01"
        if m == 12:
            month_end = f"{y}-12-31"
        else:
            next_m_start = date(y if m < 12 else y + 1, (m % 12) + 1, 1)
            month_end = (next_m_start - timedelta(days=1)).strftime("%Y-%m-%d")

        result = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": month_start, "end_date": month_end
        })

        # Income (Total Income, not Net Income) + summed expenses, both positive
        total_income, total_expense = _pl_income_expense_totals(result)

        from calendar import month_abbr
        monthly_data.append({
            "month": f"{month_abbr[m]} {y}",
            "expenses": total_expense,
            "income": total_income,
            "net": total_income - total_expense,
        })

    avg_burn = sum(d["expenses"] for d in monthly_data) / len(monthly_data) if monthly_data else 0
    avg_income = sum(d["income"] for d in monthly_data) / len(monthly_data) if monthly_data else 0
    avg_net = sum(d["net"] for d in monthly_data) / len(monthly_data) if monthly_data else 0

    lines = ["## Monthly Burn Rate Analysis\n"]
    lines.append("| Month | Income | Expenses | Net |")
    lines.append("|---|---|---|---|")
    for d in monthly_data:
        lines.append(f"| {d['month']} | {fmt(d['income'])} | {fmt(d['expenses'])} | {fmt(d['net'])} |")
    lines.append(f"\n**Average Monthly Burn:** {fmt(avg_burn)}")
    lines.append(f"**Average Monthly Income:** {fmt(avg_income)}")
    lines.append(f"**Average Monthly Net:** {fmt(avg_net)}")

    # Trend (is burn increasing or decreasing?)
    if len(monthly_data) >= 3:
        first_half = sum(d["expenses"] for d in monthly_data[:len(monthly_data)//2])
        second_half = sum(d["expenses"] for d in monthly_data[len(monthly_data)//2:])
        if second_half > first_half * 1.1:
            lines.append("\n⚠️ **Trend: Expenses increasing** — burn rate growing over time.")
        elif second_half < first_half * 0.9:
            lines.append("\n✅ **Trend: Expenses decreasing** — spending is tightening.")
        else:
            lines.append("\n📊 **Trend: Stable** — expenses roughly consistent.")

    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_runway_calculator(current_cash: float = 0, monthly_revenue: float = 0, monthly_expenses: float = 0) -> str:
    """Calculate runway (months until cash runs out). If amounts are 0, auto-calculates from last 3 months of QB data.
    Returns months of runway and recommendations."""
    if current_cash == 0:
        current_cash = await _bank_cash_on_hand()

    if monthly_expenses == 0 or monthly_revenue == 0:
        from datetime import date
        today = date.today()
        start_3mo = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        result = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": start_3mo, "end_date": end
        })
        income, expenses = _pl_income_expense_totals(result)
        monthly_revenue = income / 3
        monthly_expenses = expenses / 3

    net_burn = monthly_expenses - monthly_revenue

    header = (f"## Runway Calculator\n\n"
              f"**Cash on hand:** {fmt(current_cash)}\n"
              f"**Monthly revenue:** {fmt(monthly_revenue)}\n"
              f"**Monthly expenses:** {fmt(monthly_expenses)}\n")

    if net_burn <= 0:
        return (header + f"\n✅ **Cash-flow positive!** Revenue covers expenses "
                f"with {fmt(abs(net_burn))}/month to spare — no cash runway limit "
                f"at the current rate.")

    if current_cash <= 0:
        return (header + f"**Net monthly burn:** {fmt(net_burn)}\n\n"
                f"🔴 **No runway** — the cash balance is {fmt(current_cash)} "
                f"(zero or negative) while burning {fmt(net_burn)}/month. Raise "
                f"cash or cut costs immediately.")

    runway_months = current_cash / net_burn

    lines = ["## Runway Calculator\n"]
    lines.append(f"**Cash on hand:** {fmt(current_cash)}")
    lines.append(f"**Monthly revenue:** {fmt(monthly_revenue)}")
    lines.append(f"**Monthly expenses:** {fmt(monthly_expenses)}")
    lines.append(f"**Net monthly burn:** {fmt(net_burn)}")
    lines.append(f"\n### 🏃 Runway: {runway_months:.1f} months")

    if runway_months < 3:
        lines.append("\n🔴 **CRITICAL** — Less than 3 months of runway. Immediate action needed.")
    elif runway_months < 6:
        lines.append("\n🟡 **WARNING** — Less than 6 months. Begin fundraising or cost-cutting.")
    elif runway_months < 12:
        lines.append("\n🟢 **OK** — 6-12 months of runway. Plan ahead for sustainability.")
    else:
        lines.append("\n✅ **HEALTHY** — 12+ months of runway.")

    return "\n".join(lines)


# ===================================================================
# TAX TOOLS — Schedule C, Quarterly Estimates, Deductions, Depreciation
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "For Canadian books use qb_t2125_summary.")
async def qb_schedule_c(tax_year: str = "2024") -> str:
    """Generate IRS Schedule C (Profit or Loss from Business) line-by-line mapping.
    Maps QuickBooks expense categories to Schedule C lines for tax filing. tax_year: YYYY format."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end,
        "summarize_column_by": "Total"
    })

    # Income (Gross receipts) from the P&L Income section summary
    report_rows = result.get("Rows", {}).get("Row", [])
    total_income = 0.0
    for section in report_rows:
        cols = section.get("Summary", {}).get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0") or 0)
            except (ValueError, TypeError):
                val = 0.0
            if "income" in label and "net" not in label:
                total_income = val

    # Expenses: P&L period activity, word-boundary mapped, nothing dropped
    # (unmatched accounts flow to Line 27a so Line 28 reconciles to the P&L).
    expense_dict = _extract_pl_expense_accounts(result)
    sc_lines = _map_expenses_to_schedule_c(expense_dict)
    pl_total = _pl_expense_total(result)

    def _sc_line_sort(item):
        m = _re.search(r"Line (\d+)([a-z]?)", item[0])
        return (int(m.group(1)) if m else 999, m.group(2) if m else "")

    lines = [f"## IRS Schedule C — {tax_year}\n"]
    lines.append(f"**Line 1 — Gross receipts:** {fmt(total_income)}")
    lines.append(f"**Line 7 — Gross income:** {fmt(total_income)}\n")

    lines.append("### Expenses:")
    total_mapped = 0.0
    home_flagged = False
    for line_name, data in sorted(sc_lines.items(), key=_sc_line_sort):
        flag = " ⚠️ (review — may belong on Form 8829)" if data["home"] else ""
        lines.append(f"\n**{line_name}: {fmt(data['amount'])}**{flag}")
        for acct, amt in data["accounts"]:
            lines.append(f"  - {acct}: {fmt(amt)}")
        total_mapped += data["amount"]
        home_flagged = home_flagged or data["home"]

    lines.append(f"\n**Line 28 — Total expenses: {fmt(total_mapped)}**")
    if pl_total and abs(total_mapped - pl_total) > 0.01:
        lines.append(
            f"⚠️ Does not reconcile to P&L expenses ({fmt(pl_total)}) — "
            f"difference {fmt(abs(total_mapped - pl_total))}. Review.")
    net_profit = total_income - total_mapped
    lines.append(f"**Line 31 — Net profit (loss): {fmt(net_profit)}**")
    if home_flagged:
        lines.append(
            "\n*Items flagged ⚠️ (home office, homeowner insurance, home "
            "utilities) generally belong on Form 8829, not directly on "
            "Schedule C — review before filing.*")

    if net_profit < 0:
        lines.append(f"\n📋 **NOL:** This {fmt(abs(net_profit))} loss can be carried forward to offset future income.")

    return "\n".join(lines) + tax_data_footer(int(tax_year))




@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Use qb_estimate_instalments for CRA instalments + CPP.")
async def qb_estimate_quarterly_tax(tax_year: str = "2025", filing_status: str = "single", state: str = "") -> str:
    """Estimate quarterly tax payments (federal + state) based on YTD P&L.
    filing_status: single, married_joint, married_separate. state: two-letter
    code (MA, CA, ...); auto-detected from the QuickBooks company address
    when omitted."""
    from datetime import date
    today = date.today()
    year = int(tax_year)
    start = f"{year}-01-01"
    end = min(today.strftime("%Y-%m-%d"), f"{year}-12-31")

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })

    total_income = 0
    total_expenses = 0
    report_rows = result.get("Rows", {}).get("Row", [])
    for section in report_rows:
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val
            elif "expense" in label:
                total_expenses = abs(val)

    net_income = total_income - total_expenses

    # Self-employment tax + federal brackets from the tax-data registry.
    # Future years fall back to the latest tables WITH a visible note
    # (Constitution: never silently reuse stale rates).
    try:
        ss_wage_base, _ss_note = tax_value_or_latest("SS_WAGE_BASE", year)
        params, _fed_note = tax_value_or_latest("FED_BRACKETS", year)
    except TaxDataError as e:
        return str(e)
    vintage_notes = [n for n in (_ss_note, _fed_note) if n]

    se_base = net_income * _SE_NET_EARNINGS_FACTOR if net_income > 0 else 0
    se_tax = (min(se_base, ss_wage_base) * _SE_SS_RATE
              + se_base * _SE_MEDICARE_RATE)

    adjusted_income = net_income - (se_tax / 2)  # SE deduction
    standard_deduction = (params["std_single"]
                          if filing_status in ("single", "married_separate")
                          else params["std_married"])

    taxable = max(0, adjusted_income - standard_deduction)
    thresholds = (params["single"] if filing_status in ("single", "married_separate")
                  else params["married_joint"])
    sizes = [thresholds[0]] + [thresholds[i] - thresholds[i - 1]
                               for i in range(1, len(thresholds))] + [float("inf")]
    brackets = list(zip(sizes, _RATES))
    federal_tax = 0

    remaining = taxable
    for bracket_size, rate in brackets:
        if remaining <= 0:
            break
        amount = min(remaining, bracket_size)
        federal_tax += amount * rate
        remaining -= amount

    # State tax estimate
    state = state.strip().upper()
    if not state:
        state = (await _get_region()).get("subdivision", "")
    entry = _US_STATE_TAX.get(state)
    if entry:
        rate, kind = entry
        state_tax = max(0, net_income) * rate
        if kind == "none":
            state_rate_desc = f"{state} — no state income tax on earned income"
        elif kind == "flat":
            state_rate_desc = f"{state} flat {rate * 100:g}% income tax"
        else:
            state_rate_desc = f"{state} progressive — ~{rate * 100:g}% effective-rate approximation"
    else:
        state_tax = max(0, net_income) * 0.05  # Generic estimate
        state_rate_desc = (f"{state or 'state unknown'} — generic ~5% estimate "
                           f"(pass state=XX for a better one)")

    total_annual = federal_tax + se_tax + state_tax
    quarterly = total_annual / 4

    # Determine which quarters remain
    quarter_due = {1: "Apr 15", 2: "Jun 15", 3: "Sep 15", 4: "Jan 15 (next year)"}
    current_quarter = (today.month - 1) // 3 + 1

    lines = [f"## Estimated Quarterly Tax — {tax_year}\n"]
    for note in vintage_notes:
        lines.append(f"⚠️ {note}")
    lines.append(f"**YTD Net Income:** {fmt(net_income)} ({start} to {end})")
    lines.append(f"**Filing Status:** {filing_status}")
    lines.append(f"**State:** {state or '(unknown)'}\n")

    lines.append("### Tax Breakdown:")
    lines.append(f"- Federal income tax: {fmt(federal_tax)}")
    lines.append(f"- Self-employment tax: {fmt(se_tax)}")
    lines.append(f"  (Social Security: {fmt(min(se_base, ss_wage_base) * 0.124)}, Medicare: {fmt(se_base * 0.029)})")
    lines.append(f"- {state_rate_desc}: {fmt(state_tax)}")
    lines.append(f"\n**Total estimated annual tax: {fmt(total_annual)}**")
    lines.append(f"**Each quarterly payment: {fmt(quarterly)}**")
    lines.append("\n*State tax is a planning approximation — flat-state rates "
                 "are statutory; progressive states use a rough effective rate.*")

    lines.append(f"\n### Quarterly Due Dates:")
    for q, due in quarter_due.items():
        status = "✅ Past" if q < current_quarter else ("⏳ Current" if q == current_quarter else "📅 Upcoming")
        lines.append(f"  Q{q}: {due} — {fmt(quarterly)} ({status})")

    if net_income <= 0:
        lines.append(f"\n📋 **Note:** With a net loss, no estimated payments are due. You may carry forward this NOL.")

    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "CA deduction guidance will come from qb_t2125_summary.")
async def qb_deduction_finder(tax_year: str = "") -> str:
    """Analyze books for commonly missed tax deductions. Checks for home office,
    vehicle expenses, health insurance, retirement contributions, startup costs,
    Section 179, and more. Returns suggestions with estimated savings.
    tax_year defaults to the current year."""
    from datetime import date as _date
    if not tax_year:
        tax_year = str(_date.today().year)
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })

    expense_dict = {}
    total_income = 0
    total_expenses = 0
    report_rows = result.get("Rows", {}).get("Row", [])

    def extract_all(rows, out):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    out[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_all(nested, out)

    for section in report_rows:
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            # Accumulate across ALL income/expense sections — a P&L has both
            # "Expenses" and "Other Expenses" as separate top-level sections, so
            # assigning (=) here kept only the last one ("Other Expenses"), badly
            # understating the total and the NOL. Sum them instead.
            if "income" in label and "net" not in label:
                total_income += val
            elif "expense" in label and "net" not in label:
                total_expenses += abs(val)
        nested = section.get("Rows", {}).get("Row", [])
        if nested:
            extract_all(nested, expense_dict)

    findings = []
    estimated_savings = 0

    # Check for home office
    has_home_office = any("home" in k.lower() and "office" in k.lower() for k in expense_dict)
    has_rent = any("rent" in k.lower() for k in expense_dict)
    if not has_home_office and not has_rent:
        findings.append({
            "deduction": "Home Office Deduction (IRS Form 8829)",
            "status": "🔴 NOT CLAIMED",
            "details": "Simplified: $5/sq ft up to 300 sq ft = $1,500. Regular method may be higher with mortgage interest, property taxes, utilities, insurance.",
            "estimate": 1500,
        })
        estimated_savings += 1500

    # Check for vehicle expenses
    has_vehicle = any("auto" in k.lower() or "vehicle" in k.lower() or "car" in k.lower() or "mileage" in k.lower() for k in expense_dict)
    if not has_vehicle:
        findings.append({
            "deduction": "Vehicle Expenses (Standard Mileage or Actual)",
            "status": "🔴 NOT CLAIMED",
            "details": (f"Standard mileage: "
                        + ", ".join(f"{c}¢/mile ({y})" for y, c in sorted(_STD_MILEAGE_CENTS.items()))
                        + ". Track business miles for meetings, supply runs, etc."),
            "estimate": 1000,
        })
        estimated_savings += 1000

    # Check for health insurance
    has_health = any("health" in k.lower() or "medical" in k.lower() or "dental" in k.lower() for k in expense_dict)
    if not has_health:
        findings.append({
            "deduction": "Self-Employed Health Insurance (Schedule 1, Line 17)",
            "status": "🟡 CHECK IF APPLICABLE",
            "details": "100% of health/dental/vision premiums deductible above-the-line. Must not have employer coverage.",
            "estimate": 6000,
        })
        estimated_savings += 6000

    # Check for retirement contributions
    has_retirement = any("retire" in k.lower() or "401k" in k.lower() or "sep" in k.lower() or "ira" in k.lower() for k in expense_dict)
    if not has_retirement:
        ret_year = max(_RETIREMENT_LIMITS)
        ret = _RETIREMENT_LIMITS[ret_year]
        findings.append({
            "deduction": "Retirement Contributions (SEP-IRA / Solo 401k)",
            "status": "🟡 OPPORTUNITY",
            "details": (f"SEP-IRA: up to 25% of net SE income (max ${ret['sep_max']:,} "
                        f"for {ret_year}). Solo 401k: ${ret['solo_401k_deferral']:,} "
                        f"employee + 25% employer."),
            "estimate": 0,
        })

    # Check for depreciation
    has_depreciation = any("deprec" in k.lower() or "section 179" in k.lower() for k in expense_dict)
    if not has_depreciation:
        # Check if there are asset purchases
        findings.append({
            "deduction": "Section 179 / Bonus Depreciation",
            "status": "🟡 CHECK ASSETS",
            "details": "Equipment, computers, furniture can be expensed immediately: §179 up to $2.56M (2026, active business required) or 100% bonus depreciation (permanent under OBBBA for property acquired after Jan 19, 2025; no income limit).",
            "estimate": 0,
        })

    # Check for education/training
    has_education = any("education" in k.lower() or "training" in k.lower() or "course" in k.lower() for k in expense_dict)
    if not has_education:
        findings.append({
            "deduction": "Education & Training",
            "status": "🟡 CHECK",
            "details": "Courses, certifications, books, conferences related to your business are deductible.",
            "estimate": 500,
        })
        estimated_savings += 500

    # Check for startup costs
    net_income = total_income - total_expenses
    if net_income < 0 and total_income == 0:
        findings.append({
            "deduction": "Section 195 Startup Costs",
            "status": "🟡 MAY APPLY",
            "details": "First $5,000 of startup costs deductible in year 1 (phased out dollar-for-dollar above $50K). Remainder amortized over 180 months from commencement — run qb_startup_cost_analysis for the schedule.",
            "estimate": 5000,
        })
        estimated_savings += 5000

    # R&D Tax Credit check (for tech/AI companies)
    has_software = any("software" in k.lower() or "cloud" in k.lower() or "hosting" in k.lower() for k in expense_dict)
    if has_software:
        sw_total = sum(abs(v) for k, v in expense_dict.items() if any(kw in k.lower() for kw in ["software", "cloud", "hosting", "api"]))
        findings.append({
            "deduction": "R&D Tax Credit (Form 6765)",
            "status": "🟡 LIKELY ELIGIBLE",
            "details": f"Software/cloud/API spend of {fmt(sw_total)} suggests R&D activity. Credit = ~10% of qualified research expenses. Startups can offset payroll taxes up to $500K/year.",
            "estimate": sw_total * 0.10,
        })
        estimated_savings += sw_total * 0.10
        findings.append({
            "deduction": "§174A Domestic R&E Expensing",
            "status": "🟢 RESTORED",
            "details": "OBBBA restored 100% immediate expensing of domestic research & software development costs (§174A), ending the 5-year amortization required for 2022–2024. Small businesses may amend/elect to accelerate remaining unamortized 2022–2024 R&E. Foreign R&E remains 15-year.",
            "estimate": 0,
        })

    # NOL carryforward
    if net_income < 0:
        findings.append({
            "deduction": "Net Operating Loss (NOL) Carryforward",
            "status": "📋 AVAILABLE",
            "details": f"NOL of {fmt(abs(net_income))} can offset up to 80% of future taxable income. Carries forward indefinitely (federal) or 20 years (MA).",
            "estimate": 0,
        })

    lines = [f"## Deduction Finder — {tax_year}\n"]
    lines.append(f"**Total Income:** {fmt(total_income)} | **Total Expenses:** {fmt(total_expenses)} | **Net:** {fmt(net_income)}\n")

    for f in findings:
        lines.append(f"### {f['status']} {f['deduction']}")
        lines.append(f"{f['details']}")
        if f['estimate'] > 0:
            lines.append(f"**Estimated value: {fmt(f['estimate'])}**")
        lines.append("")

    if estimated_savings > 0:
        lines.append(f"\n### 💰 Total Estimated Unclaimed Deductions: {fmt(estimated_savings)}")
        # Rough tax savings at 30% effective rate
        lines.append(f"**Potential tax savings: ~{fmt(estimated_savings * 0.30)}** (at ~30% effective rate)")

    return "\n".join(lines) + tax_data_footer()


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Use qb_cca_schedule for CCA classes.")
async def qb_depreciation_schedule(tax_year: str = "") -> str:
    """Generate a depreciation schedule for all fixed assets. Shows Section 179,
    MACRS, and accumulated depreciation for tax year (defaults to the current
    year). Pulls from QB asset accounts."""
    from datetime import date as _date
    if not tax_year:
        tax_year = str(_date.today().year)
    # Fetch fixed-asset accounts (cost accounts + accumulated-depreciation contras)
    assets = await qb_query(
        "SELECT * FROM Account WHERE AccountType IN ('Fixed Asset', 'Other Asset') "
        "MAXRESULTS 100")
    acct_list = assets.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return f"No fixed asset accounts found for {tax_year}."

    def _is_contra(nm: str) -> bool:
        low = (nm or "").lower()
        return ("accum" in low and "dep" in low) or low.strip().startswith("less")

    def _tokens(nm: str) -> set:
        stripped = _re.sub(
            r"accumulated|accum\.?|depreciation|deprec\.?|amortization|less|"
            r"[-–—:()]", " ", nm or "", flags=_re.IGNORECASE)
        return {t.lower() for t in stripped.split() if len(t) > 2}

    contras, costs = [], []
    for a in acct_list:
        nm = a.get("Name", "")
        bal = float(a.get("CurrentBalance", 0) or 0)
        (contras if _is_contra(nm) else costs).append((nm, bal, _tokens(nm)))

    def _accum_for(cost_tokens: set) -> float:
        return sum(abs(cb) for _, cb, ct in contras if ct & cost_tokens)

    def _method_life(nm: str):
        low = nm.lower()
        if any(k in low for k in ("computer", "laptop", "tablet", "server", "hardware")):
            return "MACRS 5-yr", 5
        if "furniture" in low or "fixture" in low:
            return "MACRS 7-yr", 7
        if any(k in low for k in ("vehicle", "auto", "truck", "car")):
            return "MACRS 5-yr", 5
        if any(k in low for k in ("building", "improvement", "real property")):
            return "SL 39-yr", 39
        if any(k in low for k in ("land",)):
            return "Not depreciable", 0
        return "MACRS 5-yr (default)", 5

    lines = [
        f"## Fixed-Asset Register — {tax_year}\n",
        "### On the books (from QuickBooks)",
        "| Asset | Cost basis | Accumulated deprec. | Net book value | Est. method / life |",
        "|---|---|---|---|---|",
    ]
    total_cost = total_accum = total_net = 0.0
    asset_rows = []  # (name, cost_basis, method, life)
    for name, bal, toks in costs:
        accum = _accum_for(toks)
        if abs(bal) < 1 and accum == 0:
            continue
        net = bal
        cost = net + accum  # QBO CurrentBalance is net book value; gross = net + accum
        method, life = _method_life(name)
        total_cost += cost
        total_accum += accum
        total_net += net
        asset_rows.append((name, cost, method, life))
        life_s = f"{method}" if life else method
        lines.append(f"| {name} | {fmt(cost)} | {fmt(accum)} | {fmt(net)} | {life_s} |")
    lines.append(
        f"| **Totals** | **{fmt(total_cost)}** | **{fmt(total_accum)}** | "
        f"**{fmt(total_net)}** | |")
    lines.append(
        "\n*Cost basis = net book value + the matched “Accumulated "
        "Depreciation” contra account; where the books don’t separate "
        "them, cost ≈ net. QuickBooks Online’s API does **not** expose "
        "per-asset **acquisition / in-service dates** or the elected "
        "**depreciation method** — confirm those from the purchase invoice "
        "and prior-year Form 4562 before filing. Land is not depreciable.*")

    # Forward-looking tax estimate (illustrative straight-line on cost basis)
    lines.append("\n### Forward-looking tax depreciation estimate")
    lines.append("| Asset | Cost basis | Method | Est. annual (SL) |")
    lines.append("|---|---|---|---|")
    total_est = 0.0
    for name, cost, method, life in asset_rows:
        annual = (cost / life) if life else 0.0
        total_est += annual
        lines.append(f"| {name} | {fmt(cost)} | {method} | {fmt(annual)} |")
    lines.append(f"| **Total** | | | **{fmt(total_est)}** |")
    lines.append(
        "\n*Illustrative straight-line estimate on cost basis. Actual **MACRS**, "
        "**§179** (full first-year expensing up to $2,560,000 for 2026), and "
        "**100% bonus** (permanent for property acquired after Jan 19, 2025) depend "
        "on the in-service year and elections and are applied by your CPA on Form "
        "4562. This estimate will **not** match depreciation **booked in your P&L** "
        "(actual recorded entries) — the two are reconciled at tax time.*")

    return "\n".join(lines) + tax_data_footer()


# ===================================================================
# RECONCILIATION & MATCHING
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_match_invoices_to_transactions(invoices_json: str, start_date: str, end_date: str, tolerance: float = 2.0) -> str:
    """Match extracted invoices against QuickBooks transactions. invoices_json is a JSON array:
    [{"vendor": "...", "amount": 100, "date": "YYYY-MM-DD", "description": "..."}].
    tolerance: dollar amount for fuzzy matching. Returns matched, unmatched, and suggestions."""
    try:
        invoices = json.loads(invoices_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON for invoices."

    # Get all transactions in range
    purchases = await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    txns = purchases.get("QueryResponse", {}).get("Purchase", [])

    matched = []
    unmatched_invoices = []
    used_txn_ids = set()

    for inv in invoices:
        inv_vendor = (inv.get("vendor", "") or "").lower().strip()
        inv_amount = float(inv.get("amount", 0))
        inv_date = inv.get("date", "")
        best_match = None
        best_score = 0

        for txn in txns:
            if txn["Id"] in used_txn_ids:
                continue
            txn_vendor = (txn.get("EntityRef", {}).get("name", "") or "").lower().strip()
            txn_amount = float(txn.get("TotalAmt", 0))
            txn_date = txn.get("TxnDate", "")

            # Score the match
            score = 0
            if abs(txn_amount - inv_amount) <= tolerance:
                score += 50
            if inv_vendor and txn_vendor and (inv_vendor in txn_vendor or txn_vendor in inv_vendor):
                score += 30
            if inv_date == txn_date:
                score += 20
            elif inv_date and txn_date:
                try:
                    d1 = datetime.strptime(inv_date, "%Y-%m-%d")
                    d2 = datetime.strptime(txn_date, "%Y-%m-%d")
                    if abs((d2 - d1).days) <= 7:
                        score += 10
                except (ValueError, TypeError):
                    pass

            if score > best_score and score >= 50:
                best_score = score
                best_match = txn

        if best_match:
            used_txn_ids.add(best_match["Id"])
            matched.append({
                "invoice": inv,
                "transaction": best_match,
                "score": best_score,
            })
        else:
            unmatched_invoices.append(inv)

    lines = [f"## Invoice Matching Results\n"]
    lines.append(f"**Matched:** {len(matched)} | **Unmatched:** {len(unmatched_invoices)} | **Total invoices:** {len(invoices)}\n")

    if matched:
        lines.append("### Matched Invoices:")
        for m in matched:
            inv = m["invoice"]
            txn = m["transaction"]
            lines.append(f"- ✅ {inv.get('vendor', '?')} | Invoice: {fmt(inv.get('amount', 0))} ({inv.get('date', '?')}) → QB: {fmt(float(txn.get('TotalAmt', 0)))} ({txn.get('TxnDate', '?')}) [Score: {m['score']}]")

    if unmatched_invoices:
        lines.append(f"\n### Unmatched Invoices ({len(unmatched_invoices)} — need to be created):")
        total_unmatched = 0
        for inv in unmatched_invoices:
            amt = float(inv.get("amount", 0))
            lines.append(f"- ❌ {inv.get('vendor', '?')} | {fmt(amt)} | {inv.get('date', '?')} | {inv.get('description', '')}")
            total_unmatched += amt
        lines.append(f"\n**Total unmatched: {fmt(total_unmatched)}**")
        lines.append("\nUse `qb_batch_create_expenses` or `qb_batch_create_bills` to import these.")

    return "\n".join(lines)


# ===================================================================
# UTILITIES — Account Management, Vendor Merge, Fiscal Year Close
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_inactivate_account(account_name: str) -> str:
    """Inactivate a QuickBooks account (hide it from active lists without deleting).
    Useful for cleaning up unused or personal accounts. Requires exact account name."""
    accounts = await qb_query(f"SELECT * FROM Account WHERE Name = '{account_name}' MAXRESULTS 1")
    acct_list = accounts.get("QueryResponse", {}).get("Account", [])

    if not acct_list:
        return f"No account matching '{account_name}' found."

    acct = acct_list[0]
    if not acct.get("Active", True):
        return f"Account '{account_name}' is already inactive."

    balance = float(acct.get("CurrentBalance", 0))
    if abs(balance) > 0.01:
        return f"Cannot inactivate '{account_name}' — it has a balance of {fmt(balance)}. Zero it out first with a journal entry."

    body = {
        "Id": acct["Id"],
        "SyncToken": acct["SyncToken"],
        "Active": False,
        "Name": acct["Name"],
        "AccountType": acct["AccountType"],
    }
    if "AccountSubType" in acct:
        body["AccountSubType"] = acct["AccountSubType"]

    result = await qb_request("POST", "account", json_body=body)
    return f"✅ Account '{account_name}' (ID: {acct['Id']}) has been inactivated."


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_account(name: str, account_type: str, account_sub_type: str = "", description: str = "") -> str:
    """Create a new account in the chart of accounts.
    account_type: Bank, Accounts Receivable, Other Current Asset, Fixed Asset, Other Asset,
    Accounts Payable, Credit Card, Other Current Liability, Long Term Liability, Equity,
    Income, Cost of Goods Sold, Expense, Other Income, Other Expense.
    account_sub_type: varies by type (e.g., 'Checking' for Bank, 'OfficeGeneralAdministrativeExpenses' for Expense)."""
    # QuickBooks caps these locally — validate before POST so the caller gets a
    # useful message instead of raw QBO error 2050.
    if len(name) > 100:
        return f"Account name is {len(name)} characters; QuickBooks allows at most 100."
    if len(description) > 100:
        return f"Description is {len(description)} characters; QuickBooks allows at most 100."
    body = {
        "Name": name,
        "AccountType": account_type,
    }
    if account_sub_type:
        body["AccountSubType"] = account_sub_type
    if description:
        body["Description"] = description

    result = await qb_request("POST", "account", json_body=body)
    new_acct = result.get("Account", {})
    return (f"✅ Created account '{new_acct.get('Name')}' (ID: {new_acct.get('Id')})\n"
            f"  Type: {new_acct.get('AccountType')} / {new_acct.get('AccountSubType', '')}")


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_vendor_summary(start_date: str = "", end_date: str = "", top_n: int = 20) -> str:
    """Rank vendors by total spend within a date range. Shows top N vendors with
    transaction count and total amount. Useful for negotiation and cost analysis.
    Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    result = await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    purchases = result.get("QueryResponse", {}).get("Purchase", [])

    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    from collections import defaultdict
    vendor_totals = defaultdict(lambda: {"count": 0, "total": 0.0})
    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        amt = float(p.get("TotalAmt", 0))
        vendor_totals[vendor]["count"] += 1
        vendor_totals[vendor]["total"] += amt

    sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1]["total"], reverse=True)[:top_n]

    lines = [f"## Top Vendors by Spend: {start_date} to {end_date}\n"]
    lines.append("| Rank | Vendor | Transactions | Total Spend |")
    lines.append("|---|---|---|---|")
    grand_total = 0
    for i, (vendor, data) in enumerate(sorted_vendors, 1):
        lines.append(f"| {i} | {vendor} | {data['count']} | {fmt(data['total'])} |")
        grand_total += data["total"]

    lines.append(f"\n**Total across top {len(sorted_vendors)} vendors: {fmt(grand_total)}**")
    lines.append(f"**Total vendors in period: {len(vendor_totals)}**")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_bill(vendor_name: str, amount: float, account_name: str, date: str, due_date: str = "", description: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a single bill (accounts payable) in QuickBooks.
    vendor_name: payee, amount: total, account_name: expense category, date: YYYY-MM-DD.
    due_date: when payment is due (defaults to date if empty).
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; tax_inclusive=True when amount already includes tax."""
    if not due_date:
        due_date = date

    # Look up or create vendor
    vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
    vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
    if not vendor_list:
        new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
        vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
    else:
        vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

    # Look up expense account
    acct, acct_err = await _resolve_account(account_name)
    if acct_err:
        return acct_err
    acct_ref = {"value": acct["Id"], "name": acct["Name"]}

    body = {
        "VendorRef": vendor_ref,
        "TxnDate": date,
        "DueDate": due_date,
        "Line": [{
            "Amount": amount,
            "DetailType": "AccountBasedExpenseLineDetail",
            "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
            "Description": description,
        }],
    }

    region = (await _get_region())["region"]
    if region != "US":
        if not tax_code:
            return _TAX_CODE_REQUIRED_MSG
        try:
            tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)
        _apply_global_tax(body, "Line", "AccountBasedExpenseLineDetail",
                          tax_id, tax_inclusive, region)

    resp = await qb_request("POST", "bill", json_body=body)
    bill = resp.get("Bill", {})
    return (f"✅ Created bill #{bill.get('Id')}\n"
            f"  Vendor: {vendor_name} | Amount: {fmt(amount)} | Due: {due_date}\n"
            f"  Category: {acct_list[0]['Name']}")


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_profit_loss_by_class(start_date: str = "", end_date: str = "") -> str:
    """Generate P&L report broken down by class/department. Useful for multi-segment businesses.
    Dates in YYYY-MM-DD (default: current year-to-date). Returns nothing if classes aren't used."""
    start_date, end_date = _ytd_range(start_date, end_date)
    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date, "end_date": end_date,
        "summarize_column_by": "Class"
    })

    header = result.get("Header", {})
    columns = result.get("Columns", {}).get("Column", [])
    col_names = [c.get("ColTitle", "") for c in columns]

    if len(col_names) <= 2:
        return "No class data found. This report requires QuickBooks classes to be enabled."

    lines = [f"## Profit & Loss by Class: {start_date} to {end_date}\n"]
    report_rows = result.get("Rows", {}).get("Row", [])
    _parse_report_rows(report_rows, lines)
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_income_summary(start_date: str = "", end_date: str = "") -> str:
    """Get income grouped by source/category for a date range. Complements qb_expense_summary.
    Shows all income accounts and their totals. Dates in YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date, "end_date": end_date
    })

    income_items = {}
    report_rows = result.get("Rows", {}).get("Row", [])

    def extract_income(rows, out):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    out[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_income(nested, out)

    for section in report_rows:
        header = section.get("Header", {}).get("ColData", [{}])
        label = header[0].get("value", "").lower() if header else ""
        if "income" in label and "net" not in label:
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_income(nested, income_items)

    if not income_items:
        return f"No income found between {start_date} and {end_date}."

    lines = [f"## Income Summary: {start_date} to {end_date}\n"]
    total = 0
    for name, amount in sorted(income_items.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- **{name}:** {fmt(amount)}")
        total += amount
    lines.append(f"\n**Total Income: {fmt(total)}**")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_fiscal_year_close_checklist(tax_year: str = "2024") -> str:
    """Generate a year-end close checklist with status checks against QuickBooks data.
    Verifies key items are in order for tax filing: uncategorized transactions, open invoices,
    undeposited funds, equity cleanup, and more."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    checks = []

    # 1. Check for uncategorized transactions
    accts = await qb_query("SELECT Id, Name FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    uncat_accts = accts.get("QueryResponse", {}).get("Account", [])
    uncat_total = 0
    for a in uncat_accts:
        uncat_total += abs(float(a.get("CurrentBalance", 0)))
    if uncat_total > 0:
        checks.append(f"🔴 **Uncategorized transactions:** {fmt(uncat_total)} needs categorization")
    else:
        checks.append("✅ **No uncategorized transactions**")

    # 2. Check for open invoices
    open_invoices = await qb_query(f"SELECT * FROM Invoice WHERE Balance > '0' MAXRESULTS 100")
    inv_list = open_invoices.get("QueryResponse", {}).get("Invoice", [])
    open_balance = sum(float(i.get("Balance", 0)) for i in inv_list)
    if open_balance > 0:
        checks.append(f"🟡 **Open invoices:** {len(inv_list)} invoices, {fmt(open_balance)} outstanding")
    else:
        checks.append("✅ **No open invoices**")

    # 3. Check for undeposited funds
    udf = await qb_query("SELECT * FROM Account WHERE Name = 'Undeposited Funds' MAXRESULTS 1")
    udf_accts = udf.get("QueryResponse", {}).get("Account", [])
    if udf_accts:
        udf_balance = float(udf_accts[0].get("CurrentBalance", 0))
        if abs(udf_balance) > 0:
            checks.append(f"🟡 **Undeposited funds:** {fmt(udf_balance)} — should be deposited or cleared")
        else:
            checks.append("✅ **Undeposited funds: $0.00**")

    # 4. Check Opening Balance Equity
    obe = await qb_query("SELECT * FROM Account WHERE Name = 'Opening Balance Equity' MAXRESULTS 1")
    obe_accts = obe.get("QueryResponse", {}).get("Account", [])
    if obe_accts:
        obe_balance = float(obe_accts[0].get("CurrentBalance", 0))
        if abs(obe_balance) > 0:
            checks.append(f"🟡 **Opening Balance Equity:** {fmt(obe_balance)} — CPA should close to Retained Earnings")
        else:
            checks.append("✅ **Opening Balance Equity: $0.00**")

    # 5. Check for personal accounts still active
    personal_keywords = ["personal", "mortgage", "student loan"]
    all_accts = await qb_query_all("SELECT * FROM Account WHERE Active = true MAXRESULTS 200")
    all_list = all_accts.get("QueryResponse", {}).get("Account", [])
    personal_active = [a for a in all_list if any(kw in a.get("Name", "").lower() for kw in personal_keywords)]
    if personal_active:
        names = ", ".join(a["Name"] for a in personal_active)
        checks.append(f"🟡 **Personal accounts still active:** {names}")
    else:
        checks.append("✅ **No personal accounts active**")

    # 6. P&L summary
    pnl = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })
    net_income = 0
    for section in pnl.get("Rows", {}).get("Row", []):
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2 and "net" in cols[0].get("value", "").lower():
            try:
                net_income = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                pass
    checks.append(f"📊 **{tax_year} Net Income (Loss):** {fmt(net_income)}")

    lines = [f"## Fiscal Year-End Close Checklist — {tax_year}\n"]
    for c in checks:
        lines.append(c)

    lines.append(f"\n### Recommended Next Steps:")
    lines.append("1. Resolve any 🔴 items immediately")
    lines.append("2. Address 🟡 items before filing taxes")
    lines.append("3. Run `qb_schedule_c` for Schedule C line mapping")
    lines.append("4. Run `qb_deduction_finder` for missed deductions")
    lines.append("5. Send CPA handoff package with all reports")

    return "\n".join(lines)


# ===================================================================
# ATTACHMENT / RECEIPT UPLOAD
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_upload_receipt(entity_type: str, entity_id: str, file_name: str, file_url: str, content_type: str = "image/jpeg") -> str:
    """Attach a receipt or document to a QuickBooks transaction.
    entity_type: Purchase, Bill, Invoice, etc. entity_id: transaction ID.
    file_url: public URL of the receipt image/PDF. content_type: MIME type."""
    if _demo_active():
        # This tool uploads via a raw multipart request, so the qb_request
        # demo fallback never sees it — simulate here instead.
        return (f"🎭 *Demo Mode* — Attachment simulated!\n\n- File: {file_name}\n"
                f"- Attached to: {entity_type} #{entity_id}\n"
                f"- (No real upload was performed.)")
    token = await get_access_token()
    url = f"{BASE_URL}/v3/company/{get_ctx().realm_id}/upload"

    # Download the file first
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_resp = await client.get(file_url)
        if file_resp.status_code != 200:
            return f"Error: Could not download file from {file_url} (status {file_resp.status_code})"
        file_data = file_resp.content

    # Upload as multipart
    import io
    boundary = "----QuickBooksAttachment"
    metadata = json.dumps({
        "AttachableRef": [{"EntityRef": {"type": entity_type, "value": entity_id}}],
        "FileName": file_name,
        "ContentType": content_type,
    })

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file_metadata_0\"\r\n"
        f"Content-Type: application/json\r\n\r\n"
        f"{metadata}\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file_content_0\"; filename=\"{file_name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, content=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        })
        resp.raise_for_status()
        result = resp.json()

    attachable = result.get("AttachableResponse", [{}])[0].get("Attachable", {})
    return (f"✅ Receipt attached to {entity_type} #{entity_id}\n"
            f"  File: {file_name}\n"
            f"  Attachment ID: {attachable.get('Id', '?')}")


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_attachments(entity_type: str = "", entity_id: str = "", max_results: int = 25) -> str:
    """List attachments/receipts. Filter by entity_type and entity_id to see attachments
    for a specific transaction, or leave empty to list all recent attachments."""
    if entity_type and entity_id:
        query = (f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Type = '{entity_type}' "
                 f"AND AttachableRef.EntityRef.Value = '{entity_id}' MAXRESULTS {max_results}")
    else:
        query = f"SELECT * FROM Attachable MAXRESULTS {max_results}"

    result = await qb_query(query)
    attachments = result.get("QueryResponse", {}).get("Attachable", [])

    if not attachments:
        return "No attachments found."

    lines = [f"## Attachments ({len(attachments)} found)\n"]
    for a in attachments:
        refs = a.get("AttachableRef", [])
        ref_str = ", ".join(f"{r.get('EntityRef', {}).get('type', '?')} #{r.get('EntityRef', {}).get('value', '?')}" for r in refs)
        lines.append(f"- **{a.get('FileName', 'Unknown')}** (ID: {a.get('Id')})")
        lines.append(f"  Size: {a.get('Size', '?')} bytes | Type: {a.get('ContentType', '?')}")
        if ref_str:
            lines.append(f"  Linked to: {ref_str}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_missing_receipts(threshold: float = 75.0, start_date: str = "", end_date: str = "") -> str:
    """Find expense transactions at/above a dollar threshold that have NO
    receipt attached in QuickBooks — the IRS substantiation gap (receipts are
    generally required for expenses >= $75; lodging at any amount). threshold:
    default $75. Dates YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    threshold = _validate_amount(threshold, "threshold")

    # Set of (entity, id) that already have an attachment.
    attached = set()
    try:
        att = await qb_query_all("SELECT * FROM Attachable MAXRESULTS 1000")
        for a in att.get("QueryResponse", {}).get("Attachable", []):
            for r in a.get("AttachableRef", []):
                ref = r.get("EntityRef", {})
                if ref.get("value"):
                    attached.add((str(ref.get("type", "")).lower(), str(ref.get("value"))))
    except Exception as e:
        logger.debug(f"Attachable query failed: {e}")

    missing = []
    for entity in ("Purchase", "Bill"):
        r = await qb_query_all(
            f"SELECT * FROM {entity} WHERE TxnDate >= '{start_date}' AND "
            f"TxnDate <= '{end_date}' MAXRESULTS 1000")
        for t in r.get("QueryResponse", {}).get(entity, []):
            amt = float(t.get("TotalAmt", 0) or 0)
            if amt < threshold:
                continue
            if (entity.lower(), str(t.get("Id", ""))) in attached:
                continue
            payee = (t.get("EntityRef") or t.get("VendorRef") or {}).get("name", "(no payee)")
            missing.append({"type": entity, "id": t.get("Id"),
                            "date": t.get("TxnDate", "?"), "payee": payee, "amount": amt})

    missing.sort(key=lambda x: x["amount"], reverse=True)
    lines = [f"## Transactions Missing Receipts — {start_date} to {end_date}",
             f"*Threshold: {fmt(threshold)} (IRS substantiation guideline).*\n"]
    if not missing:
        lines.append(f"✅ Every expense at or above {fmt(threshold)} has a receipt "
                     "attached in QuickBooks.")
        return "\n".join(lines)
    total = sum(m["amount"] for m in missing)
    lines.append(f"**{len(missing)} transactions ({fmt(total)}) are missing a receipt:**\n")
    lines.append("| Date | Payee | Amount | Transaction |")
    lines.append("|---|---|---|---|")
    for m in missing[:100]:
        lines.append(f"| {m['date']} | {m['payee']} | {fmt(m['amount'])} | {m['type']} #{m['id']} |")
    if len(missing) > 100:
        lines.append(f"\n*(showing the 100 largest of {len(missing)})*")
    lines.append("\n*Attach receipts with qb_upload_receipt or in QuickBooks. Lodging "
                 "requires a receipt at any amount; keep documentation for every "
                 "deduction you claim.*")
    return "\n".join(lines)


def _cdc_iter(cdc_response: dict):
    """Yield transaction dicts (with an injected '_entity' key) from a
    QuickBooks CDC response, whatever entity buckets it contains."""
    for block in cdc_response.get("CDCResponse", []) or []:
        for qr in block.get("QueryResponse", []) or []:
            for key, rows in qr.items():
                if isinstance(rows, list):
                    for t in rows:
                        if isinstance(t, dict):
                            t = dict(t)
                            t["_entity"] = key
                            yield t


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_change_audit_trail(since_date: str = "", entities: str = "") -> str:
    """What changed in the books since a date — created, updated, and **deleted**
    transactions, via QuickBooks Change Data Capture. Answers "what changed since
    I last closed this period." since_date: YYYY-MM-DD (default: 7 days ago;
    QuickBooks allows up to ~31 days back). entities: comma-separated (default:
    the common transaction types)."""
    from datetime import date as _d, timedelta as _td
    since = (since_date[:10] if since_date
             else (_d.today() - _td(days=7)).isoformat())
    ent = entities.strip() or ("Purchase,Bill,Invoice,JournalEntry,Payment,"
                               "Deposit,CreditMemo,VendorCredit,BillPayment")
    try:
        r = await qb_request("GET", "cdc",
                             params={"entities": ent, "changedSince": f"{since}T00:00:00"})
    except Exception as e:
        return (f"Change data capture unavailable: {e}. QuickBooks CDC allows a "
                "lookback of up to ~31 days — pick a more recent since_date.")

    created, updated, deleted = [], [], []
    for t in _cdc_iter(r):
        status = str(t.get("status", "")).lower()
        meta = t.get("MetaData", {})
        rec = {
            "entity": t.get("_entity", "?"), "id": t.get("Id", "?"),
            "name": (t.get("EntityRef") or t.get("VendorRef")
                     or t.get("CustomerRef") or {}).get("name", ""),
            "amount": t.get("TotalAmt", ""),
            "created": (meta.get("CreateTime", "") or "")[:10],
            "updated": (meta.get("LastUpdatedTime", "") or "")[:10],
        }
        if status == "deleted":
            deleted.append(rec)
        elif rec["created"] and rec["created"] >= since:
            created.append(rec)
        else:
            updated.append(rec)

    def _amt(a):
        try:
            return fmt(float(a))
        except (ValueError, TypeError):
            return "—"

    lines = [f"## Change Audit Trail — since {since}\n",
             f"*Created {len(created)} · Updated {len(updated)} · "
             f"**Deleted {len(deleted)}** (QuickBooks Change Data Capture).*"]
    if not (created or updated or deleted):
        lines.append("\nNo transaction changes recorded in this window.")
        return "\n".join(lines)
    for title, group in (("🗑️ Deleted", deleted), ("🆕 Created", created),
                         ("✏️ Updated", updated)):
        if not group:
            continue
        lines.append(f"\n### {title} ({len(group)})")
        lines.append("| Entity | # | Party | Amount | Changed |")
        lines.append("|---|---|---|---|---|")
        for c in group[:50]:
            lines.append(f"| {c['entity']} | {c['id']} | {c['name'] or '—'} | "
                         f"{_amt(c['amount'])} | {c['updated'] or c['created']} |")
        if len(group) > 50:
            lines.append(f"\n*(showing 50 of {len(group)})*")
    lines.append("\n*Deleted transactions are the ones to review first when the "
                 "books changed after a close. QuickBooks CDC reflects the last "
                 "~31 days.*")
    return "\n".join(lines)


# ===================================================================
# RECURRING TRANSACTIONS
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_recurring_transactions(max_results: int = 50) -> str:
    """List all recurring transactions (templates) in QuickBooks.
    Shows recurring bills, invoices, and expenses with their schedules."""
    # QB API uses RecurringTransaction endpoint
    try:
        result = await qb_query(f"SELECT * FROM RecurringTransaction MAXRESULTS {max_results}")
        recurrings = result.get("QueryResponse", {}).get("RecurringTransaction", [])
    except Exception:
        # Recurring transactions may not be queryable via SQL in all QBO versions
        return "Recurring transactions query not available in this QuickBooks plan."

    if not recurrings:
        return "No recurring transactions found."

    lines = [f"## Recurring Transactions ({len(recurrings)} found)\n"]
    for r in recurrings:
        rtype = r.get("RecurringInfo", {}).get("RecurType", "?")
        name = r.get("RecurringInfo", {}).get("Name", "?")
        schedule = r.get("RecurringInfo", {}).get("ScheduleInfo", {})
        interval = schedule.get("IntervalType", "?")
        next_date = schedule.get("NextDate", "?")
        lines.append(f"- **{name}** ({rtype})")
        lines.append(f"  Schedule: Every {interval} | Next: {next_date}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# SECURITY & AUDIT LOGGING
# ===================================================================

import logging
import re
from functools import wraps

# Configure audit logger — writes to file for compliance trail
_audit_logger = logging.getLogger("qb_audit")
_audit_logger.setLevel(logging.INFO)
_audit_handler = logging.StreamHandler()
_audit_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_audit_logger.addHandler(_audit_handler)

# Try to add file handler for persistent audit trail
try:
    _file_handler = logging.FileHandler(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.log"),
        encoding="utf-8"
    )
    _file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _audit_logger.addHandler(_file_handler)
except Exception:
    pass  # File logging optional — stderr still captures audit events


def _sanitize_input(value: str, field_name: str = "input") -> str:
    """Sanitize string inputs to prevent SQL injection in QB queries.
    QuickBooks uses its own query language, but we still validate inputs."""
    if not isinstance(value, str):
        return str(value)
    # Block common injection patterns
    dangerous_patterns = [
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|EXEC)",
        r"--\s*$",
        r"/\*.*\*/",
        r"'\s*(OR|AND)\s+'",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError(f"Invalid characters in {field_name}: potential injection detected")
    # Strip control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    return value


def _validate_date(date_str: str, field_name: str = "date") -> str:
    """Validate date format is YYYY-MM-DD."""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError(f"Invalid {field_name} format: '{date_str}'. Use YYYY-MM-DD.")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid {field_name}: '{date_str}' is not a real date.")
    return date_str


def _validate_amount(amount: float, field_name: str = "amount") -> float:
    """Validate monetary amounts are reasonable."""
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative: {amount}")
    if amount > 10_000_000:
        raise ValueError(f"{field_name} exceeds safety limit ($10M): {amount}")
    return round(amount, 2)


def _audit_log(action: str, details: str):
    """Log an auditable action for compliance."""
    _audit_logger.info(f"ACTION={action} | {details}")


# ===================================================================
# NEW TOOL 1: Reclassify Transaction
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_reclassify_transaction(entity_type: str, entity_id: str, new_account_name: str, memo: str = "") -> str:
    """Reclassify a transaction to a different expense/income account. Simpler than manual update.
    entity_type: Purchase, Deposit, Bill, etc. entity_id: the transaction ID.
    new_account_name: name of the account to reclassify to."""
    entity_type = _sanitize_input(entity_type, "entity_type")
    entity_id = _sanitize_input(entity_id, "entity_id")
    new_account_name = _sanitize_input(new_account_name, "new_account_name")

    _audit_log("RECLASSIFY_START", f"type={entity_type} id={entity_id} new_acct={new_account_name}")

    # Find the new account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{new_account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{new_account_name}' not found. Use qb_list_accounts to see available accounts."
    if len(accounts) > 1:
        names = ", ".join(a["Name"] for a in accounts)
        return f"Multiple accounts match '{new_account_name}': {names}. Please be more specific."
    target_acct = accounts[0]

    # Read the existing transaction
    txn = await qb_read(entity_type.lower(), entity_id)
    entity_data = txn.get(entity_type, {})
    if not entity_data:
        return f"{entity_type} #{entity_id} not found."

    old_lines_info = []
    # Update all AccountBasedExpenseLineDetail lines
    for line in entity_data.get("Line", []):
        if line.get("DetailType") == "AccountBasedExpenseLineDetail":
            old_acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "?")
            old_lines_info.append(f"{old_acct}: {fmt(line.get('Amount'))}")
            line["AccountBasedExpenseLineDetail"]["AccountRef"] = {
                "value": target_acct["Id"],
                "name": target_acct["Name"]
            }

    if memo:
        entity_data["PrivateNote"] = memo

    # Sparse update — include SyncToken
    result = await qb_request("POST", entity_type.lower(), json_body=entity_data)
    updated = result.get(entity_type, {})

    _audit_log("RECLASSIFY_DONE", f"type={entity_type} id={entity_id} new_acct={target_acct['Name']} (ID:{target_acct['Id']})")

    return (
        f"✅ Reclassified {entity_type} #{entity_id}\n"
        f"  From: {'; '.join(old_lines_info)}\n"
        f"  To: {target_acct['Name']}\n"
        f"  SyncToken: {updated.get('SyncToken', '?')}"
    )


# ===================================================================
# NEW TOOL 2: Batch Create Journal Entries
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_batch_create_journal_entries(entries_json: str) -> str:
    """Create multiple journal entries in one call. entries_json is a JSON array:
    [{"date": "YYYY-MM-DD", "memo": "...", "lines": [{"account_name": "...", "amount": 100.00, "type": "Debit"}, ...]}].
    Each entry must have balanced debits and credits. Returns summary of created JEs."""
    entries = json.loads(entries_json) if isinstance(entries_json, str) else entries_json

    if not isinstance(entries, list) or len(entries) == 0:
        return "Error: entries_json must be a non-empty JSON array of journal entries."
    if len(entries) > 25:
        return "Error: Maximum 25 journal entries per batch. Split into multiple calls."

    _audit_log("BATCH_JE_START", f"count={len(entries)}")

    results = []
    errors = []

    for i, entry in enumerate(entries):
        try:
            date = _validate_date(entry.get("date", ""), f"entry[{i}].date")
            memo = entry.get("memo", "")
            lines = entry.get("lines", [])

            if not lines or len(lines) < 2:
                errors.append(f"Entry {i+1}: Must have at least 2 lines (debit + credit)")
                continue

            je_lines = []
            total_debit = 0.0
            total_credit = 0.0

            for line in lines:
                acct_name = _sanitize_input(line.get("account_name", ""), "account_name")
                amount = _validate_amount(float(line.get("amount", 0)), "amount")
                posting_type = line.get("type", "Debit")

                if posting_type not in ("Debit", "Credit"):
                    errors.append(f"Entry {i+1}: Invalid posting type '{posting_type}'. Use 'Debit' or 'Credit'.")
                    break

                acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{acct_name}%' MAXRESULTS 1")
                acct_list = acct_result.get("QueryResponse", {}).get("Account", [])
                if not acct_list:
                    errors.append(f"Entry {i+1}: Account '{acct_name}' not found.")
                    break
                acct = acct_list[0]

                if posting_type == "Debit":
                    total_debit += amount
                else:
                    total_credit += amount

                je_lines.append({
                    "DetailType": "JournalEntryLineDetail",
                    "Amount": amount,
                    "Description": line.get("description", ""),
                    "JournalEntryLineDetail": {
                        "PostingType": posting_type,
                        "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
                    }
                })

            if len(je_lines) != len(lines):
                continue  # An error was recorded above

            if abs(total_debit - total_credit) > 0.01:
                errors.append(f"Entry {i+1}: Does not balance. Debits={fmt(total_debit)}, Credits={fmt(total_credit)}")
                continue

            je_body = {"TxnDate": date, "Line": je_lines}
            if memo:
                je_body["PrivateNote"] = memo

            result = await qb_request("POST", "journalentry", json_body=je_body)
            je = result.get("JournalEntry", {})
            results.append(f"  ✅ JE #{je.get('Id')} | {date} | {fmt(je.get('TotalAmt'))} | {memo[:50]}")

            _audit_log("BATCH_JE_CREATED", f"id={je.get('Id')} date={date} amount={fmt(je.get('TotalAmt'))}")

        except Exception as e:
            errors.append(f"Entry {i+1}: {str(e)}")

    output = [f"## Batch Journal Entry Results\n"]
    if results:
        output.append(f"**Created: {len(results)} journal entries**")
        output.extend(results)
    if errors:
        output.append(f"\n**Errors: {len(errors)}**")
        output.extend(f"  ❌ {e}" for e in errors)

    _audit_log("BATCH_JE_DONE", f"created={len(results)} errors={len(errors)}")
    return "\n".join(output)


# ===================================================================
# NEW TOOL 3: Home Office Calculator (Form 8829)
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "CRA business-use-of-home rules differ; see qb_t2125_summary.")
async def qb_home_office_calculator(
    home_sqft: float,
    office_sqft: float,
    home_value: float,
    land_value: float = 0,
    annual_mortgage_interest: float = 0,
    annual_property_tax: float = 0,
    annual_insurance: float = 0,
    annual_utilities: float = 0,
    annual_repairs: float = 0,
    depreciation_years: float = 39,
    tax_year: str = "2025"
) -> str:
    """Calculate home office deduction using the regular method (Form 8829).
    Returns deduction breakdown by category with IRS line mappings.
    home_sqft: total home square footage. office_sqft: dedicated office square footage.
    home_value: fair market value or purchase price. land_value: land portion (not depreciable).
    All annual amounts are the full household totals — business % is calculated automatically."""
    home_sqft = _validate_amount(home_sqft, "home_sqft")
    office_sqft = _validate_amount(office_sqft, "office_sqft")
    if office_sqft > home_sqft:
        return "Error: Office square footage cannot exceed home square footage."

    biz_pct = round(office_sqft / home_sqft, 4)
    biz_pct_display = f"{biz_pct * 100:.2f}%"

    building_value = home_value - land_value
    annual_depreciation = building_value / depreciation_years

    deductions = {
        "Mortgage interest": annual_mortgage_interest * biz_pct,
        "Property taxes": annual_property_tax * biz_pct,
        "Homeowner insurance": annual_insurance * biz_pct,
        "Utilities": annual_utilities * biz_pct,
        "Repairs & maintenance": annual_repairs * biz_pct,
        "Depreciation": annual_depreciation * biz_pct,
    }

    total = sum(deductions.values())

    lines = [
        f"## Home Office Deduction — {tax_year} (Form 8829)\n",
        f"**Business Use Percentage:** {office_sqft:.0f} sq ft / {home_sqft:.0f} sq ft = **{biz_pct_display}**\n",
        f"### Deduction Breakdown",
    ]
    for category, amount in deductions.items():
        if amount > 0:
            lines.append(f"  {category}: **{fmt(amount)}**")

    lines.extend([
        f"\n### **TOTAL HOME OFFICE DEDUCTION: {fmt(total)}**",
        f"\n### Calculation Details",
        f"  Building value: {fmt(building_value)} (home {fmt(home_value)} - land {fmt(land_value)})",
        f"  Annual depreciation: {fmt(annual_depreciation)} ({fmt(building_value)} / {depreciation_years:.0f} years)",
        f"  Business %: {biz_pct_display}",
        f"\n### Schedule C Mapping",
        f"  Line 18 (Office expense): $0 — using Form 8829 instead",
        f"  Line 30 (Business use of home): **{fmt(total)}** — attach Form 8829",
        f"\n*Note: Regular method used. Simplified method ($5/sqft, max 300 sqft = $1,500) available as alternative.*",
    ])

    _audit_log("HOME_OFFICE_CALC", f"year={tax_year} biz_pct={biz_pct_display} total={fmt(total)}")
    return "\n".join(lines) + tax_data_footer()


# ===================================================================
# NEW TOOL 4: Vehicle Depreciation Calculator
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Use qb_cca_schedule (Class 10/10.1).")
async def qb_vehicle_depreciation_calculator(
    purchase_price: float,
    purchase_date: str,
    business_use_pct: float,
    vehicle_weight_lbs: float = 6001,
    is_new: bool = True,
    tax_year: str = "2025"
) -> str:
    """Calculate vehicle depreciation deduction using Section 179, bonus depreciation, and MACRS.
    purchase_price: total vehicle cost. purchase_date: YYYY-MM-DD.
    business_use_pct: decimal (0.50 = 50%). vehicle_weight_lbs: GVWR for SUV classification.
    is_new: whether vehicle is new (affects bonus depreciation eligibility).
    Returns first-year and multi-year depreciation schedule."""
    purchase_price = _validate_amount(purchase_price, "purchase_price")
    _validate_date(purchase_date, "purchase_date")

    if business_use_pct <= 0 or business_use_pct > 1:
        return "Error: business_use_pct must be between 0.01 and 1.00 (e.g., 0.50 for 50%)."

    biz_basis = purchase_price * business_use_pct
    is_heavy_suv = vehicle_weight_lbs > 6000
    year = int(tax_year)

    lines = [
        f"## Vehicle Depreciation — {tax_year}\n",
        f"**Purchase Price:** {fmt(purchase_price)}",
        f"**Purchase Date:** {purchase_date}",
        f"**Business Use:** {business_use_pct*100:.0f}%",
        f"**Business Basis:** {fmt(biz_basis)}",
        f"**GVWR:** {vehicle_weight_lbs:,.0f} lbs ({'Heavy SUV > 6,000 lbs' if is_heavy_suv else 'Standard vehicle'})",
        f"**New/Used:** {'New' if is_new else 'Used'}",
    ]

    # §280F listed-property gate: vehicles used <= 50% for business get no
    # §179 and no bonus — straight-line ADS only.
    if business_use_pct <= 0.5:
        sl_yr1 = biz_basis / 5 / 2  # ADS 5-yr straight line, half-year convention
        lines.extend([
            f"\n### ⚠️ Business use is not more than 50%",
            f"  Listed-property rules (§280F(b)) disallow Section 179 AND bonus",
            f"  depreciation at ≤50% business use. Straight-line (ADS, 5-year,",
            f"  half-year convention) applies:",
            f"  Year 1: **{fmt(sl_yr1)}**  |  Years 2–5: {fmt(biz_basis / 5)}/yr  |  Year 6: {fmt(sl_yr1)}",
            f"\n*If business use later exceeds 50%, regular MACRS becomes available "
            f"prospectively; if it drops to ≤50% after claiming §179/bonus, recapture applies.*",
            f"\n*⚠️ CPA should verify. Mileage log required to support business use percentage.*",
        ])
        _audit_log("VEHICLE_DEPR_CALC", f"year={tax_year} price={fmt(purchase_price)} biz_pct={business_use_pct} sl_only")
        return "\n".join(lines)

    # OBBBA (2025): 100% bonus is PERMANENT for property acquired AND placed
    # in service after Jan 19, 2025 (new or used, so long as new-to-you).
    # Property acquired on/before 1/19/2025 keeps the TCJA phase-down by
    # placed-in-service year (terminal 0% for 2027+ is statute, not fallback).
    vintage_notes = []
    if purchase_date > "2025-01-19":
        bonus_rate = 1.00
        bonus_note = "100% — permanent under OBBBA (acquired after Jan 19, 2025)"
    else:
        bonus_rate = tax_value("TCJA_PHASE_DOWN", year)
        bonus_note = (f"{bonus_rate*100:.0f}% — TCJA phase-down (acquired on/before "
                      f"Jan 19, 2025; rate set by placed-in-service year)")

    if is_heavy_suv:
        # Heavy SUV (GVWR 6,001–14,000 lbs): §179 up to the SUV cap, then
        # bonus, then MACRS.
        try:
            sec179_limit, _note = tax_value_or_latest("SUV_179_CAP", year)
        except TaxDataError as e:
            return str(e)
        if _note:
            vintage_notes.append(_note)
        sec179 = min(biz_basis, sec179_limit)
        remaining_after_179 = biz_basis - sec179

        bonus = remaining_after_179 * bonus_rate
        remaining_after_bonus = remaining_after_179 - bonus

        # MACRS 5-year, first year rate = 20%
        macrs_yr1 = remaining_after_bonus * 0.20
        total_yr1 = sec179 + bonus + macrs_yr1

        lines.extend([
            f"\n### First-Year Deduction Breakdown",
            f"  Section 179: **{fmt(sec179)}** (heavy SUV cap: {fmt(sec179_limit)})",
            f"  Bonus depreciation: **{fmt(bonus)}** ({bonus_note})",
            f"  MACRS Year 1 (20%): **{fmt(macrs_yr1)}**",
            f"  **TOTAL FIRST-YEAR DEDUCTION: {fmt(total_yr1)}**",
            f"\n  §179 also requires an active trade or business with sufficient",
            f"  taxable income (the deduction can't create a business loss;",
            f"  bonus depreciation can).",
            f"\n### Remaining MACRS Schedule (5-year property)",
        ])

        macrs_rates = _MACRS_5YR
        remaining_macrs = remaining_after_bonus
        for yr, rate in enumerate(macrs_rates):
            yr_deduction = remaining_macrs * rate
            year_num = year + yr
            marker = " ← (included above)" if yr == 0 else ""
            lines.append(f"  Year {yr+1} ({year_num}): {fmt(yr_deduction)} ({rate*100:.1f}%){marker}")

    else:
        # Standard vehicle: §280F luxury-auto caps apply (Rev. Proc. values;
        # first-year cap shown is the with-bonus number).
        try:
            limits, _note = tax_value_or_latest("280F_LIMITS", year)
        except TaxDataError as e:
            return str(e)
        if _note:
            vintage_notes.append(_note)
        yr1_cap = limits[1] if bonus_rate > 0 else limits["no_bonus_1"]
        yr1_deduction = min(biz_basis, yr1_cap)

        lines.extend([
            f"\n### Standard Vehicle (≤ 6,000 lbs GVWR) — §280F caps",
            f"  Bonus depreciation: {bonus_note}",
            f"  Year 1: **{fmt(yr1_deduction)}** (cap: {fmt(yr1_cap)}"
            f"{' with bonus' if bonus_rate > 0 else ' without bonus'})",
            f"  Year 2 cap: {fmt(limits[2])}",
            f"  Year 3 cap: {fmt(limits[3])}",
            f"  Year 4+: {fmt(limits[4])}/year until fully depreciated",
        ])

    for note in vintage_notes:
        lines.append(f"\n⚠️ {note}")

    lines.extend([
        f"\n### Schedule C Mapping",
        f"  Line 13 (Depreciation / Form 4562): report vehicle depreciation",
        f"\n*To put this on the books, use qb_record_depreciation — it credits an "
        f"Accumulated Depreciation contra account, never the asset itself.*",
        f"\n*⚠️ CPA should verify: bonus eligibility (acquisition vs. placed-in-service "
        f"dates), Section 179 limits, and business use substantiation.*",
        f"*Mileage log required to support business use percentage.*",
    ])

    _audit_log("VEHICLE_DEPR_CALC", f"year={tax_year} price={fmt(purchase_price)} biz_pct={business_use_pct}")
    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "CRA treats most startup costs as ordinary expenses once the business has commenced; see qb_t2125_summary.")
async def qb_startup_cost_analysis(total_startup_costs: float, commencement_date: str, tax_year: str = "") -> str:
    """Compute the §195 startup-cost deduction and amortization schedule.
    Up to $5,000 is deductible in the year the business commences, phased
    out dollar-for-dollar once total startup costs exceed $50,000; the
    remainder amortizes straight-line over 180 months starting the month
    the active trade or business begins. commencement_date: YYYY-MM-DD the
    business actually commenced (not when costs were paid)."""
    total_startup_costs = _validate_amount(total_startup_costs, "total_startup_costs")
    commencement_date = _validate_date(commencement_date, "commencement_date")

    c_year = int(commencement_date[:4])
    c_month = int(commencement_date[5:7])
    year = int(tax_year) if tax_year else c_year
    if year < c_year:
        return (f"tax_year {year} is before the commencement date "
                f"{commencement_date} — no §195 deduction until the business "
                f"actually commences.")

    immediate = max(0.0, min(5_000.0, 5_000.0 - max(0.0, total_startup_costs - 50_000.0)))
    immediate = min(immediate, total_startup_costs)
    amortizable = total_startup_costs - immediate
    monthly = amortizable / 180 if amortizable > 0 else 0.0

    # Months of amortization falling in the requested tax year
    if year == c_year:
        months_this_year = 13 - c_month
    else:
        months_used_before = (13 - c_month) + (year - c_year - 1) * 12
        months_this_year = max(0, min(12, 180 - months_used_before))
    amort_this_year = monthly * months_this_year

    lines = [
        f"## §195 Startup Cost Analysis — {year}\n",
        f"**Total startup costs:** {fmt(total_startup_costs)}",
        f"**Business commenced:** {commencement_date}",
        f"\n### Year-{1 + (year - c_year)} treatment",
    ]
    if year == c_year:
        lines.append(f"  Immediate deduction: **{fmt(immediate)}**"
                     + (f" (reduced — costs exceed $50,000)" if total_startup_costs > 50_000 else ""))
        if total_startup_costs >= 55_000:
            lines.append("  ⚠️ Costs ≥ $55,000: the immediate deduction is fully "
                         "phased out; everything amortizes over 180 months.")
    lines.append(f"  Amortization ({months_this_year} month(s) × {fmt(monthly)}): "
                 f"**{fmt(amort_this_year)}**")
    total_ded = amort_this_year + (immediate if year == c_year else 0)
    lines.append(f"  **Total {year} deduction: {fmt(total_ded)}**")
    lines.extend([
        f"\n### Ongoing",
        f"  Amortizable balance: {fmt(amortizable)} over 180 months "
        f"({fmt(monthly * 12)}/full year) beginning {c_year}-{c_month:02d}.",
        f"\n*Schedule C: immediate portion on line 27a (other expenses); "
        f"amortization via Form 4562 Part VI. Costs paid before commencement "
        f"are capitalized until the business starts — the commencement date, "
        f"not the payment date, starts the clock.*",
        f"\n*⚠️ Organizational costs (entity formation) have a separate, "
        f"parallel $5,000/§248 allowance. CPA should verify.*",
    ])
    _audit_log("STARTUP_COST_ANALYSIS", f"total={fmt(total_startup_costs)} year={year}")
    return "\n".join(lines) + tax_data_footer(year)


# ===================================================================
# NEW TOOL 5: List Journal Entries by Memo
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_journal_entries_by_memo(search_text: str, max_results: int = 50) -> str:
    """Search journal entries by memo/private note text. Useful for finding specific
    JEs by description (e.g., 'home office', 'depreciation', 'reclassify').
    search_text: text to search for in memo field (case-insensitive partial match)."""
    search_text = _sanitize_input(search_text, "search_text")

    # QB query doesn't support LIKE on PrivateNote, so we fetch all and filter
    result = await qb_query_all(f"SELECT * FROM JournalEntry MAXRESULTS 500")
    all_jes = result.get("QueryResponse", {}).get("JournalEntry", [])

    if not all_jes:
        return "No journal entries found."

    matches = []
    for je in all_jes:
        memo = je.get("PrivateNote", "")
        if search_text.lower() in memo.lower():
            matches.append(je)

    if not matches:
        return f"No journal entries found matching '{search_text}'."

    matches = matches[:max_results]

    lines = [f"## Journal Entries matching '{search_text}' ({len(matches)} found)\n"]
    for je in matches:
        je_id = je.get("Id", "?")
        date = je.get("TxnDate", "?")
        memo = je.get("PrivateNote", "")
        total = je.get("TotalAmt", 0)

        lines.append(f"**{date}** | ID: {je_id} | {fmt(float(total))}")
        if memo:
            lines.append(f"  Memo: {memo[:100]}{'...' if len(memo) > 100 else ''}")

        for line in je.get("Line", []):
            detail = line.get("JournalEntryLineDetail", {})
            acct = detail.get("AccountRef", {}).get("name", "?")
            posting = detail.get("PostingType", "?")
            amt = line.get("Amount", 0)
            lines.append(f"  - {posting} {acct}: {fmt(float(amt))}")
        lines.append("")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 6: Account Transactions
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_account_transactions(account_name: str, start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """Get all transactions for a specific account within a date range.
    Shows every debit and credit hitting the account with vendor names, memos,
    transaction types, and IDs. Useful for account reconciliation and verifying balances.
    account_name: exact or partial account name. Dates YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    account_name = _sanitize_input(account_name, "account_name")
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    # Find the account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{account_name}' not found."
    if len(accounts) > 1:
        names = ", ".join(f"{a['Name']} (ID:{a['Id']})" for a in accounts)
        return f"Multiple accounts match: {names}. Please be more specific."
    acct = accounts[0]
    acct_id = acct["Id"]
    acct_type = acct.get("AccountType", "")
    is_active = acct.get("Active", True)

    lines = [
        f"## Account Transactions: {acct['Name']} (ID: {acct_id})",
        f"**Period:** {start_date} to {end_date}",
        f"**Type:** {acct_type} / {acct.get('AccountSubType', '')}",
        f"**Active:** {'Yes' if is_active else '⚠️ DELETED/INACTIVE'}",
        f"**Current Balance:** {fmt(float(acct.get('CurrentBalance', 0)))}",
        "",
    ]

    # Query multiple transaction types that could hit this account
    txn_types = {
        "Purchase": f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
        "Deposit": f"SELECT * FROM Deposit WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
        "JournalEntry": f"SELECT * FROM JournalEntry WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
        "Transfer": f"SELECT * FROM Transfer WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
        "Bill": f"SELECT * FROM Bill WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
        "BillPayment": f"SELECT * FROM BillPayment WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}",
    }

    all_txns = []

    for txn_type, query in txn_types.items():
        try:
            result = (await qb_query(query)).get("QueryResponse", {}).get(txn_type, [])
        except Exception:
            continue

        for txn in result:
            # Check if this transaction touches our account
            touches_account = False
            amount = float(txn.get("TotalAmt", 0))

            if txn_type == "Purchase":
                if txn.get("AccountRef", {}).get("value") == acct_id:
                    touches_account = True
                for line in txn.get("Line", []):
                    detail = line.get("AccountBasedExpenseLineDetail", {})
                    if detail.get("AccountRef", {}).get("value") == acct_id:
                        touches_account = True
                        amount = float(line.get("Amount", amount))

            elif txn_type == "Deposit":
                if txn.get("DepositToAccountRef", {}).get("value") == acct_id:
                    touches_account = True
                for line in txn.get("Line", []):
                    detail = line.get("DepositLineDetail", {})
                    if detail.get("AccountRef", {}).get("value") == acct_id:
                        touches_account = True
                        amount = float(line.get("Amount", amount))

            elif txn_type == "JournalEntry":
                for line in txn.get("Line", []):
                    detail = line.get("JournalEntryLineDetail", {})
                    if detail.get("AccountRef", {}).get("value") == acct_id:
                        touches_account = True
                        amount = float(line.get("Amount", amount))

            elif txn_type == "Transfer":
                if (txn.get("FromAccountRef", {}).get("value") == acct_id or
                        txn.get("ToAccountRef", {}).get("value") == acct_id):
                    touches_account = True

            elif txn_type in ("Bill", "BillPayment"):
                for line in txn.get("Line", []):
                    detail = line.get("AccountBasedExpenseLineDetail", {})
                    if detail.get("AccountRef", {}).get("value") == acct_id:
                        touches_account = True
                        amount = float(line.get("Amount", amount))
                if txn.get("APAccountRef", {}).get("value") == acct_id:
                    touches_account = True

            if touches_account:
                vendor = txn.get("EntityRef", {}).get("name", "")
                if not vendor and txn_type == "Transfer":
                    from_name = txn.get("FromAccountRef", {}).get("name", "?")
                    to_name = txn.get("ToAccountRef", {}).get("name", "?")
                    vendor = f"{from_name} → {to_name}"

                all_txns.append({
                    "type": txn_type,
                    "id": txn.get("Id", "?"),
                    "date": txn.get("TxnDate", "?"),
                    "amount": amount,
                    "vendor": vendor or "(no vendor)",
                    "memo": (txn.get("PrivateNote", "") or txn.get("Memo", "") or "")[:80],
                    "payment_acct": txn.get("AccountRef", {}).get("name", ""),
                })

    # Sort by date
    all_txns.sort(key=lambda t: t["date"])

    if not all_txns:
        # Fallback to General Ledger report for accounts that don't match direct queries
        params = {"start_date": start_date, "end_date": end_date, "account": acct_id}
        result = await qb_request("GET", "reports/GeneralLedger", params=params)
        rows = result.get("Rows", {}).get("Row", [])
        _parse_report_rows(rows, lines)
        if len(lines) <= 6:
            lines.append("No transactions found for this account in the date range.")
        return "\n".join(lines)

    # Build detailed output
    total_amount = sum(t["amount"] for t in all_txns)
    lines.append(f"**Transactions Found:** {len(all_txns)} | **Total:** {fmt(total_amount)}\n")
    lines.append("| Date | Type | ID | Vendor | Amount | Memo |")
    lines.append("|------|------|----|--------|--------|------|")

    for t in all_txns:
        memo_short = t["memo"][:40] + "..." if len(t["memo"]) > 40 else t["memo"]
        lines.append(
            f"| {t['date']} | {t['type']} | {t['id']} | {t['vendor']} | {fmt(t['amount'])} | {memo_short} |"
        )

    # Summary by vendor
    from collections import Counter
    vendor_totals = Counter()
    vendor_counts = Counter()
    for t in all_txns:
        vendor_totals[t["vendor"]] += t["amount"]
        vendor_counts[t["vendor"]] += 1

    if len(vendor_totals) > 1:
        lines.append(f"\n### By Vendor")
        for vendor, total in vendor_totals.most_common(15):
            lines.append(f"  {vendor}: {fmt(total)} ({vendor_counts[vendor]} txns)")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 7: Schedule C Detailed
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "For Canadian books use qb_t2125_summary.")
async def qb_schedule_c_detailed(tax_year: str = "2025") -> str:
    """Generate a detailed Schedule C (Profit or Loss from Business) mapping with
    QuickBooks account-level detail for each line. More granular than qb_schedule_c —
    shows which QB accounts feed each Schedule C line. tax_year in YYYY format."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    # P&L period activity (NOT balance-sheet CurrentBalances). The previous
    # version summed every account's CurrentBalance — including credit-card
    # LIABILITIES ("Delta Platinum Business Card" -> Line 9 via 'car' in 'Card')
    # — which was both the wrong number and the wrong accounts. Now identical
    # to qb_schedule_c so the two tools always agree and reconcile to the P&L.
    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end, "summarize_column_by": "Total"})

    expense_dict = _extract_pl_expense_accounts(result)
    sc_lines = _map_expenses_to_schedule_c(expense_dict)
    pl_total = _pl_expense_total(result)

    total_income = 0.0
    for section in result.get("Rows", {}).get("Row", []):
        cols = section.get("Summary", {}).get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0") or 0)
            except (ValueError, TypeError):
                val = 0.0
            if "income" in label and "net" not in label:
                total_income = val

    # Company name from the connected QuickBooks company (never hardcoded)
    company_name = ""
    try:
        _ci = await qb_query("SELECT * FROM CompanyInfo")
        company_name = (_ci.get("QueryResponse", {})
                        .get("CompanyInfo", [{}])[0].get("CompanyName", ""))
    except Exception:
        pass

    def _sc_line_sort(item):
        m = _re.search(r"Line (\d+)([a-z]?)", item[0])
        return (int(m.group(1)) if m else 999, m.group(2) if m else "")

    lines = [
        f"## Schedule C Detail — {tax_year}\n",
        *( [f"**{company_name}**"] if company_name else [] ),
        f"**EIN:** Check QB Company Info",
        f"**Period:** {start} to {end}\n",
        f"**Line 1 — Gross receipts: {fmt(total_income)}**\n",
        "### Expenses (by Schedule C line, from P&L):",
    ]

    total_expenses = 0.0
    home_flagged = False
    for line_name, data in sorted(sc_lines.items(), key=_sc_line_sort):
        flag = " ⚠️ (may belong on Form 8829)" if data["home"] else ""
        lines.append(f"\n**{line_name}: {fmt(data['amount'])}**{flag}")
        for acct, amt in data["accounts"]:
            lines.append(f"  - {acct}: {fmt(amt)}")
        total_expenses += data["amount"]
        home_flagged = home_flagged or data["home"]

    net = total_income - total_expenses
    recon = ("" if not pl_total or abs(total_expenses - pl_total) <= 0.01 else
             f"\n  ⚠️ Line 28 does not reconcile to P&L expenses ({fmt(pl_total)}) — review.")
    lines.extend([
        f"\n---",
        f"### **Summary**",
        f"  Total Income (Line 1): {fmt(total_income)}",
        f"  Total Expenses (Line 28): {fmt(total_expenses)}",
        f"  **Net Profit/Loss (Line 31): {fmt(net)}**{recon}",
        ("\n*Items flagged ⚠️ (home office, homeowner insurance, home utilities) "
         "generally belong on Form 8829, not directly on Schedule C.*"
         if home_flagged else ""),
        f"*Line 30 (business use of home) is computed separately via Form 8829. "
        f"CPA should verify account-to-line mappings before filing.*",
    ])

    _audit_log("SCHEDULE_C_DETAIL", f"year={tax_year} income={fmt(total_income)} expenses={fmt(total_expenses)}")
    return "\n".join(lines) + tax_data_footer(int(tax_year))


# ===================================================================
# NEW TOOL 8: Create Sub-Account
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_sub_account(name: str, parent_account_name: str, account_type: str = "", account_sub_type: str = "", description: str = "") -> str:
    """Create a sub-account under an existing parent account. Simpler than qb_create_account
    for building account hierarchies. name: new sub-account name.
    parent_account_name: name of existing parent account.
    account_type/account_sub_type: inherited from parent if not specified."""
    name = _sanitize_input(name, "name")
    parent_account_name = _sanitize_input(parent_account_name, "parent_account_name")

    # Find parent account
    parent_result = await qb_query(f"SELECT * FROM Account WHERE Name = '{parent_account_name}' MAXRESULTS 5")
    parents = parent_result.get("QueryResponse", {}).get("Account", [])
    if not parents:
        # Try partial match
        parent_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{parent_account_name}%' MAXRESULTS 5")
        parents = parent_result.get("QueryResponse", {}).get("Account", [])
    if not parents:
        return f"Parent account '{parent_account_name}' not found."
    if len(parents) > 1:
        names = ", ".join(f"{a['Name']} (ID:{a['Id']})" for a in parents)
        return f"Multiple accounts match: {names}. Please be more specific."
    parent = parents[0]

    body = {
        "Name": name,
        "SubAccount": True,
        "ParentRef": {"value": parent["Id"], "name": parent["Name"]},
        "AccountType": account_type or parent.get("AccountType", "Expense"),
        "AccountSubType": account_sub_type or parent.get("AccountSubType", ""),
    }
    if description:
        body["Description"] = description

    result = await qb_request("POST", "account", json_body=body)
    new_acct = result.get("Account", {})

    _audit_log("CREATE_SUB_ACCOUNT", f"name={name} parent={parent['Name']} id={new_acct.get('Id')}")

    return (
        f"✅ Created sub-account '{new_acct.get('FullyQualifiedName', name)}' (ID: {new_acct.get('Id')})\n"
        f"  Parent: {parent['Name']} (ID: {parent['Id']})\n"
        f"  Type: {new_acct.get('AccountType', '?')} / {new_acct.get('AccountSubType', '')}"
    )


# ===================================================================
# NEW TOOL 9: Transaction Detail
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_transaction_detail(entity_type: str, entity_id: str) -> str:
    """Get complete details for a single transaction. entity_type: Purchase, Deposit,
    Transfer, JournalEntry, Bill, Invoice, Payment, SalesReceipt, BillPayment, etc.
    entity_id: the transaction ID. Returns all fields including line items, memo, metadata."""
    entity_type = _sanitize_input(entity_type, "entity_type")
    entity_id = _sanitize_input(entity_id, "entity_id")

    valid_types = [
        "Purchase", "Deposit", "Transfer", "JournalEntry", "Bill",
        "Invoice", "Payment", "SalesReceipt", "BillPayment", "Estimate",
        "CreditMemo", "RefundReceipt", "VendorCredit"
    ]
    if entity_type not in valid_types:
        return f"Invalid entity_type '{entity_type}'. Valid types: {', '.join(valid_types)}"

    txn = await qb_read(entity_type.lower(), entity_id)
    entity_data = txn.get(entity_type, {})
    if not entity_data:
        return f"{entity_type} #{entity_id} not found."

    lines = [f"## {entity_type} #{entity_id} — Full Detail\n"]

    # Multicurrency books: show the transaction currency + exchange rate
    cur_tag = _txn_currency_tag(entity_data) if await _multicurrency_enabled() else ""

    # Common fields
    for field, label in [
        ("TxnDate", "Date"), ("TotalAmt", "Total"), ("PrivateNote", "Memo"),
        ("DocNumber", "Doc Number"), ("TxnStatus", "Status"),
    ]:
        val = entity_data.get(field)
        if val is not None:
            if field == "TotalAmt":
                lines.append(f"**{label}:** {fmt(float(val))}{cur_tag}")
            else:
                lines.append(f"**{label}:** {val}")

    # Entity references
    for ref_field, label in [
        ("EntityRef", "Vendor/Customer"), ("AccountRef", "Account"),
        ("DepositToAccountRef", "Deposit To"), ("FromAccountRef", "From Account"),
        ("ToAccountRef", "To Account"),
    ]:
        ref = entity_data.get(ref_field, {})
        if ref:
            lines.append(f"**{label}:** {ref.get('name', '?')} (ID: {ref.get('value', '?')})")

    # Line items
    txn_lines = entity_data.get("Line", [])
    if txn_lines:
        lines.append(f"\n### Line Items ({len(txn_lines)})")
        for i, line in enumerate(txn_lines, 1):
            detail_type = line.get("DetailType", "?")
            amount = line.get("Amount", 0)
            desc = line.get("Description", "")

            lines.append(f"\n**Line {i}:** {fmt(float(amount))} ({detail_type})")
            if desc:
                lines.append(f"  Description: {desc}")

            # Parse detail based on type
            if detail_type == "AccountBasedExpenseLineDetail":
                detail = line.get("AccountBasedExpenseLineDetail", {})
                lines.append(f"  Account: {detail.get('AccountRef', {}).get('name', '?')}")
            elif detail_type == "JournalEntryLineDetail":
                detail = line.get("JournalEntryLineDetail", {})
                lines.append(f"  Account: {detail.get('AccountRef', {}).get('name', '?')}")
                lines.append(f"  Posting: {detail.get('PostingType', '?')}")
            elif detail_type == "ItemBasedExpenseLineDetail":
                detail = line.get("ItemBasedExpenseLineDetail", {})
                lines.append(f"  Item: {detail.get('ItemRef', {}).get('name', '?')}")

    # Metadata
    meta = entity_data.get("MetaData", {})
    if meta:
        lines.append(f"\n### Metadata")
        lines.append(f"  Created: {meta.get('CreateTime', '?')}")
        lines.append(f"  Updated: {meta.get('LastUpdatedTime', '?')}")
    lines.append(f"  SyncToken: {entity_data.get('SyncToken', '?')}")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 10: Delete Journal Entry
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_delete_journal_entry(journal_entry_id: str, confirm: bool = False) -> str:
    """Delete a journal entry. Use for removing draft, duplicate, or test JEs.
    journal_entry_id: the JE ID to delete. confirm: must be True to execute deletion.
    ⚠️ This is PERMANENT. Use qb_void_transaction to void instead of delete when possible."""
    journal_entry_id = _sanitize_input(journal_entry_id, "journal_entry_id")

    if not confirm:
        # Read the JE first to show what would be deleted
        txn = await qb_read("JournalEntry", journal_entry_id)
        je = txn.get("JournalEntry", {})
        if not je:
            return f"Journal entry #{journal_entry_id} not found."

        memo = je.get("PrivateNote", "(no memo)")
        date = je.get("TxnDate", "?")
        total = je.get("TotalAmt", 0)

        return (
            f"⚠️ **Confirm Deletion**\n"
            f"  JE #{journal_entry_id} | {date} | {fmt(float(total))}\n"
            f"  Memo: {memo[:100]}\n\n"
            f"To delete, call again with confirm=True.\n"
            f"Consider using qb_void_transaction instead (keeps audit trail)."
        )

    _audit_log("DELETE_JE_START", f"id={journal_entry_id}")

    # Read to get SyncToken
    txn = await qb_read("JournalEntry", journal_entry_id)
    je = txn.get("JournalEntry", {})
    if not je:
        return f"Journal entry #{journal_entry_id} not found."

    # QB delete: POST with ?operation=delete
    delete_body = {"Id": journal_entry_id, "SyncToken": je["SyncToken"]}
    result = await qb_request("POST", "journalentry?operation=delete", json_body=delete_body)

    _audit_log("DELETE_JE_DONE", f"id={journal_entry_id} memo={je.get('PrivateNote', '')[:50]}")

    return f"✅ Journal entry #{journal_entry_id} permanently deleted."


# ===================================================================
# NEW: 1099 Contractor Reporting
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Use qb_t4a_contractor_report.")
async def qb_1099_contractor_report(tax_year: str = "2025", threshold: float = 0.0) -> str:
    """Generate 1099-NEC contractor reporting data for a tax year.
    Lists all vendors paid at or above the IRS reporting threshold via
    non-employee compensation ($600 through 2025; $2,000 from 2026 under
    OBBBA, auto-selected by tax_year). Shows vendor name, total paid, TIN
    status, and address. tax_year: YYYY. threshold: optional override."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"
    if not threshold:
        try:
            threshold, _t_note = tax_value_or_latest("NEC_1099_THRESHOLD", int(tax_year))
        except TaxDataError as e:
            return str(e)
    threshold = _validate_amount(threshold, "threshold")

    # Get all vendors
    vendor_result = await qb_query_all("SELECT * FROM Vendor MAXRESULTS 500")
    vendors = vendor_result.get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return "No vendors found."

    # Get all purchases for the year
    purchase_result = await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    purchases = purchase_result.get("QueryResponse", {}).get("Purchase", [])

    # Get all bill payments for the year
    billpay_result = await qb_query_all(
        f"SELECT * FROM BillPayment WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    bill_payments = billpay_result.get("QueryResponse", {}).get("BillPayment", [])

    # Get all bills for the year (for bill-based payments)
    bill_result = await qb_query_all(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    bills = bill_result.get("QueryResponse", {}).get("Bill", [])

    # Build vendor lookup
    vendor_map = {}
    for v in vendors:
        vid = v.get("Id", "")
        vendor_map[vid] = {
            "name": v.get("DisplayName", "?"),
            "company": v.get("CompanyName", ""),
            "tin": v.get("TaxIdentifier", ""),
            "vendor1099": v.get("Vendor1099", False),
            "email": v.get("PrimaryEmailAddr", {}).get("Address", ""),
            "address": "",
            "total_paid": 0.0,
            "payment_count": 0,
        }
        addr = v.get("BillAddr", {})
        if addr:
            parts = [addr.get("Line1", ""), addr.get("City", ""),
                     addr.get("CountrySubDivisionCode", ""), addr.get("PostalCode", "")]
            vendor_map[vid]["address"] = ", ".join(p for p in parts if p)

    # Tally from purchases (direct payments)
    for p in purchases:
        entity_ref = p.get("EntityRef", {})
        vid = entity_ref.get("value", "")
        if vid in vendor_map:
            amount = float(p.get("TotalAmt", 0))
            vendor_map[vid]["total_paid"] += amount
            vendor_map[vid]["payment_count"] += 1

    # Tally from bills
    for b in bills:
        entity_ref = b.get("VendorRef", {})
        vid = entity_ref.get("value", "")
        if vid in vendor_map:
            amount = float(b.get("TotalAmt", 0))
            vendor_map[vid]["total_paid"] += amount
            vendor_map[vid]["payment_count"] += 1

    # 1099-NEC applies ONLY to vendors the business marked "Track payments for
    # 1099" in QuickBooks (the Vendor1099 flag). Filtering by dollar amount
    # alone wrongly swept in banks and credit-card/loan payments, SaaS
    # corporations, product purchases, and owner draws — none of which are
    # 1099-NEC reportable. Respect the flag: reportable = flagged vendors only.
    any_flagged = any(info["vendor1099"] for info in vendor_map.values())
    reportable, review = [], []
    for info in vendor_map.values():
        if info["total_paid"] < threshold:
            continue
        (reportable if info["vendor1099"] else review).append(info)
    reportable.sort(key=lambda x: x["total_paid"], reverse=True)
    review.sort(key=lambda x: x["total_paid"], reverse=True)

    lines = [
        f"## 1099-NEC Contractor Report — {tax_year}",
        f"**Threshold:** {fmt(threshold)} · reportable = vendors marked "
        "“Track payments for 1099” in QuickBooks",
        f"**Reportable vendors:** {len(reportable)}\n",
    ]

    grand_total = 0.0
    missing_tin = 0
    missing_addr = 0

    if reportable:
        for i, v in enumerate(reportable, 1):
            grand_total += v["total_paid"]
            if not v["tin"]:
                missing_tin += 1
            if not v["address"]:
                missing_addr += 1
            tin_status = "✅ On file" if v["tin"] else "⚠️ MISSING"
            lines.append(f"### {i}. {v['name']}")
            lines.append(f"  **Total Paid:** {fmt(v['total_paid'])} ({v['payment_count']} payments)")
            lines.append(f"  **TIN Status:** {tin_status}")
            if v["company"]:
                lines.append(f"  **Company:** {v['company']}")
            lines.append("  **Address:** " + (v["address"] or
                         "⚠️ MISSING — needed for 1099-NEC filing"))
            if v["email"]:
                lines.append(f"  **Email:** {v['email']}")
            lines.append("")
    elif not any_flagged:
        lines.append(
            "No vendors are marked for 1099 tracking in QuickBooks, so there is "
            "nothing to report yet. In QuickBooks, open each **contractor** vendor "
            "→ **Edit** → check **“Track payments for 1099”** (and collect "
            "a W-9), then re-run. 1099-NEC covers non-employee **compensation** — "
            "not corporations, credit-card/loan payments, product purchases, or "
            "owner draws.\n")
    else:
        lines.append("No 1099-flagged vendors reached the threshold this year.\n")

    # Advisory review list: paid over threshold but NOT flagged. These are NOT
    # automatically reportable — most (banks, corporations, goods, owner draws)
    # are excluded from 1099-NEC. Surfaced only so a real contractor that wasn't
    # flagged can be caught and corrected in QuickBooks.
    if review:
        lines.append("---")
        lines.append(f"### Not marked for 1099 — review ({len(review)})")
        lines.append(
            "*Paid over the threshold but not flagged in QuickBooks, so **not "
            "counted above**. Corporations, product purchases, credit-card/loan "
            "payments, and owner draws are not 1099-NEC reportable. If any below "
            "is an individual/LLC you paid for services, mark them in QuickBooks "
            "and re-run.*\n")
        for v in review[:20]:
            lines.append(f"  - {v['name']}: {fmt(v['total_paid'])} "
                         f"({v['payment_count']} payments)")
        lines.append("")

    lines.extend([
        f"---",
        f"### Summary",
        f"  Reportable (1099-flagged) payments: {fmt(grand_total)}",
        f"  Vendors requiring 1099-NEC: {len(reportable)}",
        f"  Missing TIN: {missing_tin}",
        f"  Missing address: {missing_addr}",
        "",
    ])

    if reportable and (missing_tin > 0 or missing_addr > 0):
        lines.append("### ⚠️ Action Items")
        if missing_tin > 0:
            lines.append(f"  - Collect W-9 from {missing_tin} flagged vendor(s) to get TIN")
        if missing_addr > 0:
            lines.append(f"  - Collect mailing address from {missing_addr} flagged vendor(s)")
        lines.append(f"  - 1099-NEC filing deadline: January 31, {int(tax_year)+1}")
        lines.append(f"  - Use IRS FIRE system or approved e-file provider")

    _audit_log("1099_REPORT", f"year={tax_year} reportable={len(reportable)} total={fmt(grand_total)}")
    return "\n".join(lines) + tax_data_footer(int(tax_year))


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Canadian payroll differs — hand T4/T4A summaries to your accountant.")
async def qb_payroll_checklist(tax_year: str = "") -> str:
    """Payroll boundary checklist. AccountingQB does NOT run payroll or compute
    payroll taxes — this inspects the books for payroll signals (wages, payroll-
    tax liability accounts, 1099 contractors) and produces the checklist to hand
    your CPA / payroll provider: W-2 vs 1099 classification, 941/940 reconciliation,
    and year-end forms. tax_year: YYYY (default: current year)."""
    from datetime import date as _d
    if not tax_year:
        tax_year = str(_d.today().year)
    start, end = f"{tax_year}-01-01", f"{tax_year}-12-31"

    pl = await qb_request("GET", "reports/ProfitAndLoss",
                          params={"start_date": start, "end_date": end})
    exp = _extract_pl_expense_accounts(pl)
    wage_accts = {n: v for n, v in exp.items()
                  if _re.search(r"\b(wage|salar|payroll)", n, _re.IGNORECASE)}
    total_wages = sum(abs(v) for v in wage_accts.values())

    payroll_liabs = {}
    try:
        liabs = await qb_query(
            "SELECT * FROM Account WHERE AccountType IN ('Other Current Liability',"
            "'Long Term Liability') MAXRESULTS 100")
        for a in liabs.get("QueryResponse", {}).get("Account", []):
            nm = a.get("Name", "")
            if _re.search(r"payroll|941|940|futa|suta|fica|withhold|employ",
                          nm, _re.IGNORECASE):
                payroll_liabs[nm] = float(a.get("CurrentBalance", 0) or 0)
    except Exception as e:
        logger.debug(f"payroll liability query failed: {e}")

    try:
        vres = await qb_query("SELECT * FROM Vendor WHERE Vendor1099 = true MAXRESULTS 100")
        contractors_1099 = len(vres.get("QueryResponse", {}).get("Vendor", []))
    except Exception:
        contractors_1099 = 0

    lines = [
        f"## Payroll Boundary Checklist — {tax_year}\n",
        "AccountingQB does **not** run payroll, compute payroll taxes, or file "
        "employment returns. Here's what your books show and what to hand your CPA "
        "or payroll provider.\n",
        "### What the books show",
    ]
    if wage_accts:
        lines.append(f"- **Wages/salaries booked:** {fmt(total_wages)} across "
                     f"{len(wage_accts)} account(s) — indicates **W-2 employees**.")
        for n, v in sorted(wage_accts.items(), key=lambda x: -abs(x[1])):
            lines.append(f"  - {n}: {fmt(abs(v))}")
    else:
        lines.append("- No wages/salary expense detected — likely no W-2 employees "
                     "(a Schedule C owner's draws are **not** wages).")
    if payroll_liabs:
        lines.append(f"- **Payroll-tax liability accounts:** {len(payroll_liabs)} "
                     "(year-end balances should tie to filed 941/940).")
        for n, v in payroll_liabs.items():
            lines.append(f"  - {n}: {fmt(v)}")
    lines.append(f"- **Contractors flagged for 1099:** {contractors_1099} "
                 "(run qb_1099_contractor_report).")

    lines.append("\n### Hand to your CPA / payroll provider")
    lines.append("- [ ] W-2 vs 1099 classification confirmed for every worker "
                 "(misclassification is the #1 payroll audit issue)")
    if wage_accts:
        lines.append("- [ ] Form 941 (quarterly) reconciles to booked wages + withholding")
        lines.append("- [ ] Form 940 (FUTA, annual) filed")
        lines.append("- [ ] W-2 / W-3 issued to employees (due Jan 31)")
        lines.append("- [ ] Payroll-tax liability accounts cleared after each deposit")
    lines.append("- [ ] 1099-NEC issued to reportable contractors (due Jan 31)")
    lines.append("- [ ] State unemployment (SUTA) + withholding returns filed")

    lines.append("\n*Boundary checklist, not payroll-tax advice. Use a payroll "
                 "provider (Gusto, QuickBooks Payroll, ADP) or your CPA to compute "
                 "and file employment taxes.*")
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_bank_reconciliation(account_name: str, csv_data: str,
                                 start_date: str = "", end_date: str = "",
                                 tolerance_days: int = 4) -> str:
    """Reconcile a bank / credit-card statement against the books. QuickBooks
    Online's API does not expose cleared/reconciled status, so paste your
    statement as CSV (columns like Date, Description, Amount) and this produces
    the tie-out: matched, in-statement-not-in-books (missing entries to add), and
    in-books-not-in-statement (uncleared / outstanding). account_name: the QB
    account (for context). tolerance_days: date window for a match (default 4).
    Dates default to the statement's own range."""
    import csv as _csv
    import io as _io

    reader = _csv.reader(_io.StringIO(csv_data.strip()))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return "No CSV rows found. Provide columns like Date, Description, Amount."
    hdr = [h.strip().lower() for h in rows[0]]

    def _col(*names):
        for i, h in enumerate(hdr):
            if any(n in h for n in names):
                return i
        return -1

    di, ai, ni = _col("date"), _col("amount", "debit", "credit"), _col("desc", "memo", "payee", "name")
    body = rows[1:] if (di >= 0 or ai >= 0) else rows
    if di < 0:
        di = 0
    if ai < 0:
        ai = len(hdr) - 1

    def _num(x):
        x = x.strip().replace("$", "").replace(",", "")
        neg = x.startswith("(") and x.endswith(")")
        x = x.strip("()")
        try:
            v = float(x)
            return -v if neg else v
        except ValueError:
            return None

    bank = []
    for r in body:
        if len(r) <= max(di, ai):
            continue
        amt = _num(r[ai])
        if amt is None:
            continue
        bank.append({"date": r[di].strip()[:10],
                     "desc": (r[ni].strip() if 0 <= ni < len(r) else ""),
                     "amount": amt})
    if not bank:
        return ("Could not parse amounts from the CSV — expected a numeric Amount "
                "column (Date, Description, Amount).")

    dates = [b["date"] for b in bank if b["date"]]
    start = start_date or (min(dates) if dates else "")
    end = end_date or (max(dates) if dates else "")

    book = []
    for entity in ("Purchase", "BillPayment", "Deposit", "Payment",
                   "SalesReceipt", "JournalEntry"):
        try:
            r = await qb_query_all(f"SELECT * FROM {entity} WHERE TxnDate >= '{start}' "
                               f"AND TxnDate <= '{end}' MAXRESULTS 1000")
            for t in r.get("QueryResponse", {}).get(entity, []):
                amt = float(t.get("TotalAmt", 0) or 0)
                if amt == 0:
                    continue
                party = (t.get("EntityRef") or t.get("VendorRef")
                         or t.get("CustomerRef") or {}).get("name", "")
                book.append({"date": (t.get("TxnDate", "") or "")[:10], "amount": amt,
                             "party": party, "type": entity, "id": t.get("Id"),
                             "matched": False})
        except Exception as e:
            logger.debug(f"{entity} query failed in bank rec: {e}")

    def _pd(x):
        try:
            return datetime.strptime((x or "")[:10], "%Y-%m-%d")
        except ValueError:
            return None

    matched, unmatched_bank = [], []
    for b in bank:
        bd, target = _pd(b["date"]), abs(b["amount"])
        hit = None
        for k in book:
            if k["matched"] or abs(abs(k["amount"]) - target) >= 0.01:
                continue
            kd = _pd(k["date"])
            if (bd and kd and abs((kd - bd).days) <= tolerance_days) or not (bd and kd):
                hit = k
                break
        if hit:
            hit["matched"] = True
            matched.append(b)
        else:
            unmatched_bank.append(b)
    unmatched_book = [k for k in book if not k["matched"]]

    lines = [
        f"## Bank Reconciliation — {account_name or 'account'} ({start} to {end})",
        f"*Statement lines: {len(bank)} · book transactions: {len(book)}*\n",
        f"- ✅ **Matched:** {len(matched)}",
        f"- 🔴 **In statement, not in books:** {len(unmatched_bank)} (missing entries to add)",
        f"- 🟡 **In books, not in statement:** {len(unmatched_book)} (uncleared / outstanding)\n",
    ]
    if unmatched_bank:
        lines.append("### 🔴 On the statement but not in QuickBooks")
        lines.append("| Date | Description | Amount |")
        lines.append("|---|---|---|")
        for b in unmatched_bank[:50]:
            lines.append(f"| {b['date']} | {b['desc'][:40]} | {fmt(b['amount'])} |")
    if unmatched_book:
        lines.append("\n### 🟡 In QuickBooks but not on the statement (uncleared)")
        lines.append("| Date | Party | Amount | Transaction |")
        lines.append("|---|---|---|---|")
        for k in unmatched_book[:50]:
            lines.append(f"| {k['date']} | {k['party'] or '—'} | {fmt(k['amount'])} "
                         f"| {k['type']} #{k['id']} |")
    lines.append("\n*Matched by amount within the date tolerance — verify before "
                 "clearing. QuickBooks Online's API does not expose cleared/"
                 "reconciled status, which is why this reconciles against your "
                 "statement CSV.*")
    return "\n".join(lines)


# ===================================================================
# NEW: Anomaly Detection
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_anomaly_detection(start_date: str, end_date: str, sensitivity: str = "medium") -> str:
    """Analyze transactions for anomalies and unusual patterns.
    Detects: unusually large transactions, duplicate payments, weekend/holiday activity,
    round-number payments, vendor concentration risk, and statistical outliers.
    sensitivity: low (flag only extreme), medium (balanced), high (flag more).
    start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")
    sensitivity = _sanitize_input(sensitivity, "sensitivity")

    if sensitivity not in ("low", "medium", "high"):
        sensitivity = "medium"

    # Set z-score thresholds based on sensitivity
    z_thresholds = {"low": 3.0, "medium": 2.0, "high": 1.5}
    z_limit = z_thresholds[sensitivity]

    # Fetch all purchases
    purchase_result = await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    purchases = purchase_result.get("QueryResponse", {}).get("Purchase", [])

    # Fetch bills
    bill_result = await qb_query_all(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    bills = bill_result.get("QueryResponse", {}).get("Bill", [])

    # Equity/owner account keywords — these are personal transfers (CC payments,
    # owner draws, personal expenses), NOT vendor payments. We exclude them from
    # round-number, outlier, and weekend checks to reduce false positives.
    EQUITY_KEYWORDS = {
        "owner investment", "owner draw", "personal expense", "personal healthcare",
        "opening balance equity", "federal estimated tax", "state tax",
        "owner retirement", "health insurance premium", "hsa contribution",
    }

    def _is_equity_txn(txn):
        """Check if a transaction is an owner/equity transfer (not a real vendor payment)."""
        acct = txn.get("account_category", "").lower()
        memo = txn.get("memo", "").lower()
        for kw in EQUITY_KEYWORDS:
            if kw in acct or kw in memo:
                return True
        # Also catch common CC payment memos from bank imports
        if "mobile payment" in memo and "thank you" in memo:
            return True
        if "online transfer" in memo and ("payment" in memo or "debit" in memo):
            return True
        return False

    # Combine into unified transaction list
    all_txns = []
    for p in purchases:
        # Extract expense category from line items for equity detection
        line_categories = []
        for line in p.get("Line", []):
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name:
                line_categories.append(acct_name)
        all_txns.append({
            "type": "Purchase",
            "id": p.get("Id", "?"),
            "date": p.get("TxnDate", "?"),
            "amount": float(p.get("TotalAmt", 0)),
            "vendor": p.get("EntityRef", {}).get("name", "Unknown"),
            "memo": p.get("PrivateNote", p.get("Memo", "")),
            "account": p.get("AccountRef", {}).get("name", "?"),
            "account_category": ", ".join(line_categories),
            "is_equity": False,  # set below
        })
    for b in bills:
        line_categories = []
        for line in b.get("Line", []):
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name:
                line_categories.append(acct_name)
        all_txns.append({
            "type": "Bill",
            "id": b.get("Id", "?"),
            "date": b.get("TxnDate", "?"),
            "amount": float(b.get("TotalAmt", 0)),
            "vendor": b.get("VendorRef", {}).get("name", "Unknown"),
            "memo": b.get("PrivateNote", ""),
            "account": "",
            "account_category": ", ".join(line_categories),
            "is_equity": False,
        })

    # Tag equity transactions
    for t in all_txns:
        t["is_equity"] = _is_equity_txn(t)

    if not all_txns:
        return "No transactions found in the date range."

    # Use only non-equity, business transactions for statistical baseline
    biz_txns = [t for t in all_txns if not t["is_equity"]]
    amounts = [t["amount"] for t in biz_txns if t["amount"] > 0]
    equity_count = sum(1 for t in all_txns if t["is_equity"])
    if not amounts:
        return "No non-zero transactions found."

    # Recurring/subscription vendors: automated billing (SaaS, usage-based) runs
    # on any day of the week and often repeats at identical amounts on adjacent
    # days, so flagging those as "weekend" or "duplicate" is pure noise. Treat a
    # vendor as recurring if it appears >=3 times in the period, or its expense
    # account looks like software/subscription/SaaS.
    from collections import Counter
    _vendor_freq = Counter(t["vendor"] for t in biz_txns if t["vendor"] != "Unknown")
    _saas_re = _re.compile(
        r"\b(software|subscription|saas|hosting|cloud|web services|app|dues)\b",
        _re.IGNORECASE)
    recurring_vendors = {v for v, c in _vendor_freq.items() if c >= 3} | {
        t["vendor"] for t in biz_txns
        if t["vendor"] != "Unknown" and _saas_re.search(t.get("account_category", ""))
    }

    # Statistical analysis
    import statistics
    mean_amt = statistics.mean(amounts)
    stdev_amt = statistics.stdev(amounts) if len(amounts) > 1 else 0
    median_amt = statistics.median(amounts)

    anomalies = []

    # 1. Statistical outliers (z-score) — skip equity/owner transfers
    for t in biz_txns:
        if stdev_amt > 0 and t["amount"] > 0:
            z = (t["amount"] - mean_amt) / stdev_amt
            if z > z_limit:
                anomalies.append({
                    "category": "Statistical Outlier",
                    "severity": "HIGH" if z > 3 else "MEDIUM",
                    "detail": f"{t['type']} #{t['id']} on {t['date']}: {fmt(t['amount'])} to {t['vendor']} (z-score: {z:.1f})",
                    "txn": t,
                })

    # 2. Duplicate detection (same vendor + similar amount within 3 days)
    # Skip equity transactions — CC payment on credit card + bank debit are two
    # legs of the same transfer, not duplicates.
    from datetime import timedelta
    non_equity_txns = [t for t in all_txns if not t["is_equity"]]
    sorted_txns = sorted(non_equity_txns, key=lambda x: (x["vendor"], x["date"]))
    for i in range(len(sorted_txns) - 1):
        a = sorted_txns[i]
        b = sorted_txns[i + 1]
        if (a["vendor"] == b["vendor"] and a["vendor"] != "Unknown"
                and a["vendor"] not in recurring_vendors):
            try:
                date_a = datetime.strptime(a["date"], "%Y-%m-%d")
                date_b = datetime.strptime(b["date"], "%Y-%m-%d")
                day_diff = abs((date_b - date_a).days)
                amt_diff = abs(a["amount"] - b["amount"])
                # Same vendor + same amount + SAME DAY is the real double-charge
                # signature. Adjacent-day identical charges are normal usage-based
                # billing (Cursor/Windsurf), not duplicates.
                if day_diff == 0 and amt_diff < 0.01 and a["amount"] > 0:
                    anomalies.append({
                        "category": "Potential Duplicate",
                        "severity": "HIGH",
                        "detail": f"{a['vendor']}: {fmt(a['amount'])} on {a['date']} & {b['date']} ({a['type']} #{a['id']} & #{b['id']})",
                        "txn": a,
                    })
            except ValueError:
                pass

    # 3. Round-number payments — skip equity (CC payments are naturally round)
    for t in biz_txns:
        if t["amount"] >= 1000 and t["amount"] == round(t["amount"], -2):
            anomalies.append({
                "category": "Round Number",
                "severity": "LOW",
                "detail": f"{t['type']} #{t['id']}: {fmt(t['amount'])} to {t['vendor']} on {t['date']}",
                "txn": t,
            })

    # 4. Weekend transactions — skip equity (CC bills) and recurring/subscription
    # vendors (automated billing runs on weekends; flagging it is noise).
    for t in biz_txns:
        if t["vendor"] in recurring_vendors:
            continue
        try:
            d = datetime.strptime(t["date"], "%Y-%m-%d")
            if d.weekday() >= 5:  # Saturday=5, Sunday=6
                day_name = "Saturday" if d.weekday() == 5 else "Sunday"
                anomalies.append({
                    "category": "Weekend Transaction",
                    "severity": "LOW",
                    "detail": f"{t['type']} #{t['id']}: {fmt(t['amount'])} to {t['vendor']} on {t['date']} ({day_name})",
                    "txn": t,
                })
        except ValueError:
            pass

    # 5. Vendor concentration risk — use business txns only for accurate %
    vendor_totals = {}
    total_spend = sum(amounts) if amounts else 0
    for t in biz_txns:
        v = t["vendor"]
        vendor_totals[v] = vendor_totals.get(v, 0) + t["amount"]
    for v, total in vendor_totals.items():
        pct = (total / total_spend * 100) if total_spend > 0 else 0
        if pct > 30 and v != "Unknown":
            anomalies.append({
                "category": "Vendor Concentration",
                "severity": "MEDIUM",
                "detail": f"{v}: {fmt(total)} = {pct:.1f}% of total spend",
                "txn": None,
            })

    # Deduplicate
    seen = set()
    unique_anomalies = []
    for a in anomalies:
        key = a["detail"]
        if key not in seen:
            seen.add(key)
            unique_anomalies.append(a)

    # Sort by severity
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    unique_anomalies.sort(key=lambda x: sev_order.get(x["severity"], 3))

    lines = [
        f"## Transaction Anomaly Report",
        f"**Period:** {start_date} to {end_date}",
        f"**Total Transactions:** {len(all_txns)} ({equity_count} owner/equity transfers excluded from checks)",
        f"**Business Transactions Analyzed:** {len(biz_txns)}",
        f"**Sensitivity:** {sensitivity} (z-score threshold: {z_limit})",
        f"**Anomalies Found:** {len(unique_anomalies)}\n",
        f"### Statistics (business transactions only)",
        f"  Mean transaction: {fmt(mean_amt)}",
        f"  Median transaction: {fmt(median_amt)}",
        f"  Std deviation: {fmt(stdev_amt)}",
        f"  Total business spend: {fmt(total_spend)}\n",
    ]

    if not unique_anomalies:
        lines.append("✅ No anomalies detected at this sensitivity level.")
    else:
        # Group by category
        from collections import defaultdict
        by_cat = defaultdict(list)
        for a in unique_anomalies:
            by_cat[a["category"]].append(a)

        for cat, items in by_cat.items():
            lines.append(f"### {cat} ({len(items)})")
            for a in items:
                icon = "🔴" if a["severity"] == "HIGH" else "🟡" if a["severity"] == "MEDIUM" else "🟢"
                lines.append(f"  {icon} [{a['severity']}] {a['detail']}")
            lines.append("")

    _audit_log("ANOMALY_DETECTION", f"period={start_date}/{end_date} txns={len(all_txns)} anomalies={len(unique_anomalies)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Credit Memo Management
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_credit_memos(start_date: str, end_date: str, customer_name: str = "", max_results: int = 100) -> str:
    """List credit memos (customer credits/refunds) within a date range.
    Credit memos reduce what a customer owes. Optionally filter by customer_name.
    start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    query = f"SELECT * FROM CreditMemo WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if customer_name:
        customer_name = _sanitize_input(customer_name, "customer_name")
        # Look up customer first
        cust_result = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 5")
        customers = cust_result.get("QueryResponse", {}).get("Customer", [])
        if customers:
            cust_id = customers[0]["Id"]
            query += f" AND CustomerRef = '{cust_id}'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    memos = result.get("QueryResponse", {}).get("CreditMemo", [])

    if not memos:
        return "No credit memos found in the date range."

    total = 0.0
    lines = [f"## Credit Memos ({start_date} to {end_date})\n"]
    for cm in memos:
        cm_id = cm.get("Id", "?")
        date = cm.get("TxnDate", "?")
        cust = cm.get("CustomerRef", {}).get("name", "?")
        amount = float(cm.get("TotalAmt", 0))
        balance = float(cm.get("RemainingCredit", 0))
        memo = cm.get("PrivateNote", "")
        doc_num = cm.get("DocNumber", "")
        total += amount

        lines.append(f"**#{doc_num or cm_id}** | {date} | {cust}")
        lines.append(f"  Amount: {fmt(amount)} | Remaining: {fmt(balance)}")
        if memo:
            lines.append(f"  Memo: {memo[:80]}")
        lines.append("")

    lines.append(f"---\n**Total Credit Memos:** {fmt(total)} ({len(memos)} memos)")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_credit_memo(customer_name: str, line_items: str, date: str = "", memo: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a credit memo for a customer. Reduces what the customer owes.
    customer_name: customer to credit. line_items: JSON string array
    [{\"description\": \"Returned item\", \"amount\": 50.00}].
    date: YYYY-MM-DD (defaults to today). memo: internal note.
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; per-line override via 'tax_code' key in line_items JSON; tax_inclusive=True when amounts already include tax."""
    customer_name = _sanitize_input(customer_name, "customer_name")
    import json as _json

    # Find customer
    cust_result = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 5")
    customers = cust_result.get("QueryResponse", {}).get("Customer", [])
    if not customers:
        return f"Customer '{customer_name}' not found."
    if len(customers) > 1:
        names = ", ".join(f"{c['DisplayName']} (ID:{c['Id']})" for c in customers)
        return f"Multiple customers match: {names}. Be more specific."
    customer = customers[0]

    try:
        items = _json.loads(line_items)
    except _json.JSONDecodeError:
        return "Invalid line_items JSON. Use format: [{\"description\": \"...\", \"amount\": 100}]"

    region = (await _get_region())["region"]
    default_tax_id = None
    tax_cache: dict = {}
    if region != "US" and tax_code:
        try:
            default_tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)

    cm_lines = []
    for item in items:
        amt = _validate_amount(float(item.get("amount", 0)), "line amount")
        line = {
            "Amount": amt,
            "Description": item.get("description", ""),
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "ItemRef": {"value": "1", "name": "Services"},
            },
        }
        try:
            line_tax = await _line_tax_code_ref(item, region, tax_cache)
        except ValueError as e:
            return str(e)
        if line_tax:
            line["SalesItemLineDetail"]["TaxCodeRef"] = line_tax
        cm_lines.append(line)

    if region != "US" and not default_tax_id and not any(
        "TaxCodeRef" in l["SalesItemLineDetail"] for l in cm_lines
    ):
        return _TAX_CODE_REQUIRED_MSG

    body = {
        "CustomerRef": {"value": customer["Id"]},
        "Line": cm_lines,
    }
    if date:
        body["TxnDate"] = _validate_date(date, "date")
    if memo:
        body["PrivateNote"] = memo
    _apply_global_tax(body, "Line", "SalesItemLineDetail",
                      default_tax_id, tax_inclusive, region)

    result = await qb_request("POST", "creditmemo", json_body=body)
    cm = result.get("CreditMemo", {})

    _audit_log("CREATE_CREDIT_MEMO", f"customer={customer['DisplayName']} amount={fmt(float(cm.get('TotalAmt', 0)))}")
    return (
        f"✅ Credit memo created\n"
        f"  ID: {cm.get('Id')}\n"
        f"  Customer: {customer['DisplayName']}\n"
        f"  Amount: {fmt(float(cm.get('TotalAmt', 0)))}\n"
        f"  Date: {cm.get('TxnDate', 'today')}"
    )


# ===================================================================
# NEW: Vendor Credit Management
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_vendor_credits(start_date: str, end_date: str, vendor_name: str = "", max_results: int = 100) -> str:
    """List vendor credits within a date range. Vendor credits reduce what you owe a vendor.
    Optionally filter by vendor_name. start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    query = f"SELECT * FROM VendorCredit WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if vendor_name:
        vendor_name = _sanitize_input(vendor_name, "vendor_name")
        vend_result = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 5")
        vendors = vend_result.get("QueryResponse", {}).get("Vendor", [])
        if vendors:
            vend_id = vendors[0]["Id"]
            query += f" AND VendorRef = '{vend_id}'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    credits = result.get("QueryResponse", {}).get("VendorCredit", [])

    if not credits:
        return "No vendor credits found in the date range."

    total = 0.0
    lines = [f"## Vendor Credits ({start_date} to {end_date})\n"]
    for vc in credits:
        vc_id = vc.get("Id", "?")
        date = vc.get("TxnDate", "?")
        vend = vc.get("VendorRef", {}).get("name", "?")
        amount = float(vc.get("TotalAmt", 0))
        memo = vc.get("PrivateNote", "")
        total += amount

        lines.append(f"**#{vc_id}** | {date} | {vend} | {fmt(amount)}")
        if memo:
            lines.append(f"  Memo: {memo[:80]}")

        for line in vc.get("Line", []):
            acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
            if acct:
                lines.append(f"  - {acct}: {fmt(float(line.get('Amount', 0)))}")
        lines.append("")

    lines.append(f"---\n**Total Vendor Credits:** {fmt(total)} ({len(credits)} credits)")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_vendor_credit(vendor_name: str, amount: float, account_name: str, date: str = "", description: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a vendor credit. Reduces what you owe a vendor (e.g., refund, return, pricing adjustment).
    vendor_name: vendor issuing the credit. amount: credit amount.
    account_name: expense account to reduce. date: YYYY-MM-DD (defaults to today).
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; tax_inclusive=True when amount already includes tax."""
    vendor_name = _sanitize_input(vendor_name, "vendor_name")
    account_name = _sanitize_input(account_name, "account_name")
    amount = _validate_amount(amount, "amount")

    # Find vendor
    vend_result = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 5")
    vendors = vend_result.get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return f"Vendor '{vendor_name}' not found."
    if len(vendors) > 1:
        names = ", ".join(f"{v['DisplayName']} (ID:{v['Id']})" for v in vendors)
        return f"Multiple vendors match: {names}. Be more specific."
    vendor = vendors[0]

    # Find account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{account_name}' not found."
    account = accounts[0]

    body = {
        "VendorRef": {"value": vendor["Id"]},
        "Line": [{
            "Amount": amount,
            "Description": description,
            "DetailType": "AccountBasedExpenseLineDetail",
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"value": account["Id"], "name": account["Name"]},
            },
        }],
    }
    if date:
        body["TxnDate"] = _validate_date(date, "date")

    region = (await _get_region())["region"]
    if region != "US":
        if not tax_code:
            return _TAX_CODE_REQUIRED_MSG
        try:
            tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)
        _apply_global_tax(body, "Line", "AccountBasedExpenseLineDetail",
                          tax_id, tax_inclusive, region)

    result = await qb_request("POST", "vendorcredit", json_body=body)
    vc = result.get("VendorCredit", {})

    _audit_log("CREATE_VENDOR_CREDIT", f"vendor={vendor['DisplayName']} amount={fmt(amount)}")
    return (
        f"✅ Vendor credit created\n"
        f"  ID: {vc.get('Id')}\n"
        f"  Vendor: {vendor['DisplayName']}\n"
        f"  Amount: {fmt(amount)}\n"
        f"  Account: {account['Name']}\n"
        f"  Date: {vc.get('TxnDate', 'today')}"
    )


# ===================================================================
# NEW: Sales Tax Summary
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_sales_tax_summary(start_date: str = "", end_date: str = "") -> str:
    """Generate a sales tax summary report for a date range.
    Shows taxable sales, tax collected, tax rates, and liability by jurisdiction.
    Useful for state/local sales tax filing. Dates YYYY-MM-DD (default: current year-to-date)."""
    start_date, end_date = _ytd_range(start_date, end_date)
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    # Canadian companies get return-ready GST34 numbers from qb_gst_hst_return;
    # this tool stays useful as the generic by-jurisdiction TxnTaxDetail view.
    ca_note = []
    if (await _get_region())["region"] == "CA":
        ca_note = [
            "*Canadian company detected — run qb_gst_hst_return for return-ready "
            "GST34 line numbers (101/103/106/109) and ITC restrictions. The "
            "breakdown below is the by-jurisdiction detail.*\n"
        ]

    # Get invoices and sales receipts with tax
    inv_result = await qb_query_all(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    invoices = inv_result.get("QueryResponse", {}).get("Invoice", [])

    sr_result = await qb_query_all(
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    sales_receipts = sr_result.get("QueryResponse", {}).get("SalesReceipt", [])

    # Customer cash refunds net back out of taxable sales and tax collected.
    refunds = []
    try:
        ref_result = await qb_query_all(
            f"SELECT * FROM RefundReceipt WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
        )
        refunds = ref_result.get("QueryResponse", {}).get("RefundReceipt", [])
    except Exception as e:
        logger.debug(f"RefundReceipt query failed: {e}")

    # Try to get the TaxAgency / TaxCode info
    tax_code_result = await qb_query("SELECT * FROM TaxCode MAXRESULTS 50")
    tax_codes = tax_code_result.get("QueryResponse", {}).get("TaxCode", [])

    tax_rate_result = await qb_query("SELECT * FROM TaxRate MAXRESULTS 50")
    tax_rates = tax_rate_result.get("QueryResponse", {}).get("TaxRate", [])

    # Build tax rate lookup
    rate_map = {}
    for tr in tax_rates:
        rate_map[tr.get("Id", "")] = {
            "name": tr.get("Name", "?"),
            "rate": float(tr.get("RateValue", 0)),
            "agency": tr.get("AgencyRef", {}).get("name", "?"),
        }

    total_taxable = 0.0
    total_tax = 0.0
    total_exempt = 0.0
    total_gross = 0.0
    tax_by_rate = {}

    for txn_list, sign in [(invoices, 1), (sales_receipts, 1), (refunds, -1)]:
        for txn in txn_list:
            total_amt = float(txn.get("TotalAmt", 0))
            tax_amt = float(txn.get("TxnTaxDetail", {}).get("TotalTax", 0))
            total_gross += total_amt * sign
            total_tax += tax_amt * sign

            if tax_amt > 0:
                total_taxable += (total_amt - tax_amt) * sign
            else:
                total_exempt += total_amt * sign

            # Parse tax detail lines
            tax_lines = txn.get("TxnTaxDetail", {}).get("TaxLine", [])
            for tl in tax_lines:
                detail = tl.get("TaxLineDetail", {})
                rate_id = detail.get("TaxRateRef", {}).get("value", "")
                tax_on = float(detail.get("NetAmountTaxable", 0))
                tax_charged = float(tl.get("Amount", 0))
                rate_info = rate_map.get(rate_id, {"name": f"Rate#{rate_id}", "rate": 0, "agency": "?"})

                key = rate_info["name"]
                if key not in tax_by_rate:
                    tax_by_rate[key] = {
                        "rate": rate_info["rate"],
                        "agency": rate_info["agency"],
                        "taxable_amount": 0.0,
                        "tax_collected": 0.0,
                    }
                tax_by_rate[key]["taxable_amount"] += tax_on * sign
                tax_by_rate[key]["tax_collected"] += tax_charged * sign

    lines = ca_note + [
        f"## Sales Tax Summary",
        f"**Period:** {start_date} to {end_date}",
        f"**Invoices:** {len(invoices)} | **Sales Receipts:** {len(sales_receipts)}"
        + (f" | **Refunds (netted):** {len(refunds)}" if refunds else "") + "\n",
        f"### Totals",
        f"  Gross Sales: {fmt(total_gross)}",
        f"  Taxable Sales: {fmt(total_taxable)}",
        f"  Tax-Exempt Sales: {fmt(total_exempt)}",
        f"  **Total Tax Collected: {fmt(total_tax)}**\n",
    ]

    if tax_by_rate:
        lines.append(f"### Tax Breakdown by Rate")
        for name, info in sorted(tax_by_rate.items()):
            lines.append(f"  **{name}** ({info['rate']}%) — Agency: {info['agency']}")
            lines.append(f"    Taxable: {fmt(info['taxable_amount'])} | Tax: {fmt(info['tax_collected'])}")
            lines.append("")

    if tax_codes:
        lines.append(f"### Active Tax Codes ({len(tax_codes)})")
        for tc in tax_codes:
            active = "Active" if tc.get("Active") else "Inactive"
            taxable = "Taxable" if tc.get("Taxable") else "Non-Taxable"
            lines.append(f"  - {tc.get('Name', '?')} ({active}, {taxable})")

    lines.extend([
        f"\n---",
        f"*Note: Verify totals against QB Sales Tax Liability report before filing.*",
        f"*File frequency depends on your state registration.*",
    ])

    _audit_log("SALES_TAX_SUMMARY", f"period={start_date}/{end_date} tax_collected={fmt(total_tax)}")
    return "\n".join(lines) + tax_data_footer()


# ===================================================================
# SALES TAX CODES & RATES — discovery (Canada / global tax editions)
# ===================================================================

async def _tax_agency_names() -> dict:
    """Map TaxAgency Id -> DisplayName (best effort; names are cosmetic)."""
    names = {}
    try:
        result = await qb_query_all("SELECT * FROM TaxAgency MAXRESULTS 1000")
        for ta in result.get("QueryResponse", {}).get("TaxAgency", []):
            names[str(ta.get("Id", ""))] = ta.get("DisplayName", "?")
    except Exception as e:
        logger.debug(f"TaxAgency lookup failed: {e}")
    return names


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("US", "Economic nexus is US-specific; Canadian GST/HST registration differs.")
async def qb_sales_tax_nexus(year: str = "", approaching_pct: int = 80) -> str:
    """Screen for state sales-tax ECONOMIC NEXUS exposure and show sales-tax
    liability by state. Rolls up your sales by DESTINATION state (ship-to) and
    compares to each state's sourced post-Wayfair threshold. This is a screening
    reference, NOT a determination — confirm with the state and a tax professional
    before registering. year: YYYY (default: current). approaching_pct: warn at
    this % of a threshold (default 80)."""
    from datetime import date as _d
    if not year:
        year = str(_d.today().year)
    start, end = f"{year}-01-01", f"{year}-12-31"

    nexus = _tt.TABLES["US_SALES_TAX_NEXUS"]
    thresholds = nexus["values"]

    # Customer -> state fallback (used when a sale has no ship/bill address)
    cust_state = {}
    try:
        cres = await qb_query_all("SELECT * FROM Customer MAXRESULTS 1000")
        for c in cres.get("QueryResponse", {}).get("Customer", []):
            st = (c.get("ShipAddr") or c.get("BillAddr") or {}).get("CountrySubDivisionCode", "")
            if st:
                cust_state[c.get("Id", "")] = st.upper()
    except Exception as e:
        logger.debug(f"customer state map failed: {e}")

    by_state = {}  # state -> {sales, txns, tax}
    # Invoices + sales receipts add sales; RefundReceipts (customer cash refunds)
    # net back out, so a refunded sale doesn't push a state over its threshold or
    # overstate liability. A refund isn't a new sale, so it doesn't add to txns.
    for entity, sign in (("Invoice", 1), ("SalesReceipt", 1), ("RefundReceipt", -1)):
        try:
            r = await qb_query_all(f"SELECT * FROM {entity} WHERE TxnDate >= '{start}' "
                               f"AND TxnDate <= '{end}' MAXRESULTS 1000")
        except Exception as e:
            logger.debug(f"nexus {entity} query failed: {e}")
            continue
        for t in r.get("QueryResponse", {}).get(entity, []):
            st = ((t.get("ShipAddr") or {}).get("CountrySubDivisionCode")
                  or (t.get("BillAddr") or {}).get("CountrySubDivisionCode")
                  or cust_state.get((t.get("CustomerRef") or {}).get("value", ""), ""))
            st = (st or "").upper()
            if not st:
                continue
            d = by_state.setdefault(st, {"sales": 0.0, "txns": 0, "tax": 0.0})
            d["sales"] += float(t.get("TotalAmt", 0) or 0) * sign
            if sign > 0:
                d["txns"] += 1
            d["tax"] += float((t.get("TxnTaxDetail") or {}).get("TotalTax", 0) or 0) * sign

    if not by_state:
        return (f"No ship-to state found on invoices/sales receipts for {year}. "
                "Economic-nexus screening needs destination (ship-to or bill-to) "
                "states on your sales — add them in QuickBooks and re-run.")

    exposure, approaching, below, untracked = [], [], [], []
    for st, d in by_state.items():
        if st in _tt._NO_SALES_TAX_STATES:
            continue
        rule = thresholds.get(st)
        if not rule:
            untracked.append(st)
            continue
        sales_ok = d["sales"] >= rule["sales"]
        txn_ok = rule["txns"] is not None and d["txns"] >= rule["txns"]
        met = (sales_ok and (rule["txns"] is None or txn_ok)) if rule["basis"] == "and" \
            else (sales_ok or txn_ok)
        pct = (d["sales"] / rule["sales"] * 100) if rule["sales"] else 0
        rec = (st, d, rule, pct)
        if met:
            exposure.append(rec)
        elif pct >= approaching_pct or (rule["txns"] and
                                        d["txns"] >= rule["txns"] * approaching_pct / 100):
            approaching.append(rec)
        else:
            below.append(rec)

    def _thr(rule):
        s = fmt(rule["sales"])
        return f"{s} {rule['basis']} {rule['txns']} txns" if rule["txns"] else f"{s} (sales only)"

    lines = [
        f"## Sales-Tax Economic-Nexus Screen — {year}",
        f"*Sales rolled up by ship-to state vs each state's post-Wayfair threshold. "
        f"A screening reference, **not** a determination. Thresholds verified "
        f"{nexus['verified']} ([source]({nexus['source_url']})).*\n",
    ]
    if exposure:
        lines.append(f"### 🔴 Likely nexus — over the threshold ({len(exposure)})")
        lines.append("| State | Your sales | Txns | Threshold |")
        lines.append("|---|---|---|---|")
        for st, d, rule, _ in sorted(exposure, key=lambda x: -x[1]["sales"]):
            lines.append(f"| {st} | {fmt(d['sales'])} | {d['txns']} | {_thr(rule)} |")
    if approaching:
        lines.append(f"\n### 🟡 Approaching (≥{approaching_pct}% of threshold) ({len(approaching)})")
        lines.append("| State | Your sales | Txns | Threshold | % |")
        lines.append("|---|---|---|---|---|")
        for st, d, rule, pct in sorted(approaching, key=lambda x: -x[3]):
            lines.append(f"| {st} | {fmt(d['sales'])} | {d['txns']} | {_thr(rule)} | {pct:.0f}% |")
    if below:
        lines.append(f"\n### 🟢 Below threshold ({len(below)}): " +
                     ", ".join(f"{st} ({fmt(d['sales'])})"
                               for st, d, _, _ in sorted(below, key=lambda x: -x[1]["sales"])))
    if untracked:
        lines.append(f"\n### ⚠️ Not yet assessed ({len(untracked)}): " +
                     ", ".join(sorted(untracked)) +
                     " — no verified threshold on file; check the state DOR.")

    total_tax = sum(d["tax"] for d in by_state.values())
    lines.append(f"\n### Sales tax collected (liability) — {fmt(total_tax)} total")
    tax_states = [(st, d) for st, d in by_state.items() if d["tax"] > 0]
    if tax_states:
        lines.append("| State | Tax collected | Sales |")
        lines.append("|---|---|---|")
        for st, d in sorted(tax_states, key=lambda x: -x[1]["tax"]):
            lines.append(f"| {st} | {fmt(d['tax'])} | {fmt(d['sales'])} |")
    lines.append("\n*Tax collected is money you owe the state — verify each "
                 "jurisdiction's filing frequency and due dates in the state portal "
                 "(QuickBooks' API doesn't expose remittance/filed status). Run "
                 "qb_sales_tax_summary for the by-agency breakdown.*")
    lines.append("\n*Nexus edges: marketplace-facilitated sales (Amazon/Etsy) "
                 "usually don't count toward your own threshold; exempt/resale "
                 "sales don't count; the measurement window (prior vs current "
                 "calendar year) varies by state. This screen counts all ship-to "
                 "sales (net of customer refunds) — a flag to investigate, not a "
                 "final answer.*")
    return "\n".join(lines) + tax_data_footer()


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_tax_codes() -> str:
    """List this company's sales tax codes: name, Id, combined sales rate, and agency.
    In Canada/global editions, pass a code's name (e.g. 'HST ON') as tax_code= to
    create tools (qb_create_invoice, qb_create_expense, qb_create_bill, ...)."""
    region_info = await _get_region()

    tc_result = await qb_query_all("SELECT * FROM TaxCode MAXRESULTS 1000")
    tax_codes = [
        tc for tc in tc_result.get("QueryResponse", {}).get("TaxCode", [])
        if tc.get("Active", True)
    ]
    if not tax_codes:
        return "No tax codes found for this company."

    tr_result = await qb_query_all("SELECT * FROM TaxRate MAXRESULTS 1000")
    tax_rates = tr_result.get("QueryResponse", {}).get("TaxRate", [])
    agency_names = await _tax_agency_names()

    rate_map = {}
    for tr in tax_rates:
        agency_ref = tr.get("AgencyRef") or {}
        rate_map[str(tr.get("Id", ""))] = {
            "rate": float(tr.get("RateValue", 0) or 0),
            "agency": agency_ref.get("name")
                      or agency_names.get(str(agency_ref.get("value", "")), ""),
        }

    taxable, zero = [], []
    for tc in tax_codes:
        details = (tc.get("SalesTaxRateList") or {}).get("TaxRateDetail") or []
        combined = 0.0
        agencies = []
        for d in details:
            rid = str((d.get("TaxRateRef") or {}).get("value", ""))
            info = rate_map.get(rid)
            if info:
                combined += info["rate"]
                if info["agency"] and info["agency"] not in agencies:
                    agencies.append(info["agency"])
        entry = f"- **{tc.get('Name', '?')}** (Id {tc.get('Id', '?')}) — {combined:g}%"
        if agencies:
            entry += f" — Agency: {', '.join(agencies)}"
        (taxable if combined > 0 else zero).append(entry)

    lines = ["## Sales Tax Codes\n"]
    if region_info["region"] == "US":
        lines.append(
            "*This company uses US Automated Sales Tax — QuickBooks applies "
            "sales tax automatically; you normally don't need to pass tax_code.*\n"
        )
    elif region_info["region"] == "CA":
        prov_desc = _ca_regime_describe(region_info.get("subdivision", ""))
        if prov_desc:
            lines.append(
                f"*Detected province: {prov_desc} — codes whose combined rate "
                f"differs may be for other provinces or out of date.*\n"
            )
    if taxable:
        lines.append("### Taxable")
        lines.extend(taxable)
    if zero:
        lines.append("\n### Zero-rated / Exempt (0%)")
        lines.extend(zero)
    lines.append(
        "\n*Hint: pass tax_code=\"<Name>\" (e.g. tax_code=\"HST ON\") to create "
        "tools like qb_create_invoice, qb_create_expense, or qb_create_bill to "
        "apply a code to every line; JSON line_items also accept a per-line "
        "\"tax_code\" key.*"
    )
    return "\n".join(lines)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_tax_rates() -> str:
    """List this company's individual sales tax rates (rate % and tax agency).
    Tax codes (see qb_list_tax_codes) combine one or more of these rates."""
    tr_result = await qb_query_all("SELECT * FROM TaxRate MAXRESULTS 1000")
    tax_rates = tr_result.get("QueryResponse", {}).get("TaxRate", [])
    if not tax_rates:
        return "No tax rates found for this company."

    agency_names = await _tax_agency_names()

    lines = ["## Sales Tax Rates\n"]
    for tr in sorted(tax_rates, key=lambda r: r.get("Name", "")):
        agency_ref = tr.get("AgencyRef") or {}
        agency = (agency_ref.get("name")
                  or agency_names.get(str(agency_ref.get("value", "")), ""))
        entry = (f"- **{tr.get('Name', '?')}** (Id {tr.get('Id', '?')}): "
                 f"{float(tr.get('RateValue', 0) or 0):g}%")
        if agency:
            entry += f" — {agency}"
        lines.append(entry)
    return "\n".join(lines)


# ===================================================================
# NEW: Multi-Period Cash Flow Forecast
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_cash_flow_forecast(months_forward: int = 6, base_months: int = 6) -> str:
    """Forecast future cash flow based on historical patterns.
    Analyzes the last base_months of income/expenses and projects months_forward.
    Shows projected monthly cash balance, burn rate trends, and runway.
    months_forward: how many months to project (1-24).
    base_months: historical months to base projections on (3-12)."""
    months_forward = max(1, min(24, months_forward))
    base_months = max(3, min(12, base_months))

    from datetime import timedelta
    from collections import defaultdict

    today = datetime.now()
    start = (today - timedelta(days=base_months * 30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    # Get P&L by month for base period
    params = {"start_date": start, "end_date": end, "summarize_by": "Month"}
    result = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    # Parse the report
    rows = result.get("Rows", {}).get("Row", [])
    columns = result.get("Columns", {}).get("Column", [])
    month_labels = [c.get("ColTitle", "") for c in columns if c.get("ColTitle", "") != ""]

    # Extract income and expense totals per month.
    # P&L by month may have separate "Income" and "Other Income" sections
    # (and "Expenses" / "Other Expenses"), so we accumulate into dicts
    # keyed by column index, then convert to lists at the end.
    # We ignore summary rows like "Net Income", "Gross Profit", etc.
    income_by_month = defaultdict(float)
    expense_by_month = defaultdict(float)
    num_month_cols = len(month_labels)

    for row in rows:
        if row.get("type") != "Section":
            continue
        header = row.get("Header", {})
        group = header.get("ColData", [{}])[0].get("value", "") if header.get("ColData") else ""
        group_lower = group.lower().strip()

        is_income = group_lower in ("income", "other income")
        is_expense = group_lower in ("expenses", "other expenses")
        if not is_income and not is_expense:
            continue

        summary = row.get("Summary", {}).get("ColData", [])
        if not summary:
            continue

        # Summary ColData has one entry per month column plus a "Total" column.
        # The first element is the label (e.g. "Total Income"), so skip it.
        numeric_cols = summary[1:] if len(summary) > num_month_cols else summary
        for idx, col in enumerate(numeric_cols):
            val_str = col.get("value", "0").replace(",", "")
            try:
                val = float(val_str)
            except ValueError:
                continue
            if is_income:
                income_by_month[idx] += val
            else:
                expense_by_month[idx] += abs(val)

    monthly_income = [income_by_month[i] for i in sorted(income_by_month)] if income_by_month else []
    monthly_expenses = [expense_by_month[i] for i in sorted(expense_by_month)] if expense_by_month else []

    # Fallback: use P&L total approach
    if not monthly_income and not monthly_expenses:
        pl_params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
        pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=pl_params)
        pl_rows = pl_result.get("Rows", {}).get("Row", [])
        total_income = 0.0
        total_expenses = 0.0
        for row in pl_rows:
            row_data = row.get("Summary", {}).get("ColData", [])
            if row_data:
                label = row.get("Header", {}).get("ColData", [{}])[0].get("value", "")
                val_str = row_data[-1].get("value", "0").replace(",", "") if row_data else "0"
                try:
                    val = float(val_str)
                except ValueError:
                    val = 0
                label_lower = label.lower().strip()
                # Only match actual revenue/expense buckets, not "Net Income" etc.
                if label_lower in ("income", "other income"):
                    total_income += val
                elif label_lower in ("expenses", "other expenses"):
                    total_expenses += abs(val)
        avg_income = total_income / base_months
        avg_expenses = total_expenses / base_months
    else:
        import statistics
        avg_income = statistics.mean(monthly_income) if monthly_income else 0
        avg_expenses = statistics.mean(monthly_expenses) if monthly_expenses else 0

    # Get current cash position
    accts_result = await qb_query("SELECT * FROM Account WHERE AccountType = 'Bank' MAXRESULTS 20")
    bank_accounts = accts_result.get("QueryResponse", {}).get("Account", [])
    current_cash = sum(float(a.get("CurrentBalance", 0)) for a in bank_accounts)

    # Project forward
    lines = [
        f"## Cash Flow Forecast",
        f"**Based on:** Last {base_months} months of data",
        f"**Projecting:** {months_forward} months forward\n",
        f"### Current Position",
        f"  Cash on hand: {fmt(current_cash)}",
        f"  Avg monthly income: {fmt(avg_income)}",
        f"  Avg monthly expenses: {fmt(avg_expenses)}",
        f"  Net monthly: {fmt(avg_income - avg_expenses)}\n",
        f"### Monthly Projections",
        f"{'Month':<15} {'Income':>12} {'Expenses':>12} {'Net':>12} {'Balance':>14}",
        f"{'-'*65}",
    ]

    balance = current_cash
    months_to_zero = None

    for m in range(1, months_forward + 1):
        future_date = today + timedelta(days=m * 30)
        month_label = future_date.strftime("%b %Y")
        net = avg_income - avg_expenses
        balance += net

        lines.append(
            f"{month_label:<15} {fmt(avg_income):>12} {fmt(avg_expenses):>12} {fmt(net):>12} {fmt(balance):>14}"
        )
        if balance <= 0 and months_to_zero is None:
            months_to_zero = m

    lines.extend([
        "",
        f"### Runway Analysis",
    ])

    if avg_expenses > avg_income and avg_expenses > 0:
        burn = avg_expenses - avg_income
        lines.append(f"  ⚠️ **Burn rate:** {fmt(burn)}/month")
        if current_cash > 0:
            runway_months = current_cash / burn
            lines.append(f"  **Runway:** {runway_months:.1f} months")
            if runway_months < 6:
                lines.append(f"  🔴 **CRITICAL:** Less than 6 months of runway")
            elif runway_months < 12:
                lines.append(f"  🟡 **CAUTION:** Less than 12 months of runway")
        else:
            lines.append(f"  🔴 **No runway** — cash balance is {fmt(current_cash)} "
                         f"(zero or negative) while burning {fmt(burn)}/month.")
    elif avg_income > avg_expenses:
        lines.append(f"  ✅ **Positive cash flow:** {fmt(avg_income - avg_expenses)}/month")
        lines.append(f"  Cash position growing — no runway concerns")
    else:
        lines.append(f"  Break-even: income ≈ expenses")

    lines.append(f"\n*Forecast assumes constant rates. Actual results will vary.*")

    _audit_log("CASH_FLOW_FORECAST", f"months={months_forward} cash={fmt(current_cash)} net={fmt(avg_income - avg_expenses)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Profit Margin by Customer/Item
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_profit_margin_analysis(start_date: str, end_date: str, group_by: str = "customer") -> str:
    """Analyze profit margins by customer or item/product.
    Shows revenue, COGS (if tracked), and margin for each customer or item.
    group_by: 'customer' or 'item'. start_date/end_date in YYYY-MM-DD."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")
    group_by = _sanitize_input(group_by, "group_by").lower()

    if group_by not in ("customer", "item"):
        return "group_by must be 'customer' or 'item'."

    # Get invoices and sales receipts
    inv_result = await qb_query_all(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    invoices = inv_result.get("QueryResponse", {}).get("Invoice", [])

    sr_result = await qb_query_all(
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    sales_receipts = sr_result.get("QueryResponse", {}).get("SalesReceipt", [])

    from collections import defaultdict
    groups = defaultdict(lambda: {"revenue": 0.0, "cogs": 0.0, "count": 0})

    for txn_list in [invoices, sales_receipts]:
        for txn in txn_list:
            if group_by == "customer":
                key = txn.get("CustomerRef", {}).get("name", "Unknown")
                groups[key]["revenue"] += float(txn.get("TotalAmt", 0))
                groups[key]["count"] += 1
            else:
                for line in txn.get("Line", []):
                    detail = line.get("SalesItemLineDetail", {})
                    item_name = detail.get("ItemRef", {}).get("name", "")
                    if item_name:
                        amt = float(line.get("Amount", 0))
                        groups[item_name]["revenue"] += amt
                        groups[item_name]["count"] += 1

    # Try to get COGS from P&L
    params = {"start_date": start_date, "end_date": end_date, "summarize_by": "Total"}
    pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=params)
    pl_rows = pl_result.get("Rows", {}).get("Row", [])

    total_cogs = 0.0
    total_revenue = 0.0
    for row in pl_rows:
        header = row.get("Header", {}).get("ColData", [{}])[0].get("value", "")
        summary = row.get("Summary", {}).get("ColData", [])
        if summary:
            val_str = summary[-1].get("value", "0").replace(",", "")
            try:
                val = float(val_str)
            except ValueError:
                val = 0
            if "cost of goods" in header.lower():
                total_cogs = abs(val)
            elif "income" in header.lower() and "other" not in header.lower():
                total_revenue = val

    # Distribute COGS proportionally if we have it
    if total_cogs > 0 and total_revenue > 0:
        for key, data in groups.items():
            proportion = data["revenue"] / total_revenue if total_revenue > 0 else 0
            data["cogs"] = total_cogs * proportion

    # Sort by revenue
    sorted_groups = sorted(groups.items(), key=lambda x: x[1]["revenue"], reverse=True)

    lines = [
        f"## Profit Margin Analysis by {group_by.title()}",
        f"**Period:** {start_date} to {end_date}",
        f"**{group_by.title()}s:** {len(sorted_groups)}\n",
    ]

    if total_cogs > 0:
        lines.append(f"*COGS distributed proportionally to revenue (total COGS: {fmt(total_cogs)})*\n")
    else:
        lines.append(f"*No COGS tracked — margins show gross revenue only*\n")

    lines.append(f"{'Name':<30} {'Revenue':>12} {'COGS':>12} {'Margin':>12} {'%':>8} {'Txns':>6}")
    lines.append(f"{'-'*80}")

    grand_revenue = 0.0
    grand_cogs = 0.0
    for name, data in sorted_groups:
        rev = data["revenue"]
        cogs = data["cogs"]
        margin = rev - cogs
        pct = (margin / rev * 100) if rev > 0 else 0
        grand_revenue += rev
        grand_cogs += cogs

        display_name = name[:28] if len(name) > 28 else name
        lines.append(f"{display_name:<30} {fmt(rev):>12} {fmt(cogs):>12} {fmt(margin):>12} {pct:>7.1f}% {data['count']:>6}")

    grand_margin = grand_revenue - grand_cogs
    grand_pct = (grand_margin / grand_revenue * 100) if grand_revenue > 0 else 0
    lines.extend([
        f"{'-'*80}",
        f"{'TOTAL':<30} {fmt(grand_revenue):>12} {fmt(grand_cogs):>12} {fmt(grand_margin):>12} {grand_pct:>7.1f}%",
    ])

    _audit_log("PROFIT_MARGIN", f"group={group_by} period={start_date}/{end_date} revenue={fmt(grand_revenue)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Budget vs Actual
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_budget_vs_actual(fiscal_year: str = "2025") -> str:
    """Compare budgeted amounts vs actual spending for a fiscal year.
    Requires budgets to be set up in QuickBooks. Shows variance by account
    and highlights over/under-budget items. fiscal_year in YYYY format."""
    start = f"{fiscal_year}-01-01"
    end = f"{fiscal_year}-12-31"

    # Try to get budgets
    budget_result = await qb_query("SELECT * FROM Budget MAXRESULTS 10")
    budgets = budget_result.get("QueryResponse", {}).get("Budget", [])

    if not budgets:
        return (
            f"No budgets found in QuickBooks.\n\n"
            f"To use this tool, create a budget in QuickBooks:\n"
            f"  1. Go to Settings > Budgeting\n"
            f"  2. Create a budget for fiscal year {fiscal_year}\n"
            f"  3. Enter budget amounts by account/month\n"
            f"  4. Run this tool again"
        )

    # Get actual P&L
    params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
    pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    # Get Budget Summary report
    budget_params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
    try:
        bva_result = await qb_request("GET", "reports/BudgetVsActual", params=budget_params)
    except Exception:
        # Fall back to manual comparison
        bva_result = None

    if bva_result and bva_result.get("Rows"):
        # Parse the QB Budget vs Actual report
        rows = bva_result.get("Rows", {}).get("Row", [])
        lines = [
            f"## Budget vs Actual — {fiscal_year}",
            f"**Period:** {start} to {end}\n",
        ]
        _parse_report_rows(rows, lines)
        _audit_log("BUDGET_VS_ACTUAL", f"year={fiscal_year}")
        return "\n".join(lines)

    # Manual fallback: compare budget entity to P&L
    budget = budgets[0]
    budget_lines_data = budget.get("BudgetDetail", [])

    from collections import defaultdict
    budget_by_acct = defaultdict(float)
    for bd in budget_lines_data:
        acct_name = bd.get("AccountRef", {}).get("name", "?")
        amount = float(bd.get("Amount", 0))
        budget_by_acct[acct_name] += amount

    # Get actual account balances
    actual_by_acct = {}
    accts_result = await qb_query_all("SELECT * FROM Account MAXRESULTS 200")
    for a in accts_result.get("QueryResponse", {}).get("Account", []):
        actual_by_acct[a["Name"]] = float(a.get("CurrentBalance", 0))

    lines = [
        f"## Budget vs Actual — {fiscal_year}",
        f"**Budget:** {budget.get('Name', 'Default')}",
        f"**Period:** {start} to {end}\n",
        f"{'Account':<35} {'Budget':>12} {'Actual':>12} {'Variance':>12} {'%':>8}",
        f"{'-'*80}",
    ]

    total_budget = 0.0
    total_actual = 0.0
    over_budget = []

    for acct, budg_amt in sorted(budget_by_acct.items()):
        act_amt = abs(actual_by_acct.get(acct, 0))
        variance = budg_amt - act_amt
        pct = (act_amt / budg_amt * 100) if budg_amt > 0 else 0
        total_budget += budg_amt
        total_actual += act_amt

        flag = " ⚠️" if act_amt > budg_amt * 1.1 else ""
        if act_amt > budg_amt * 1.1:
            over_budget.append((acct, budg_amt, act_amt, variance))

        display_name = acct[:33] if len(acct) > 33 else acct
        lines.append(f"{display_name:<35} {fmt(budg_amt):>12} {fmt(act_amt):>12} {fmt(variance):>12} {pct:>7.1f}%{flag}")

    total_variance = total_budget - total_actual
    lines.extend([
        f"{'-'*80}",
        f"{'TOTAL':<35} {fmt(total_budget):>12} {fmt(total_actual):>12} {fmt(total_variance):>12}",
    ])

    if over_budget:
        lines.append(f"\n### ⚠️ Over Budget ({len(over_budget)} accounts)")
        for acct, b, a, v in over_budget:
            lines.append(f"  - {acct}: {fmt(a)} actual vs {fmt(b)} budget ({fmt(abs(v))} over)")

    _audit_log("BUDGET_VS_ACTUAL", f"year={fiscal_year} budget={fmt(total_budget)} actual={fmt(total_actual)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Estimate to Invoice Conversion
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_list_estimates(start_date: str = "", end_date: str = "", customer_name: str = "", status: str = "", max_results: int = 50) -> str:
    """List estimates/quotes. Optionally filter by date range, customer, or status.
    status: Pending, Accepted, Closed, Rejected (leave empty for all).
    start_date/end_date in YYYY-MM-DD format."""
    query = "SELECT * FROM Estimate"
    conditions = []

    if start_date:
        start_date = _validate_date(start_date, "start_date")
        conditions.append(f"TxnDate >= '{start_date}'")
    if end_date:
        end_date = _validate_date(end_date, "end_date")
        conditions.append(f"TxnDate <= '{end_date}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    estimates = result.get("QueryResponse", {}).get("Estimate", [])

    if not estimates:
        return "No estimates found."

    # Filter by customer and status in-memory (QB query limitations)
    if customer_name:
        customer_name = _sanitize_input(customer_name, "customer_name").lower()
        estimates = [e for e in estimates if customer_name in e.get("CustomerRef", {}).get("name", "").lower()]
    if status:
        status = _sanitize_input(status, "status")
        estimates = [e for e in estimates if e.get("TxnStatus", "").lower() == status.lower()]

    lines = [f"## Estimates ({len(estimates)} found)\n"]
    total = 0.0
    for est in estimates:
        est_id = est.get("Id", "?")
        date = est.get("TxnDate", "?")
        cust = est.get("CustomerRef", {}).get("name", "?")
        amount = float(est.get("TotalAmt", 0))
        est_status = est.get("TxnStatus", "?")
        doc_num = est.get("DocNumber", "")
        expiry = est.get("ExpirationDate", "")
        total += amount

        lines.append(f"**#{doc_num or est_id}** | {date} | {cust} | {fmt(amount)} | {est_status}")
        if expiry:
            lines.append(f"  Expires: {expiry}")
        line_count = len([l for l in est.get("Line", []) if l.get("DetailType") != "SubTotalLineDetail"])
        lines.append(f"  Line items: {line_count}")
        lines.append("")

    lines.append(f"---\n**Total:** {fmt(total)}")
    lines.append(f"\nUse qb_convert_estimate_to_invoice to convert an accepted estimate.")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_convert_estimate_to_invoice(estimate_id: str) -> str:
    """Convert an estimate/quote into an invoice. Copies all line items, customer,
    and details from the estimate. estimate_id: the estimate's ID."""
    estimate_id = _sanitize_input(estimate_id, "estimate_id")

    # Read the estimate
    est_data = await qb_read("Estimate", estimate_id)
    estimate = est_data.get("Estimate", {})
    if not estimate:
        return f"Estimate #{estimate_id} not found."

    customer_ref = estimate.get("CustomerRef", {})
    if not customer_ref:
        return "Estimate has no customer reference."

    # Build invoice from estimate lines
    invoice_lines = []
    for line in estimate.get("Line", []):
        detail_type = line.get("DetailType", "")
        if detail_type == "SubTotalLineDetail":
            continue
        invoice_lines.append({
            "Amount": line.get("Amount", 0),
            "Description": line.get("Description", ""),
            "DetailType": detail_type,
        })
        # Copy the detail object
        if detail_type == "SalesItemLineDetail":
            invoice_lines[-1]["SalesItemLineDetail"] = line.get("SalesItemLineDetail", {})
        elif detail_type == "GroupLineDetail":
            invoice_lines[-1]["GroupLineDetail"] = line.get("GroupLineDetail", {})

    body = {
        "CustomerRef": customer_ref,
        "Line": invoice_lines,
        "PrivateNote": f"Converted from Estimate #{estimate.get('DocNumber', estimate_id)}",
    }

    # Copy optional fields
    if estimate.get("BillEmail"):
        body["BillEmail"] = estimate["BillEmail"]
    if estimate.get("ShipAddr"):
        body["ShipAddr"] = estimate["ShipAddr"]
    if estimate.get("BillAddr"):
        body["BillAddr"] = estimate["BillAddr"]

    result = await qb_request("POST", "invoice", json_body=body)
    invoice = result.get("Invoice", {})

    _audit_log("ESTIMATE_TO_INVOICE", f"estimate={estimate_id} invoice={invoice.get('Id')}")

    return (
        f"✅ Invoice created from Estimate #{estimate.get('DocNumber', estimate_id)}\n"
        f"  Invoice ID: {invoice.get('Id')}\n"
        f"  Invoice #: {invoice.get('DocNumber', 'auto')}\n"
        f"  Customer: {customer_ref.get('name', '?')}\n"
        f"  Amount: {fmt(float(invoice.get('TotalAmt', 0)))}\n"
        f"  Date: {invoice.get('TxnDate', 'today')}\n\n"
        f"*The original estimate remains unchanged. Update its status manually if needed.*"
    )


# ===================================================================
# BOOKS HEALTH AUDIT
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_books_health_audit(tax_year: str = "2025") -> str:
    """Run a comprehensive health audit on your QuickBooks books.
    Checks for: unknown vendors, uncategorized transactions, potential duplicates,
    undeposited funds, open invoices/bills, equity account cleanup, and more.
    Returns a scored report (0-100) with actionable items for your accountant.
    tax_year: YYYY format."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"
    issues = []
    warnings = []
    passed = []
    score = 100  # start perfect, deduct for issues

    # --- 1. Unknown/missing vendor transactions (split active vs deleted accounts) ---
    purchases = (await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )).get("QueryResponse", {}).get("Purchase", [])

    # Build active account lookup
    all_accounts_raw = (await qb_query_all(
        "SELECT Id, Name, Active FROM Account MAXRESULTS 500"
    )).get("QueryResponse", {}).get("Account", [])
    active_account_ids = {a["Id"] for a in all_accounts_raw if a.get("Active", True)}

    active_unknown = []
    deleted_unknown = []
    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "")
        if not vendor or vendor.lower() in ("unknown", ""):
            txn_info = {
                "id": p.get("Id"),
                "date": p.get("TxnDate"),
                "amount": float(p.get("TotalAmt", 0)),
                "memo": (p.get("PrivateNote", "") or p.get("Memo", "") or "")[:60],
                "account": p.get("AccountRef", {}).get("name", "?"),
            }
            acct_id = p.get("AccountRef", {}).get("value", "")
            if acct_id in active_account_ids:
                active_unknown.append(txn_info)
            else:
                deleted_unknown.append(txn_info)

    if active_unknown:
        deduction = min(25, len(active_unknown) // 10 + 5)
        score -= deduction
        issues.append(
            f"🔴 **{len(active_unknown)} transactions with unknown vendors (active accounts)**\n"
            f"   These need vendor names assigned for proper 1099 tracking and expense reporting.\n"
            f"   Largest: {fmt(max(t['amount'] for t in active_unknown))} | "
            f"Total: {fmt(sum(t['amount'] for t in active_unknown))}\n"
            f"   → Use `qb_unknown_vendor_report` then `qb_bulk_update_vendor` to fix."
        )
    else:
        passed.append("✅ All active-account transactions have vendor names assigned")

    if deleted_unknown:
        # Don't penalize score for deleted-account issues — they can't be fixed
        warnings.append(
            f"🟡 **{len(deleted_unknown)} unknown-vendor transactions on deleted/inactive accounts**\n"
            f"   These cannot be updated via API (QB limitation). Total: {fmt(sum(t['amount'] for t in deleted_unknown))}\n"
            f"   Your accountant can safely ignore these."
        )

    # --- 2. Uncategorized transactions ---
    all_accounts = (await qb_query_all(
        "SELECT * FROM Account MAXRESULTS 200"
    )).get("QueryResponse", {}).get("Account", [])
    # Merge with raw account data if needed
    if not all_accounts:
        all_accounts = all_accounts_raw

    uncat_accounts = [a for a in all_accounts
                      if "uncategorized" in a.get("Name", "").lower()]
    uncat_with_balance = [a for a in uncat_accounts
                         if abs(float(a.get("CurrentBalance", 0))) > 0.01]

    if uncat_with_balance:
        total_uncat = sum(abs(float(a.get("CurrentBalance", 0))) for a in uncat_with_balance)
        score -= min(20, int(total_uncat / 500) + 5)
        issues.append(
            f"🔴 **{len(uncat_with_balance)} uncategorized accounts with balances** "
            f"(total: {fmt(total_uncat)})\n"
            + "\n".join(f"   • {a['Name']}: {fmt(abs(float(a.get('CurrentBalance', 0))))}"
                        for a in uncat_with_balance)
            + "\n   → Use `qb_uncategorized_transactions` then `qb_reclassify_transaction` to fix."
        )
    else:
        passed.append("✅ No uncategorized account balances")

    # --- 3. Undeposited funds check ---
    undeposited = [a for a in all_accounts
                   if "undeposited" in a.get("Name", "").lower()
                   and abs(float(a.get("CurrentBalance", 0))) > 0.01]
    if undeposited:
        total_ud = sum(abs(float(a.get("CurrentBalance", 0))) for a in undeposited)
        score -= 5
        warnings.append(
            f"🟡 **Undeposited Funds balance: {fmt(total_ud)}**\n"
            f"   Payments received but not yet deposited. Record bank deposits to clear."
        )
    else:
        passed.append("✅ Undeposited Funds account is clear")

    # --- 4. Open/overdue invoices ---
    invoices = (await qb_query_all(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 500"
    )).get("QueryResponse", {}).get("Invoice", [])

    unpaid = [i for i in invoices if float(i.get("Balance", 0)) > 0]
    if unpaid:
        total_ar = sum(float(i.get("Balance", 0)) for i in unpaid)
        warnings.append(
            f"🟡 **{len(unpaid)} unpaid invoices** totaling {fmt(total_ar)}\n"
            f"   Ensure these are collected or written off before closing the year."
        )
    else:
        passed.append("✅ No unpaid invoices")

    # --- 5. Open bills (AP) ---
    bills = (await qb_query_all(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 500"
    )).get("QueryResponse", {}).get("Bill", [])

    unpaid_bills = [b for b in bills if float(b.get("Balance", 0)) > 0]
    if unpaid_bills:
        total_ap = sum(float(b.get("Balance", 0)) for b in unpaid_bills)
        warnings.append(
            f"🟡 **{len(unpaid_bills)} unpaid bills** totaling {fmt(total_ap)}\n"
            f"   Verify these are real obligations or void if duplicates."
        )
    else:
        passed.append("✅ No unpaid bills")

    # --- 6. Equity account review (owner transactions) ---
    equity_accounts = [a for a in all_accounts
                       if a.get("AccountType", "").lower() == "equity"
                       and abs(float(a.get("CurrentBalance", 0))) > 0.01]
    if equity_accounts:
        equity_detail = "\n".join(
            f"   • {a['Name']}: {fmt(float(a.get('CurrentBalance', 0)))}"
            for a in equity_accounts
        )
        total_equity = sum(float(a.get("CurrentBalance", 0)) for a in equity_accounts)
        if any("opening balance" in a.get("Name", "").lower() for a in equity_accounts):
            score -= 5
            warnings.append(
                f"🟡 **Opening Balance Equity has a balance** — should be zero after setup.\n"
                f"   Reclassify to Owner's Equity or retained earnings.\n{equity_detail}"
            )
        else:
            passed.append(f"✅ Equity accounts look clean ({len(equity_accounts)} accounts, net {fmt(total_equity)})")
    else:
        passed.append("✅ No equity accounts with balances")

    # --- 7. Potential duplicates (quick check) ---
    from collections import defaultdict
    txn_fingerprints = defaultdict(list)
    for p in purchases:
        key = (p.get("TxnDate", ""), str(round(float(p.get("TotalAmt", 0)), 2)))
        txn_fingerprints[key].append(p.get("Id"))

    dupes = {k: v for k, v in txn_fingerprints.items() if len(v) > 1}
    dupe_count = sum(len(v) - 1 for v in dupes.values())
    if dupe_count > 5:
        score -= min(10, dupe_count)
        warnings.append(
            f"🟡 **{dupe_count} potential duplicate transactions** "
            f"({len(dupes)} date/amount combinations)\n"
            f"   → Use `qb_find_duplicates` for detailed review."
        )
    else:
        passed.append("✅ No significant duplicate patterns detected")

    # --- 8. Missing tax info (1099 readiness) ---
    vendors = (await qb_query_all(
        "SELECT * FROM Vendor MAXRESULTS 200"
    )).get("QueryResponse", {}).get("Vendor", [])

    vendors_no_tin = [v for v in vendors
                      if not v.get("TaxIdentifier")
                      and v.get("Vendor1099", False)]
    if vendors_no_tin:
        score -= 3
        warnings.append(
            f"🟡 **{len(vendors_no_tin)} 1099 vendors missing TIN**\n"
            f"   → Collect W-9s from: "
            + ", ".join(v.get("DisplayName", "?") for v in vendors_no_tin[:5])
        )
    else:
        passed.append("✅ All 1099 vendors have TINs (or no vendors marked as 1099)")

    # --- Score and report ---
    score = max(0, score)
    if score >= 90:
        grade = "🟢 EXCELLENT"
    elif score >= 70:
        grade = "🟡 NEEDS ATTENTION"
    elif score >= 50:
        grade = "🟠 SIGNIFICANT ISSUES"
    else:
        grade = "🔴 CRITICAL — DO NOT SEND TO ACCOUNTANT"

    lines = [
        f"## Books Health Audit — {tax_year}",
        f"### Score: {score}/100 {grade}\n",
    ]

    if issues:
        lines.append("### Critical Issues")
        lines.extend(issues)
        lines.append("")

    if warnings:
        lines.append("### Warnings")
        lines.extend(warnings)
        lines.append("")

    if passed:
        lines.append("### Passed Checks")
        lines.extend(passed)
        lines.append("")

    lines.append(f"\n**Summary:** {len(issues)} critical issues, {len(warnings)} warnings, {len(passed)} passed checks.")
    lines.append(f"*Fix all critical issues before sending books to your accountant.*")

    _audit_log("BOOKS_HEALTH_AUDIT", f"year={tax_year} score={score} issues={len(issues)} warnings={len(warnings)}")
    return "\n".join(lines)


# ===================================================================
# UNKNOWN VENDOR REPORT & BULK FIX
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_unknown_vendor_report(start_date: str = "", end_date: str = "", max_results: int = 200) -> str:
    """Find all transactions with unknown or missing vendor names.
    Groups by memo/description pattern to help identify bulk fixes.
    Separates fixable (active account) from unfixable (deleted account) transactions.
    Returns transaction IDs for use with qb_bulk_update_vendor.
    start_date/end_date in YYYY-MM-DD (defaults to all time)."""
    query = "SELECT * FROM Purchase"
    conditions = []
    if start_date:
        start_date = _validate_date(start_date, "start_date")
        conditions.append(f"TxnDate >= '{start_date}'")
    if end_date:
        end_date = _validate_date(end_date, "end_date")
        conditions.append(f"TxnDate <= '{end_date}'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" MAXRESULTS {max_results}"

    purchases = (await qb_query(query)).get("QueryResponse", {}).get("Purchase", [])

    # Build active account lookup
    all_accounts = (await qb_query_all(
        "SELECT Id, Name, Active FROM Account MAXRESULTS 500"
    )).get("QueryResponse", {}).get("Account", [])
    active_account_ids = {a["Id"] for a in all_accounts if a.get("Active", True)}

    # Filter to unknown vendors, tag with active/deleted account status
    active_unknown = []
    deleted_unknown = []
    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "")
        if not vendor or vendor.lower() in ("unknown", ""):
            line_cats = []
            for line in p.get("Line", []):
                detail = line.get("AccountBasedExpenseLineDetail", {})
                acct = detail.get("AccountRef", {}).get("name", "")
                if acct:
                    line_cats.append(acct)

            acct_id = p.get("AccountRef", {}).get("value", "")
            acct_name = p.get("AccountRef", {}).get("name", "?")
            is_active = acct_id in active_account_ids

            txn_data = {
                "id": p.get("Id"),
                "date": p.get("TxnDate", "?"),
                "amount": float(p.get("TotalAmt", 0)),
                "memo": p.get("PrivateNote", "") or p.get("Memo", "") or "",
                "account": acct_name,
                "account_id": acct_id,
                "account_active": is_active,
                "categories": ", ".join(line_cats) if line_cats else "?",
                "payment_type": p.get("PaymentType", "?"),
            }

            if is_active:
                active_unknown.append(txn_data)
            else:
                deleted_unknown.append(txn_data)

    total_unknown = len(active_unknown) + len(deleted_unknown)
    if total_unknown == 0:
        return "✅ No transactions with unknown vendors found."

    from collections import defaultdict

    lines = [
        f"## Unknown Vendor Report",
        f"**Total:** {total_unknown} transactions with unknown/missing vendors",
        f"**Fixable (active accounts):** {len(active_unknown)}",
        f"**Unfixable (deleted accounts):** {len(deleted_unknown)} ⚠️",
        f"**Total Amount:** {fmt(sum(t['amount'] for t in active_unknown + deleted_unknown))}\n",
    ]

    # === Active account transactions (fixable) ===
    if active_unknown:
        memo_groups = defaultdict(list)
        for t in active_unknown:
            memo = t["memo"].strip() or f"[No memo — {t['categories']}]"
            key = memo[:80] if len(memo) > 80 else memo
            memo_groups[key].append(t)

        sorted_groups = sorted(memo_groups.items(),
                               key=lambda x: sum(t["amount"] for t in x[1]),
                               reverse=True)

        lines.append(f"### ✅ Fixable Transactions ({len(active_unknown)} on active accounts)\n")

        for memo, txns in sorted_groups[:30]:
            total = sum(t["amount"] for t in txns)
            lines.append(f"**\"{memo}\"** — {len(txns)} txn(s), total {fmt(total)}")
            lines.append(f"  Account: {txns[0]['account']} | Categories: {txns[0]['categories']}")
            ids = [t["id"] for t in txns]
            if len(ids) <= 5:
                lines.append(f"  IDs: {', '.join(ids)}")
            else:
                lines.append(f"  IDs: {', '.join(ids[:5])} ... +{len(ids)-5} more")
            lines.append(f"  Date range: {txns[0]['date']} to {txns[-1]['date']}")
            lines.append("")

        lines.append("**To fix:** Use `qb_bulk_update_vendor` with the IDs and the correct vendor name.\n")

    # === Deleted account transactions (unfixable via API) ===
    if deleted_unknown:
        # Group by account name
        acct_groups = defaultdict(list)
        for t in deleted_unknown:
            acct_groups[t["account"]].append(t)

        lines.append(f"### ⚠️ Unfixable Transactions ({len(deleted_unknown)} on deleted/inactive accounts)\n")
        lines.append("These transactions are on deleted accounts and **cannot be updated via API**.")
        lines.append("Your accountant can safely ignore these.\n")

        for acct_name, txns in sorted(acct_groups.items(), key=lambda x: len(x[1]), reverse=True):
            total = sum(t["amount"] for t in txns)
            lines.append(f"  **{acct_name}**: {len(txns)} txns, total {fmt(total)}")

    _audit_log("UNKNOWN_VENDOR_REPORT", f"found={total_unknown} active={len(active_unknown)} deleted={len(deleted_unknown)}")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_bulk_update_vendor(transaction_ids: str, vendor_name: str) -> str:
    """Bulk-assign a vendor name to multiple transactions.
    transaction_ids: comma-separated Purchase IDs (e.g., '123,456,789').
    vendor_name: display name of the vendor to assign. Must exist in QB already
    (use qb_create_vendor first if needed)."""
    ids = [i.strip() for i in transaction_ids.split(",") if i.strip()]
    if not ids:
        return "Error: No transaction IDs provided."
    if not vendor_name.strip():
        return "Error: vendor_name is required."

    # Look up the vendor to get the ID
    vendors = (await qb_query(
        f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name.replace(chr(39), '')}' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        # Try partial match
        vendors = (await qb_query(
            f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name.replace(chr(39), '')}%' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        return (f"Error: Vendor '{vendor_name}' not found in QuickBooks. "
                f"Create it first with `qb_create_vendor`.")

    vendor = vendors[0]
    vendor_ref = {"value": vendor["Id"], "name": vendor.get("DisplayName", vendor_name)}

    success = 0
    errors = []

    for txn_id in ids:
        try:
            # Read current transaction
            current = await qb_read("purchase", txn_id)
            purchase = current.get("Purchase", current)
            if not purchase.get("Id"):
                errors.append(f"ID {txn_id}: not found")
                continue

            # Update vendor
            purchase["EntityRef"] = vendor_ref
            result = await qb_request("POST", "purchase", json_body=purchase)
            if result.get("Purchase", {}).get("Id"):
                success += 1
            else:
                errors.append(f"ID {txn_id}: update failed")
        except Exception as e:
            errors.append(f"ID {txn_id}: {str(e)[:60]}")

    lines = [
        f"## Bulk Vendor Update Results",
        f"**Vendor:** {vendor_name}",
        f"**Attempted:** {len(ids)} transactions",
        f"**Succeeded:** {success}",
    ]
    if errors:
        lines.append(f"**Failed:** {len(errors)}")
        for e in errors[:10]:
            lines.append(f"  • {e}")

    _audit_log("BULK_UPDATE_VENDOR", f"vendor={vendor_name} success={success}/{len(ids)}")
    return "\n".join(lines)


@mcp.tool(annotations={"destructiveHint": True})
async def qb_bulk_update_vendors_multi(vendor_mapping: str) -> str:
    """Bulk-assign MULTIPLE vendors to transactions in one call.
    vendor_mapping: JSON string mapping vendor names to transaction ID lists.
    Example: '{"Supabase": ["123","456"], "Anthropic": ["789","012"]}'
    All vendors must exist in QB already (use qb_create_vendor first if needed)."""
    try:
        mapping = json.loads(vendor_mapping)
    except (json.JSONDecodeError, TypeError):
        return "Error: vendor_mapping must be valid JSON. Example: {\"Vendor\": [\"id1\",\"id2\"]}"

    if not isinstance(mapping, dict):
        return "Error: vendor_mapping must be a JSON object mapping vendor names to ID arrays."

    total_success = 0
    total_errors = []
    results_by_vendor = {}

    for vendor_name, txn_ids in mapping.items():
        if not isinstance(txn_ids, list):
            total_errors.append(f"{vendor_name}: IDs must be an array")
            continue

        # Look up vendor
        safe_name = vendor_name.replace("'", "")
        vendors = (await qb_query(
            f"SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Vendor", [])

        if not vendors:
            vendors = (await qb_query(
                f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
            )).get("QueryResponse", {}).get("Vendor", [])

        if not vendors:
            total_errors.append(f"{vendor_name}: vendor not found in QB")
            results_by_vendor[vendor_name] = {"success": 0, "failed": len(txn_ids), "error": "vendor not found"}
            continue

        vendor = vendors[0]
        vendor_ref = {"value": vendor["Id"], "name": vendor.get("DisplayName", vendor_name)}
        v_success = 0
        v_errors = []

        for txn_id in txn_ids:
            txn_id = str(txn_id).strip()
            try:
                current = await qb_read("purchase", txn_id)
                purchase = current.get("Purchase", current)
                if not purchase.get("Id"):
                    v_errors.append(f"ID {txn_id}: not found")
                    continue
                purchase["EntityRef"] = vendor_ref
                result = await qb_request("POST", "purchase", json_body=purchase)
                if result.get("Purchase", {}).get("Id"):
                    v_success += 1
                else:
                    v_errors.append(f"ID {txn_id}: update failed")
            except Exception as e:
                v_errors.append(f"ID {txn_id}: {str(e)[:60]}")

        total_success += v_success
        total_errors.extend(v_errors)
        results_by_vendor[vendor_name] = {"success": v_success, "failed": len(v_errors)}

    lines = [
        f"## Multi-Vendor Bulk Update Results",
        f"**Vendors processed:** {len(mapping)}",
        f"**Total succeeded:** {total_success}",
        f"**Total failed:** {len(total_errors)}\n",
    ]

    for vname, vresult in results_by_vendor.items():
        status = "✅" if vresult.get("failed", 0) == 0 else "⚠️"
        lines.append(f"  {status} **{vname}**: {vresult['success']} updated" +
                      (f", {vresult['failed']} failed" if vresult.get("failed", 0) > 0 else ""))

    if total_errors:
        lines.append(f"\n### Errors")
        for e in total_errors[:20]:
            lines.append(f"  • {e}")

    _audit_log("BULK_UPDATE_VENDORS_MULTI", f"vendors={len(mapping)} success={total_success} errors={len(total_errors)}")
    return "\n".join(lines)


# ===================================================================
# MONTH-END CLOSE WORKFLOW
# ===================================================================

@mcp.tool(annotations={"readOnlyHint": True})
async def qb_month_end_close(year: int = 2025, month: int = 12) -> str:
    """Run a month-end close checklist for a specific month.
    Checks: all transactions categorized, vendors assigned, accounts reconciled,
    no orphaned items, and provides a close readiness score.
    year: YYYY, month: 1-12."""
    from calendar import monthrange

    month = max(1, min(12, month))
    _, last_day = monthrange(year, month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    month_name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1]

    checklist = []
    blockers = 0
    warnings_count = 0

    # --- 1. Transaction volume ---
    purchases = (await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )).get("QueryResponse", {}).get("Purchase", [])

    deposits = (await qb_query_all(
        f"SELECT * FROM Deposit WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 500"
    )).get("QueryResponse", {}).get("Deposit", [])

    journals = (await qb_query_all(
        f"SELECT * FROM JournalEntry WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 500"
    )).get("QueryResponse", {}).get("JournalEntry", [])

    total_txns = len(purchases) + len(deposits) + len(journals)
    checklist.append(f"📊 **Transaction Volume:** {total_txns} total "
                     f"({len(purchases)} purchases, {len(deposits)} deposits, {len(journals)} journal entries)")

    # --- 2. Unknown vendors ---
    unknown_vendors = [p for p in purchases
                       if not p.get("EntityRef", {}).get("name")]
    if unknown_vendors:
        blockers += 1
        checklist.append(
            f"🔴 **{len(unknown_vendors)} purchases missing vendor** — "
            f"total {fmt(sum(float(p.get('TotalAmt', 0)) for p in unknown_vendors))}\n"
            f"   → Run `qb_unknown_vendor_report` to identify and fix."
        )
    else:
        checklist.append("✅ All purchases have vendors assigned")

    # --- 3. Uncategorized amounts ---
    all_accounts = (await qb_query_all(
        "SELECT * FROM Account MAXRESULTS 200"
    )).get("QueryResponse", {}).get("Account", [])

    uncat = [a for a in all_accounts
             if "uncategorized" in a.get("Name", "").lower()
             and abs(float(a.get("CurrentBalance", 0))) > 0.01]
    if uncat:
        total_uncat = sum(abs(float(a.get("CurrentBalance", 0))) for a in uncat)
        blockers += 1
        checklist.append(
            f"🔴 **Uncategorized balances: {fmt(total_uncat)}**\n"
            f"   → Run `qb_uncategorized_transactions` to find and reclassify."
        )
    else:
        checklist.append("✅ No uncategorized balances")

    # --- 4. P&L for the month ---
    try:
        pl_params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
        pl = await qb_request("GET", "reports/ProfitAndLoss", params=pl_params)
        pl_rows = pl.get("Rows", {}).get("Row", [])
        month_income = 0.0
        month_expenses = 0.0
        for row in pl_rows:
            if row.get("type") != "Section":
                continue
            header = row.get("Header", {})
            label = header.get("ColData", [{}])[0].get("value", "").lower().strip()
            summary = row.get("Summary", {}).get("ColData", [])
            if summary and len(summary) > 1:
                val_str = summary[-1].get("value", "0").replace(",", "")
                try:
                    val = float(val_str)
                except ValueError:
                    val = 0
                if label in ("income", "other income"):
                    month_income += val
                elif label in ("expenses", "other expenses"):
                    month_expenses += abs(val)

        net = month_income - month_expenses
        checklist.append(
            f"📊 **P&L Summary:** Income {fmt(month_income)} | "
            f"Expenses {fmt(month_expenses)} | Net {fmt(net)}"
        )
    except Exception:
        checklist.append("⚠️ Could not generate P&L for this month")

    # --- 5. Duplicate check ---
    from collections import defaultdict
    fingerprints = defaultdict(list)
    for p in purchases:
        key = (p.get("TxnDate", ""), str(round(float(p.get("TotalAmt", 0)), 2)))
        fingerprints[key].append(p.get("Id"))

    dupes = {k: v for k, v in fingerprints.items() if len(v) > 1}
    dupe_count = sum(len(v) - 1 for v in dupes.values())
    if dupe_count > 3:
        warnings_count += 1
        checklist.append(
            f"🟡 **{dupe_count} potential duplicates** — "
            f"review with `qb_find_duplicates`"
        )
    else:
        checklist.append("✅ No significant duplicates detected")

    # --- 6. Large/unusual transactions ---
    amounts = [float(p.get("TotalAmt", 0)) for p in purchases if float(p.get("TotalAmt", 0)) > 0]
    if amounts:
        import statistics
        mean_amt = statistics.mean(amounts)
        std_amt = statistics.stdev(amounts) if len(amounts) > 1 else mean_amt
        threshold = mean_amt + 2.5 * std_amt
        large = [p for p in purchases if float(p.get("TotalAmt", 0)) > threshold]
        if large:
            warnings_count += 1
            checklist.append(
                f"🟡 **{len(large)} unusually large transactions** (>{fmt(threshold)})\n"
                f"   Largest: {fmt(max(float(p.get('TotalAmt', 0)) for p in large))} — verify these are correct."
            )
        else:
            checklist.append("✅ No unusual transaction amounts")

    # --- 7. Bank account reconciliation hint ---
    bank_accounts = [a for a in all_accounts if a.get("AccountType") == "Bank"]
    if bank_accounts:
        bank_info = ", ".join(
            f"{a['Name']}: {fmt(float(a.get('CurrentBalance', 0)))}"
            for a in bank_accounts[:5]
        )
        checklist.append(
            f"📊 **Bank Balances:** {bank_info}\n"
            f"   → Verify these match your bank statements for {month_name} {year}."
        )

    # --- Close readiness ---
    if blockers == 0 and warnings_count == 0:
        status = "🟢 READY TO CLOSE"
    elif blockers == 0:
        status = "🟡 CLOSE WITH CAUTION"
    else:
        status = f"🔴 NOT READY — {blockers} blocking issue(s)"

    lines = [
        f"## Month-End Close: {month_name} {year}",
        f"### Status: {status}\n",
        "### Checklist\n",
    ] + checklist + [
        "",
        f"---",
        f"**Blockers:** {blockers} | **Warnings:** {warnings_count}",
    ]

    if blockers > 0:
        lines.append(f"\n*Resolve all 🔴 items before closing the month.*")
    else:
        lines.append(f"\n*Month looks clean. Review 🟡 warnings and confirm bank reconciliation.*")

    _audit_log("MONTH_END_CLOSE", f"{month_name} {year} blockers={blockers} warnings={warnings_count}")
    return "\n".join(lines)


# ===================================================================
# NEW: Delete Transaction (generalized)
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_delete_transaction(entity_type: str, entity_id: str, confirm: bool = False) -> str:
    """Delete a transaction permanently. Supports: Purchase, Deposit, Transfer,
    JournalEntry, Bill, BillPayment, Invoice, Payment, SalesReceipt, CreditMemo, VendorCredit.
    entity_type: QB entity type. entity_id: the transaction ID.
    confirm: must be True to execute deletion.
    ⚠️ This is PERMANENT. Use qb_void_transaction to void instead when possible."""
    entity_type = _sanitize_input(entity_type, "entity_type")
    entity_id = _sanitize_input(entity_id, "entity_id")

    # Normalize entity type
    type_map = {
        "purchase": "Purchase", "deposit": "Deposit", "transfer": "Transfer",
        "journalentry": "JournalEntry", "bill": "Bill", "billpayment": "BillPayment",
        "invoice": "Invoice", "payment": "Payment", "salesreceipt": "SalesReceipt",
        "creditmemo": "CreditMemo", "vendorcredit": "VendorCredit",
    }
    normalized = type_map.get(entity_type.lower().replace(" ", ""), entity_type)

    if not confirm:
        try:
            txn = await qb_read(normalized.lower(), entity_id)
            entity = txn.get(normalized, txn)
            memo = entity.get("PrivateNote", "") or entity.get("Memo", "") or "(no memo)"
            date = entity.get("TxnDate", "?")
            total = entity.get("TotalAmt", 0)
            vendor = entity.get("EntityRef", {}).get("name", "")

            return (
                f"⚠️ **Confirm Deletion**\n"
                f"  {normalized} #{entity_id} | {date} | {fmt(float(total))}\n"
                f"  {'Vendor: ' + vendor + ' | ' if vendor else ''}Memo: {str(memo)[:100]}\n\n"
                f"To delete, call again with confirm=True.\n"
                f"Consider using qb_void_transaction instead (keeps audit trail)."
            )
        except Exception as e:
            return f"Error reading {normalized} #{entity_id}: {str(e)[:100]}"

    _audit_log("DELETE_TXN_START", f"type={normalized} id={entity_id}")

    # Read to get SyncToken
    try:
        txn = await qb_read(normalized.lower(), entity_id)
        entity = txn.get(normalized, txn)
        if not entity.get("Id"):
            return f"{normalized} #{entity_id} not found."

        delete_body = {"Id": entity_id, "SyncToken": entity["SyncToken"]}
        endpoint = normalized.lower() + "?operation=delete"
        await qb_request("POST", endpoint, json_body=delete_body)

        _audit_log("DELETE_TXN_DONE", f"type={normalized} id={entity_id}")
        return f"✅ {normalized} #{entity_id} permanently deleted."
    except Exception as e:
        return f"Error deleting {normalized} #{entity_id}: {str(e)[:100]}"


# ===================================================================
# NEW: Update Vendor / Update Customer
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_update_vendor(vendor_name: str, email: str = "", phone: str = "",
                           company_name: str = "", display_name: str = "",
                           vendor_1099: bool = False, tax_id: str = "") -> str:
    """Update an existing vendor's details.
    vendor_name: current display name to find the vendor.
    Provide any fields to update: email, phone, company_name, display_name, vendor_1099, tax_id."""
    safe_name = vendor_name.replace("'", "")
    vendors = (await qb_query(
        f"SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        vendors = (await qb_query(
            f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        return f"Error: Vendor '{vendor_name}' not found."
    if len(vendors) > 1:
        names = ", ".join(f"{v['DisplayName']} (ID:{v['Id']})" for v in vendors)
        return f"Multiple vendors match: {names}. Please be more specific."

    vendor = vendors[0]
    updates = {}

    if email:
        updates["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        updates["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        updates["CompanyName"] = company_name
    if display_name:
        updates["DisplayName"] = display_name
    if vendor_1099:
        updates["Vendor1099"] = True
    if tax_id:
        updates["TaxIdentifier"] = tax_id

    if not updates:
        return f"No updates provided for vendor '{vendor_name}'."

    vendor.update(updates)
    result = await qb_request("POST", "vendor", json_body=vendor)
    updated = result.get("Vendor", {})

    if updated.get("Id"):
        fields_changed = ", ".join(updates.keys())
        _audit_log("UPDATE_VENDOR", f"id={updated['Id']} name={updated.get('DisplayName', '')} fields={fields_changed}")
        return f"✅ Vendor '{updated.get('DisplayName', vendor_name)}' (ID: {updated['Id']}) updated. Changed: {fields_changed}"
    return "Error: Update failed. Check the vendor name and try again."


@mcp.tool(annotations={"destructiveHint": True})
async def qb_update_customer(customer_name: str, email: str = "", phone: str = "",
                             company_name: str = "", display_name: str = "") -> str:
    """Update an existing customer's details.
    customer_name: current display name to find the customer.
    Provide any fields to update: email, phone, company_name, display_name."""
    safe_name = customer_name.replace("'", "")
    customers = (await qb_query(
        f"SELECT * FROM Customer WHERE DisplayName = '{safe_name}' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Customer", [])

    if not customers:
        customers = (await qb_query(
            f"SELECT * FROM Customer WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Customer", [])

    if not customers:
        return f"Error: Customer '{customer_name}' not found."
    if len(customers) > 1:
        names = ", ".join(f"{c['DisplayName']} (ID:{c['Id']})" for c in customers)
        return f"Multiple customers match: {names}. Please be more specific."

    customer = customers[0]
    updates = {}

    if email:
        updates["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        updates["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        updates["CompanyName"] = company_name
    if display_name:
        updates["DisplayName"] = display_name

    if not updates:
        return f"No updates provided for customer '{customer_name}'."

    customer.update(updates)
    result = await qb_request("POST", "customer", json_body=customer)
    updated = result.get("Customer", {})

    if updated.get("Id"):
        fields_changed = ", ".join(updates.keys())
        _audit_log("UPDATE_CUSTOMER", f"id={updated['Id']} name={updated.get('DisplayName', '')} fields={fields_changed}")
        return f"✅ Customer '{updated.get('DisplayName', customer_name)}' (ID: {updated['Id']}) updated. Changed: {fields_changed}"
    return "Error: Update failed. Check the customer name and try again."


# ===================================================================
# NEW: Record Bill Payment / Invoice Payment
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_record_bill_payment(vendor_name: str, amount: float, bill_id: str = "",
                                  payment_account: str = "", date: str = "", memo: str = "") -> str:
    """Record a payment against a vendor bill (accounts payable).
    vendor_name: vendor who issued the bill. amount: payment amount.
    bill_id: specific bill ID to pay (optional — will find unpaid bills if omitted).
    payment_account: bank/CC account paying from (defaults to first bank account).
    date: YYYY-MM-DD (defaults to today). memo: optional note."""
    amount = _validate_amount(amount, "amount")
    if date:
        date = _validate_date(date, "date")
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # Find vendor
    safe_name = vendor_name.replace("'", "")
    vendors = (await qb_query(
        f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return f"Error: Vendor '{vendor_name}' not found."
    vendor = vendors[0]

    # Find payment account
    if payment_account:
        safe_acct = payment_account.replace("'", "")
        accts = (await qb_query(
            f"SELECT * FROM Account WHERE Name LIKE '%{safe_acct}%' AND AccountType IN ('Bank', 'Credit Card') MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Account", [])
    else:
        accts = (await qb_query(
            "SELECT * FROM Account WHERE AccountType = 'Bank' AND Active = true MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Account", [])

    if not accts:
        return "Error: No payment account found. Specify payment_account parameter."
    pay_acct = accts[0]

    # Find bill to pay
    if bill_id:
        bill_data = await qb_read("bill", bill_id)
        bill = bill_data.get("Bill", {})
        if not bill.get("Id"):
            return f"Error: Bill #{bill_id} not found."
    else:
        # Find unpaid bills for this vendor
        bills = (await qb_query(
            f"SELECT * FROM Bill WHERE VendorRef = '{vendor['Id']}' AND Balance > '0' MAXRESULTS 10"
        )).get("QueryResponse", {}).get("Bill", [])
        if not bills:
            return f"No unpaid bills found for vendor '{vendor_name}'."
        bill = bills[0]  # Pay the oldest unpaid bill

    bill_payment = {
        "VendorRef": {"value": vendor["Id"], "name": vendor.get("DisplayName", "")},
        "TotalAmt": amount,
        "PayType": "Check",
        "CheckPayment": {
            "BankAccountRef": {"value": pay_acct["Id"], "name": pay_acct.get("Name", "")}
        },
        "TxnDate": date,
        "Line": [{
            "Amount": amount,
            "LinkedTxn": [{"TxnId": bill["Id"], "TxnType": "Bill"}]
        }],
    }
    if memo:
        bill_payment["PrivateNote"] = memo

    result = await qb_request("POST", "billpayment", json_body=bill_payment)
    bp = result.get("BillPayment", {})

    if bp.get("Id"):
        _audit_log("RECORD_BILL_PAYMENT", f"id={bp['Id']} vendor={vendor_name} amount={amount} bill={bill['Id']}")
        return (
            f"✅ Bill payment recorded\n"
            f"  **Payment ID:** {bp['Id']} | **Amount:** {fmt(amount)}\n"
            f"  **Vendor:** {vendor_name} | **Bill:** #{bill['Id']}\n"
            f"  **From:** {pay_acct.get('Name', '?')} | **Date:** {date}"
        )
    return "Error: Bill payment creation failed."


@mcp.tool(annotations={"destructiveHint": True})
async def qb_record_invoice_payment(customer_name: str, amount: float, invoice_id: str = "",
                                     deposit_account: str = "", date: str = "",
                                     payment_method: str = "", memo: str = "") -> str:
    """Record a customer payment against an invoice (accounts receivable).
    customer_name: customer making payment. amount: payment amount.
    invoice_id: specific invoice ID (optional — will find unpaid invoices if omitted).
    deposit_account: bank account to deposit to (defaults to Undeposited Funds).
    date: YYYY-MM-DD (defaults to today). payment_method: Cash, Check, CreditCard, etc."""
    amount = _validate_amount(amount, "amount")
    if date:
        date = _validate_date(date, "date")
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # Find customer
    safe_name = customer_name.replace("'", "")
    customers = (await qb_query(
        f"SELECT * FROM Customer WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Customer", [])
    if not customers:
        return f"Error: Customer '{customer_name}' not found."
    customer = customers[0]

    # Find invoice to apply payment
    if invoice_id:
        inv_data = await qb_read("invoice", invoice_id)
        invoice = inv_data.get("Invoice", {})
        if not invoice.get("Id"):
            return f"Error: Invoice #{invoice_id} not found."
    else:
        invoices = (await qb_query(
            f"SELECT * FROM Invoice WHERE CustomerRef = '{customer['Id']}' AND Balance > '0' MAXRESULTS 10"
        )).get("QueryResponse", {}).get("Invoice", [])
        if not invoices:
            return f"No unpaid invoices found for customer '{customer_name}'."
        invoice = invoices[0]

    payment = {
        "CustomerRef": {"value": customer["Id"], "name": customer.get("DisplayName", "")},
        "TotalAmt": amount,
        "TxnDate": date,
        "Line": [{
            "Amount": amount,
            "LinkedTxn": [{"TxnId": invoice["Id"], "TxnType": "Invoice"}]
        }],
    }

    if deposit_account:
        safe_acct = deposit_account.replace("'", "")
        accts = (await qb_query(
            f"SELECT * FROM Account WHERE Name LIKE '%{safe_acct}%' AND AccountType = 'Bank' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("Account", [])
        if accts:
            payment["DepositToAccountRef"] = {"value": accts[0]["Id"], "name": accts[0].get("Name", "")}

    if payment_method:
        # Look up payment method
        pm_result = (await qb_query(
            f"SELECT * FROM PaymentMethod WHERE Name LIKE '%{payment_method}%' MAXRESULTS 5"
        )).get("QueryResponse", {}).get("PaymentMethod", [])
        if pm_result:
            payment["PaymentMethodRef"] = {"value": pm_result[0]["Id"], "name": pm_result[0].get("Name", "")}

    if memo:
        payment["PrivateNote"] = memo

    result = await qb_request("POST", "payment", json_body=payment)
    pmt = result.get("Payment", {})

    if pmt.get("Id"):
        _audit_log("RECORD_INVOICE_PAYMENT", f"id={pmt['Id']} customer={customer_name} amount={amount} invoice={invoice['Id']}")
        return (
            f"✅ Invoice payment recorded\n"
            f"  **Payment ID:** {pmt['Id']} | **Amount:** {fmt(amount)}\n"
            f"  **Customer:** {customer_name} | **Invoice:** #{invoice['Id']}\n"
            f"  **Date:** {date}"
        )
    return "Error: Payment creation failed."


# ===================================================================
# NEW: Create Estimate
# ===================================================================

@mcp.tool(annotations={"destructiveHint": True})
async def qb_create_estimate(customer_name: str, line_items: str, expiration_date: str = "",
                              memo: str = "", tax_code: str = "", tax_inclusive: bool = False) -> str:
    """Create a customer estimate/quote.
    customer_name: customer to quote. line_items: JSON string array
    [{"description": "Consulting", "amount": 5000}]. expiration_date: YYYY-MM-DD (optional).
    memo: internal note.
    Canada/global editions: tax_code applies a sales tax code to all lines, e.g. 'HST ON'; per-line override via 'tax_code' key in line_items JSON; tax_inclusive=True when amounts already include tax."""
    # Find customer
    safe_name = customer_name.replace("'", "")
    customers = (await qb_query(
        f"SELECT * FROM Customer WHERE DisplayName LIKE '%{safe_name}%' MAXRESULTS 5"
    )).get("QueryResponse", {}).get("Customer", [])
    if not customers:
        return f"Error: Customer '{customer_name}' not found. Create them first with qb_create_customer."
    customer = customers[0]

    try:
        items = json.loads(line_items)
    except (json.JSONDecodeError, TypeError):
        return "Error: line_items must be valid JSON array. Example: [{\"description\": \"Service\", \"amount\": 100}]"

    if not isinstance(items, list) or not items:
        return "Error: line_items must be a non-empty array."

    region = (await _get_region())["region"]
    default_tax_id = None
    tax_cache: dict = {}
    if region != "US" and tax_code:
        try:
            default_tax_id, _ = await _resolve_tax_code(tax_code)
        except ValueError as e:
            return str(e)

    lines = []
    total = 0.0
    for i, item in enumerate(items):
        amt = float(item.get("amount", 0))
        total += amt
        line = {
            "DetailType": "SalesItemLineDetail",
            "Amount": amt,
            "Description": item.get("description", f"Line item {i+1}"),
            "SalesItemLineDetail": {
                "UnitPrice": amt,
                "Qty": 1,
            }
        }
        try:
            line_tax = await _line_tax_code_ref(item, region, tax_cache)
        except ValueError as e:
            return str(e)
        if line_tax:
            line["SalesItemLineDetail"]["TaxCodeRef"] = line_tax
        lines.append(line)

    if region != "US" and not default_tax_id and not any(
        "TaxCodeRef" in l["SalesItemLineDetail"] for l in lines
    ):
        return _TAX_CODE_REQUIRED_MSG

    estimate = {
        "CustomerRef": {"value": customer["Id"], "name": customer.get("DisplayName", "")},
        "Line": lines,
        "TxnDate": datetime.now().strftime("%Y-%m-%d"),
    }

    if expiration_date:
        estimate["ExpirationDate"] = _validate_date(expiration_date, "expiration_date")
    if memo:
        estimate["PrivateNote"] = memo
    _apply_global_tax(estimate, "Line", "SalesItemLineDetail",
                      default_tax_id, tax_inclusive, region)

    result = await qb_request("POST", "estimate", json_body=estimate)
    est = result.get("Estimate", {})

    if est.get("Id"):
        _audit_log("CREATE_ESTIMATE", f"id={est['Id']} customer={customer_name} total={total}")
        return (
            f"✅ Estimate created\n"
            f"  **Estimate ID:** {est['Id']} | **Total:** {fmt(total)}\n"
            f"  **Customer:** {customer_name}\n"
            f"  **Line items:** {len(lines)}\n"
            f"  **Status:** Pending\n"
            f"  → Convert to invoice with `qb_convert_estimate_to_invoice` when accepted."
        )
    return "Error: Estimate creation failed."


# ===================================================================
# CANADA TAX SUITE — GST/HST, T2125, CCA, T4A, CRA INSTALMENTS
# ===================================================================
# Canadian counterparts to the US tax tools above (qb_schedule_c,
# qb_estimate_quarterly_tax, qb_depreciation_schedule,
# qb_1099_contractor_report). All amounts render in home currency (CAD).
# Sources for the constants below:
# - GST34 return lines (CRA): 101 total sales & revenue; 103/105 GST/HST
#   collected + adjustments; 106/108 input tax credits (ITCs);
#   109 net tax = line 105 - line 108.
# - ITA s.67.1: only 50% of the GST/HST on meals & entertainment is
#   claimable as an ITC.
# - Quick Method eligibility: taxable supplies (tax-included) <= $400,000
#   over the prior four fiscal quarters; accountants/bookkeepers/financial
#   consultants are ineligible. Remittance rates vary (e.g. ~3.6% for
#   services in 5% GST provinces, 8.8% for Ontario services) with a 1%
#   credit on the first $30,000 of eligible supplies.
# - T2125 Part 4 expense line numbers (CRA form T2125).
# - CCA classes/rates: Schedule II, Income Tax Regulations. Accelerated
#   Investment Incentive & immediate expensing: Budget 2025 / Bill C-15 —
#   property acquired on/after Jan 1 2025 and available for use before
#   2030 gets 1.5x the first-year rate with no half-year rule (some
#   M&P/clean-energy/ZEV property gets 100% immediate expensing);
#   phase-out 2030-2033.
# - CPP/CPP2: CRA payroll tables. 2026: 5.95% each (11.9% self-employed)
#   between the $3,500 exemption and YMPE $74,600; CPP2 4% each (8%
#   self-employed) between YMPE and YAMPE $85,000. 2025: YMPE $71,300,
#   YAMPE $81,200. Self-employed pay both halves; half of base CPP is
#   deductible.
# - CRA instalments (individuals): due Mar 15 / Jun 15 / Sep 15 / Dec 15;
#   required when net tax owing > $3,000 in the current year AND either
#   of the two prior years. GST/HST annual filers owing >= $3,000 pay
#   quarterly instalments one month after each fiscal quarter end.



def _purchase_meals_split(txn: dict) -> tuple:
    """(meals_amount, other_amount) across a purchase/bill's expense lines.

    Meals/entertainment lines are detected by AccountRef name (ITA s.67.1
    restricts the ITC on these to 50%)."""
    meals = other = 0.0
    for line in txn.get("Line", []):
        try:
            amt = float(line.get("Amount", 0) or 0)
        except (ValueError, TypeError):
            amt = 0.0
        detail = line.get("AccountBasedExpenseLineDetail") or {}
        name = ((detail.get("AccountRef") or {}).get("name") or "").lower()
        if "meal" in name or "entertain" in name:
            meals += amt
        else:
            other += amt
    return meals, other


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("CA", "Use qb_sales_tax_summary / qb_schedule_c for US sales tax and income tax prep.")
async def qb_gst_hst_return(start_date: str, end_date: str, agency_name: str = "") -> str:
    """Build a GST/HST (GST34) return workpaper for a filing period.
    Computes lines 101 (sales & revenue), 103/105 (GST/HST collected),
    106/108 (input tax credits, with the 50% meals & entertainment
    restriction), and 109 (net tax) from QuickBooks transactions, and also
    pulls the QuickBooks TaxSummary report when available.
    start_date/end_date: YYYY-MM-DD filing period. agency_name: tax agency
    (defaults to the Canada Revenue Agency entry)."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    prov = (await _get_region()).get("subdivision", "")
    regime = _ca_regime(prov)

    lines = [
        f"## GST/HST Return Workpaper (GST34)",
        f"**Filing period:** {start_date} to {end_date}",
    ]
    if regime:
        lines.append(f"**Province:** {_ca_regime_describe(prov)}")
    lines.append("")

    # ---- Resolve the tax agency for the reports/TaxSummary endpoint ----
    try:
        agencies = (await qb_query_all("SELECT * FROM TaxAgency MAXRESULTS 1000")) \
            .get("QueryResponse", {}).get("TaxAgency", [])
    except Exception as e:
        logger.debug(f"TaxAgency query failed: {e}")
        agencies = []

    provincial_agencies = [a for a in agencies
                           if _ca_agency_is_provincial(a.get("DisplayName") or "")]
    pst_name = (regime or {}).get("pst_name", "PST/QST")

    agency = None
    if agency_name:
        wanted = agency_name.lower()
        matches = [a for a in agencies if wanted in (a.get("DisplayName") or "").lower()]
        if not matches:
            names = ", ".join(a.get("DisplayName", "?") for a in agencies) or "(none)"
            return f"Tax agency '{agency_name}' not found. Available agencies: {names}"
        agency = matches[0]
    elif len(agencies) == 1 and not provincial_agencies:
        agency = agencies[0]
    else:
        cra = [a for a in agencies
               if any(k in (a.get("DisplayName") or "").lower()
                      for k in ("canada revenue", "cra", "receiver general"))]
        if cra:
            agency = cra[0]
        elif agencies:
            names = ", ".join(a.get("DisplayName", "?") for a in agencies)
            lines.append(f"*Multiple tax agencies found ({names}) — pass agency_name= "
                         f"to pull the QuickBooks TaxSummary report for one of them.*\n")

    for pa in provincial_agencies:
        lines.append(
            f"⚠️ {pst_name} amounts owed to {pa.get('DisplayName', '?')} are filed "
            f"separately with that agency — they do not belong on your GST34.\n"
        )

    # ---- QuickBooks TaxSummary report (non-US editions only) ----
    if agency is not None:
        try:
            rep = await qb_request("GET", "reports/TaxSummary", params={
                "start_date": start_date, "end_date": end_date,
                "agency_id": agency.get("Id"),
            })
            rep_rows = rep.get("Rows", {}).get("Row", [])
            if rep_rows:
                lines.append(f"### QuickBooks TaxSummary report — {agency.get('DisplayName', '?')}")
                _parse_report_rows(rep_rows, lines)
                lines.append("")
        except Exception as e:
            logger.debug(f"reports/TaxSummary failed: {e}")
            lines.append("*QuickBooks TaxSummary report unavailable for this "
                         "period/agency — using transaction-derived figures below.*\n")

    # ---- Transaction-derived workpaper (always computed) ----
    line_101 = 0.0  # sales & revenue (net of GST/HST)
    line_103 = 0.0  # GST/HST collected (TxnTaxDetail.TotalTax on sales docs)
    sales_count = 0
    for entity in ("Invoice", "SalesReceipt"):
        result = await qb_query_all(
            f"SELECT * FROM {entity} WHERE TxnDate >= '{start_date}' "
            f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
        )
        for txn in result.get("QueryResponse", {}).get(entity, []):
            total = float(txn.get("TotalAmt", 0) or 0)
            tax = float((txn.get("TxnTaxDetail") or {}).get("TotalTax", 0) or 0)
            line_101 += total - tax
            line_103 += tax
            sales_count += 1

    line_106 = 0.0        # ITCs (tax on purchases, after meals restriction)
    meals_restricted = 0.0  # disallowed half of meals & entertainment GST/HST
    purchase_count = 0
    for entity in ("Purchase", "Bill"):
        result = await qb_query_all(
            f"SELECT * FROM {entity} WHERE TxnDate >= '{start_date}' "
            f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
        )
        for txn in result.get("QueryResponse", {}).get(entity, []):
            tax = float((txn.get("TxnTaxDetail") or {}).get("TotalTax", 0) or 0)
            if tax == 0:
                continue
            purchase_count += 1
            meals, other = _purchase_meals_split(txn)
            if meals > 0 and (meals + other) > 0:
                # ITA s.67.1: only 50% of GST/HST on the meals portion is claimable
                claimable = tax * ((other + _MEALS_ITC_FACTOR * meals) / (meals + other))
                meals_restricted += tax - claimable
            else:
                claimable = tax
            line_106 += claimable

    line_105 = line_103  # 103 + adjustments (104) — none derived here
    line_108 = line_106  # 106 + adjustments (107) — none derived here
    line_109 = line_105 - line_108

    lines.append("### Transaction-derived return lines")
    lines.append(f"  Line 101 — Sales and other revenue (net of GST/HST): {fmt(line_101)}")
    lines.append(f"  Line 103 — GST/HST collected or collectible: {fmt(line_103)}")
    lines.append(f"  Line 105 — Total GST/HST and adjustments: {fmt(line_105)}")
    lines.append(f"  Line 106 — Input tax credits (ITCs): {fmt(line_106)}")
    lines.append(f"  Line 108 — Total ITCs and adjustments: {fmt(line_108)}")
    lines.append(f"  **Line 109 — Net tax (105 − 108): {fmt(line_109)}**")
    lines.append(f"\n  Derived from {sales_count} sales documents and "
                 f"{purchase_count} taxed purchase documents.")
    if meals_restricted > 0:
        lines.append(f"  Meals & entertainment ITC restriction applied (50% of "
                     f"GST/HST disallowed): {fmt(meals_restricted)} excluded from line 106.")

    if regime and regime["regime"] in ("GST_PST", "GST_QST"):
        lines.append(
            f"\n⚠️ Transaction-derived line 103 sums each document's TotalTax, "
            f"which includes {regime['pst_name']} — only the GST portion belongs "
            f"on the GST34. Use the CRA-agency TaxSummary report figures above "
            f"for filing."
        )
    elif regime and sales_count >= 3 and line_101 > 0:
        expected = regime["hst"] if regime["regime"] == "HST" else regime["gst"]
        effective = line_103 / line_101
        if abs(effective - expected) > 0.2 * expected:
            label = "HST" if regime["regime"] == "HST" else "GST"
            lines.append(
                f"\n⚠️ Collected tax averages {effective * 100:.1f}% of sales but "
                f"{prov} {label} is {expected * 100:g}% — check the tax codes on "
                f"your sales documents (run qb_list_tax_codes)."
            )

    # ---- Tax payments recorded against filed returns ----
    # Filed returns aren't exposed by the API; TaxPayment (CA/AU/UK) records
    # payments against them.
    tax_payments = []
    try:
        tp_result = await qb_query_all("SELECT * FROM TaxPayment MAXRESULTS 300")
        for tp in tp_result.get("QueryResponse", {}).get("TaxPayment", []):
            pay_date = tp.get("PaymentDate") or tp.get("TxnDate") or ""
            if start_date <= pay_date <= end_date:
                tax_payments.append(tp)
    except Exception as e:
        logger.debug(f"TaxPayment query failed: {e}")

    if tax_payments:
        lines.append("\n### Tax payments in period")
        for tp in tax_payments:
            amt = tp.get("PaymentAmount", tp.get("TotalAmt", 0))
            date = tp.get("PaymentDate") or tp.get("TxnDate") or "?"
            refund = " (refund)" if tp.get("Refund") else ""
            lines.append(f"  - {date}: {fmt(float(amt or 0))}{refund}")

    # ---- Quick Method eligibility note ----
    lines.append("\n### Quick Method note")
    if line_101 + line_103 <= _GST_QUICK_METHOD_LIMIT:
        lines.append(
            f"  Taxable supplies in this period ({fmt(line_101 + line_103)} tax-included) are "
            f"within the {fmt(_GST_QUICK_METHOD_LIMIT)} Quick Method limit (measured over the "
            f"prior four fiscal quarters) — you may be eligible to elect the Quick Method "
            f"(e.g. ~3.6% remittance for services in 5% GST provinces, 8.8% for Ontario "
            f"services, with a 1% credit on the first {fmt(_GST_QUICK_METHOD_CREDIT_BASE)} of "
            f"supplies). Accountants, bookkeepers, and financial consultants are ineligible."
        )
    else:
        lines.append(
            f"  Taxable supplies exceed the {fmt(_GST_QUICK_METHOD_LIMIT)} Quick Method "
            f"eligibility limit — regular method applies."
        )

    if regime and regime["regime"] == "GST_QST":
        lines.append(
            "\n*Québec: the GST is administered by Revenu Québec — file the "
            "combined GST/QST return (FPZ-500). The line mapping above still "
            "applies to the GST portion.*"
        )

    lines.append(f"\n---\n⚠️ {_GST_WORKPAPER_FOOTER}")
    _audit_log("GST_HST_RETURN", f"period={start_date}/{end_date} net_tax={fmt(line_109)}")
    return "\n".join(lines) + tax_data_footer()


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("CA", "Use qb_schedule_c / qb_schedule_c_detailed for the IRS Schedule C.")
async def qb_t2125_summary(year: int = 0) -> str:
    """Generate a CRA T2125 (Statement of Business or Professional Activities)
    line-by-line mapping for a tax year. Maps QuickBooks expense accounts to
    T2125 Part 4 lines (8521 Advertising, 8523 Meals at 50%, 8910 Rent, ...)
    the way qb_schedule_c maps to Schedule C. year: e.g. 2025 (default: current year)."""
    from datetime import date as _date
    year = int(year) or _date.today().year
    start = f"{year}-01-01"
    end = f"{year}-12-31"

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end,
        "summarize_column_by": "Total",
    })

    # Parse P&L rows into account -> amount (same shape as qb_schedule_c)
    def extract_expenses(rows, result_dict):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    result_dict[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_expenses(nested, result_dict)

    expense_dict = {}
    total_income = 0.0
    report_rows = result.get("Rows", {}).get("Row", [])
    for section in report_rows:
        header = section.get("Header", {}).get("ColData", [{}])
        if header and "expense" in header[0].get("value", "").lower():
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_expenses(nested, expense_dict)
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val

    # Map expense accounts to T2125 lines by keyword
    from collections import defaultdict
    t_lines = defaultdict(lambda: {"amount": 0.0, "accounts": []})
    unmapped = []
    for acct_name, amount in expense_dict.items():
        amount = abs(amount)
        if amount == 0:
            continue
        mapped = False
        for keyword, (line_no, desc) in _T2125_LINE_MAP.items():
            if keyword in acct_name.lower():
                key = f"Line {line_no} — {desc}"
                deductible = amount * 0.5 if line_no == "8523" else amount
                t_lines[key]["amount"] += deductible
                note = f" (50% of {fmt(amount)})" if line_no == "8523" else ""
                t_lines[key]["accounts"].append(f"{acct_name}: {fmt(deductible)}{note}")
                mapped = True
                break
        if not mapped:
            key = "Line 9270 — Other expenses (unmapped — review)"
            t_lines[key]["amount"] += amount
            t_lines[key]["accounts"].append(f"{acct_name}: {fmt(amount)}")
            unmapped.append(acct_name)

    lines = [f"## CRA T2125 — Statement of Business Activities — {year}\n"]
    lines.append("### Income")
    lines.append(f"  Line 8000 — Gross sales, commissions or fees: {fmt(total_income)}")
    lines.append(f"  Line 8299 — Gross business income: {fmt(total_income)}")
    lines.append(
        "  *GST/HST registrants: report revenue net of GST/HST collected "
        "(QuickBooks sales figures above exclude tax when tax codes are used).*\n"
    )

    lines.append("### Part 4 — Expenses")
    total_expenses = 0.0
    for key in sorted(t_lines.keys()):
        data = t_lines[key]
        lines.append(f"\n**{key}: {fmt(data['amount'])}**")
        for acct in data["accounts"]:
            lines.append(f"  - {acct}")
        total_expenses += data["amount"]

    lines.append(
        "\n**Line 9936 — Capital cost allowance (CCA):** not computed here — "
        "run qb_cca_schedule for the class-by-class UCC schedule."
    )
    lines.append(
        "**Line 9945 — Business-use-of-home:** compute separately — must be your "
        "principal place of business OR used exclusively and regularly to meet "
        "clients; prorate by area; cannot create or increase a loss (excess "
        "carries forward)."
    )

    net = total_income - total_expenses
    lines.append(f"\n**Line 9368 — Total expenses: {fmt(total_expenses)}**")
    lines.append(f"**Line 9369 — Net income (loss) before adjustments: {fmt(net)}**")

    if unmapped:
        lines.append(f"\n*Unmapped accounts placed on line 9270 — review: "
                     f"{', '.join(unmapped)}*")

    lines.extend([
        "\n### Filing deadlines",
        "  - T1 return (self-employed): June 15",
        "  - Balance owing due: April 30",
        "  - Meals & entertainment: only 50% deductible (line 8523, ITA s.67.1)",
        "\n*Workpaper only — verify mappings with your accountant before filing.*",
    ])

    _audit_log("T2125_SUMMARY", f"year={year} income={fmt(total_income)} expenses={fmt(total_expenses)}")
    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("CA", "Use qb_depreciation_schedule for Section 179 / MACRS.")
async def qb_cca_schedule(assets_json: str = "", year: int = 0) -> str:
    """Compute a Capital Cost Allowance (CCA) schedule by class (T2125 Area A).
    Declining-balance CCA with the half-year rule, Accelerated Investment
    Incentive (1.5x first-year rate, no half-year, for property acquired on or
    after Jan 1 2025), and the Class 10.1 / Class 54 cost ceilings.
    assets_json: JSON array [{"name": "MacBook", "cost": 3000, "class": "50",
    "acquired": "YYYY-MM-DD", "ucc_opening": 1200 (optional)}].
    Call with no arguments first to list fixed-asset accounts as candidates.
    year: CCA claim year (defaults to the current year)."""
    if not year:
        year = datetime.now().year

    if not assets_json.strip():
        # Pull fixed-asset accounts as candidates (mirrors qb_depreciation_schedule)
        result = await qb_query_all(
            "SELECT * FROM Account WHERE AccountType = 'Fixed Asset' MAXRESULTS 200"
        )
        acct_list = result.get("QueryResponse", {}).get("Account", [])
        lines = [f"## CCA Schedule — {year} (setup)\n"]
        if acct_list:
            lines.append("Fixed-asset accounts found in QuickBooks (candidates):")
            for a in acct_list:
                bal = float(a.get("CurrentBalance", 0) or 0)
                lines.append(f"  - {a.get('Name', '?')}: {fmt(bal)}")
        else:
            lines.append("No fixed-asset accounts found in QuickBooks.")
        lines.append(
            "\nQuickBooks doesn't track CCA class or acquisition dates, so pass "
            "assets_json to compute the schedule, e.g.:\n"
            '`[{"name": "MacBook Pro", "cost": 3000, "class": "50", '
            '"acquired": "2026-02-01"}, {"name": "Car", "cost": 45000, '
            '"class": "10.1", "acquired": "2025-06-15"}]`\n'
            "Optional `ucc_opening` overrides the opening UCC for assets "
            "acquired in earlier years.\n\n### CCA classes"
        )
        for cls, (rate, desc) in _CCA_CLASSES.items():
            lines.append(f"  - Class {cls} ({rate * 100:g}%): {desc}")
        return "\n".join(lines)

    try:
        assets = json.loads(assets_json)
        assert isinstance(assets, list) and assets
    except (json.JSONDecodeError, AssertionError):
        return ('Error: assets_json must be a non-empty JSON array like '
                '[{"name": "MacBook", "cost": 3000, "class": "50", '
                '"acquired": "2026-02-01"}]')

    from collections import defaultdict
    by_class = defaultdict(list)
    for a in assets:
        cls = str(a.get("class", "")).strip()
        if cls not in _CCA_CLASSES:
            return (f"Error: unknown CCA class '{cls}'. Supported classes: "
                    f"{', '.join(_CCA_CLASSES)}")
        by_class[cls].append(a)

    lines = [f"## CCA Schedule — {year}\n"]
    lines.append("| Class | Asset | Cost (capped) | Opening UCC | CCA {0} | Closing UCC |".format(year))
    lines.append("|---|---|---|---|---|---|")

    total_cca = 0.0
    ceiling_notes = []
    for cls in sorted(by_class, key=float):
        rate, _desc = _CCA_CLASSES[cls]
        for a in by_class[cls]:
            name = a.get("name", "?")
            try:
                cost = float(a.get("cost", 0))
                acq_year = int(str(a.get("acquired", ""))[:4])
            except (ValueError, TypeError):
                return f"Error: asset '{name}' needs numeric cost and acquired=YYYY-MM-DD."
            if acq_year > year:
                continue

            # Cost ceilings (full 2001+ acquisition-year history in the registry)
            capped_cost = cost
            if cls == "10.1":
                try:
                    ceiling, _c_note = tax_value_or_latest("CLASS_10_1_CEILING", acq_year)
                except TaxDataError as e:
                    return str(e)
                if _c_note:
                    ceiling_notes.append(_c_note)
                if cost > ceiling:
                    capped_cost = ceiling
                    ceiling_notes.append(
                        f"{name}: Class 10.1 cost capped at {fmt(ceiling)} "
                        f"({acq_year} ceiling, plus GST/HST/PST on that amount).")
            elif cls == "54" and cost > _CLASS_54_ZEV_CEILING:
                capped_cost = _CLASS_54_ZEV_CEILING
                ceiling_notes.append(
                    f"{name}: Class 54 ZEV cost capped at {fmt(_CLASS_54_ZEV_CEILING)}.")

            # UCC simulation from acquisition year to the claim year.
            # Year 1: AII (1.5x rate, no half-year) for property acquired on or
            # after Jan 1 2025 (and available for use before 2030); otherwise
            # the half-year rule (half the net addition gets the rate).
            if a.get("ucc_opening") is not None:
                opening = float(a["ucc_opening"])
                cca = opening * rate
            else:
                ucc = capped_cost
                cca = 0.0
                opening = capped_cost
                for y in range(acq_year, year + 1):
                    opening = ucc
                    if y == acq_year:
                        if acq_year >= _AII_START_YEAR:
                            cca = ucc * rate * _AII_FIRST_YEAR_FACTOR
                        else:
                            cca = ucc * rate * 0.5  # half-year rule
                        cca = min(cca, ucc)
                    else:
                        cca = ucc * rate
                    ucc -= cca
            closing = opening - cca
            total_cca += cca

            lines.append(
                f"| {cls} ({rate * 100:g}%) | {name} | {fmt(capped_cost)} | "
                f"{fmt(opening)} | {fmt(cca)} | {fmt(closing)} |"
            )

    lines.append(f"\n**Total CCA claim (line 9936): {fmt(total_cca)}**")
    if ceiling_notes:
        lines.append("")
        for n in ceiling_notes:
            lines.append(f"  - {n}")

    lines.extend([
        "\n### Rules applied",
        f"  - Half-year rule: half the net addition gets the class rate in year 1 "
        f"(pre-{_AII_START_YEAR} acquisitions).",
        f"  - Accelerated Investment Incentive (Budget 2025 / Bill C-15): property "
        f"acquired on/after Jan 1 {_AII_START_YEAR} and available for use before 2030 "
        f"gets {_AII_FIRST_YEAR_FACTOR}x the first-year rate with no half-year rule; "
        f"phase-out 2030-2033.",
        "  - Class 10.1: no terminal loss; half-year CCA allowed in the year of sale.",
        "\n*Verify with your accountant — 100% immediate expensing may apply to "
        "eligible manufacturing & processing, clean-energy, and zero-emission "
        "vehicle property.*",
    ])

    _audit_log("CCA_SCHEDULE", f"year={year} assets={len(assets)} cca={fmt(total_cca)}")
    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("CA", "Use qb_1099_contractor_report for IRS 1099-NEC prep.")
async def qb_t4a_contractor_report(year: int) -> str:
    """Generate T4A (box 048 — fees for services) contractor reporting data for
    a calendar year. Lists vendors paid for services, flags missing business
    numbers (BN) and addresses, and notes the T5018 regime for construction.
    year: calendar year, e.g. 2025."""
    start = f"{year}-01-01"
    end = f"{year}-12-31"

    vendor_result = await qb_query_all("SELECT * FROM Vendor MAXRESULTS 500")
    vendors = vendor_result.get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return "No vendors found."

    purchase_result = await qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    purchases = purchase_result.get("QueryResponse", {}).get("Purchase", [])

    bill_result = await qb_query_all(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    bills = bill_result.get("QueryResponse", {}).get("Bill", [])

    vendor_map = {}
    for v in vendors:
        vid = v.get("Id", "")
        addr = v.get("BillAddr", {})
        parts = [addr.get("Line1", ""), addr.get("City", ""),
                 addr.get("CountrySubDivisionCode", ""), addr.get("PostalCode", "")]
        vendor_map[vid] = {
            "name": v.get("DisplayName", "?"),
            "company": v.get("CompanyName", ""),
            "bn": v.get("TaxIdentifier", ""),
            "email": v.get("PrimaryEmailAddr", {}).get("Address", ""),
            "address": ", ".join(p for p in parts if p),
            "total_paid": 0.0,
            "payment_count": 0,
        }

    for p in purchases:
        vid = p.get("EntityRef", {}).get("value", "")
        if vid in vendor_map:
            vendor_map[vid]["total_paid"] += float(p.get("TotalAmt", 0) or 0)
            vendor_map[vid]["payment_count"] += 1

    for b in bills:
        vid = b.get("VendorRef", {}).get("value", "")
        if vid in vendor_map:
            vendor_map[vid]["total_paid"] += float(b.get("TotalAmt", 0) or 0)
            vendor_map[vid]["payment_count"] += 1

    reportable = [v for v in vendor_map.values() if v["total_paid"] >= _T4A_ADMIN_THRESHOLD]
    below = [v for v in vendor_map.values() if 0 < v["total_paid"] < _T4A_ADMIN_THRESHOLD]
    reportable.sort(key=lambda x: x["total_paid"], reverse=True)

    lines = [
        f"## T4A Contractor Report (box 048 — fees for services) — {year}",
        f"**Threshold shown:** {fmt(_T4A_ADMIN_THRESHOLD)} (no legislated minimum for "
        f"box 048 — the {fmt(_T4A_ADMIN_THRESHOLD)} cutoff is common CRA administrative practice)",
        f"**Vendors at/above threshold:** {len(reportable)}\n",
    ]

    grand_total = 0.0
    missing_bn = missing_addr = 0
    for i, v in enumerate(reportable, 1):
        grand_total += v["total_paid"]
        if not v["bn"]:
            missing_bn += 1
        if not v["address"]:
            missing_addr += 1
        lines.append(f"### {i}. {v['name']}")
        lines.append(f"  **Total Paid:** {fmt(v['total_paid'])} ({v['payment_count']} payments)")
        lines.append(f"  **BN/SIN Status:** {'✅ On file' if v['bn'] else '⚠️ MISSING'}")
        if v["company"]:
            lines.append(f"  **Company:** {v['company']}")
        lines.append(f"  **Address:** {v['address'] or '⚠️ MISSING — needed for the T4A slip'}")
        if v["email"]:
            lines.append(f"  **Email:** {v['email']}")
        lines.append("")

    lines.extend([
        "---",
        "### Summary",
        f"  Total reportable payments: {fmt(grand_total)}",
        f"  Vendors needing a T4A slip: {len(reportable)}",
        f"  Missing BN/SIN: {missing_bn} | Missing address: {missing_addr}",
        f"  Vendors below {fmt(_T4A_ADMIN_THRESHOLD)} (usually not slipped): {len(below)}",
        "",
        "### Filing notes",
        "  - Report fees for services in **box 048** of the T4A (amounts exclude GST/HST).",
        f"  - T4A slips and summary are due the **last day of February {year + 1}**.",
        "  - Construction businesses: file **T5018** slips instead — report ALL "
        "subcontractor payments with no minimum threshold.",
        "  - Exclude payments for goods only; box 048 covers services.",
        "\n*Verify recipient details and slip requirements with your accountant.*",
    ])

    _audit_log("T4A_REPORT", f"year={year} vendors={len(reportable)} total={fmt(grand_total)}")
    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
@require_region("CA", "Use qb_estimate_quarterly_tax for US federal/state estimates.")
async def qb_estimate_instalments(year: int = 0, province: str = "") -> str:
    """Estimate CRA tax instalments and CPP for a self-employed Canadian based
    on YTD P&L. CPP/CPP2 (2025/2026 YMPE/YAMPE) is exact; income tax uses
    approximate 2025/2026 brackets plus a flat provincial factor — a rough
    planning estimate only. province: two-letter code (ON, BC, AB, QC, ...)."""
    from datetime import date
    today = date.today()
    if not year:
        year = today.year
    province = (province or "ON").strip().upper()

    start = f"{year}-01-01"
    end = min(today.strftime("%Y-%m-%d"), f"{year}-12-31")

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end,
    })

    total_income = total_expenses = 0.0
    for section in result.get("Rows", {}).get("Row", []):
        cols = section.get("Summary", {}).get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val
            elif "expense" in label:
                total_expenses = abs(val)

    net_income = total_income - total_expenses

    # ---- CPP (exact for 2025/2026) ----
    params = _CPP_PARAMS.get(year)
    cpp_year_note = ""
    if params is None:
        params = _CPP_PARAMS[max(_CPP_PARAMS)]
        cpp_year_note = f" (using {max(_CPP_PARAMS)} ceilings — {year} not tabulated)"
    ympe, yampe = params["ympe"], params["yampe"]

    pensionable = max(0.0, net_income)
    base_cpp = max(0.0, min(pensionable, ympe) - _CPP_BASIC_EXEMPTION) * _CPP_RATE_SELF
    cpp2 = max(0.0, min(pensionable, yampe) - ympe) * _CPP2_RATE_SELF
    cpp_total = base_cpp + cpp2

    # ---- Income tax (APPROXIMATE) ----
    # Rough: deduct half of base CPP (employer share) and the basic personal
    # amount, then run approximate federal brackets + a flat provincial factor.
    taxable = max(0.0, net_income - base_cpp / 2 - _CA_BPA_APPROX)
    federal_tax = 0.0
    prev_cap = 0.0
    for cap, rate in _CA_FED_BRACKETS_APPROX:
        if taxable <= prev_cap:
            break
        federal_tax += (min(taxable, cap) - prev_cap) * rate
        prev_cap = cap

    prov_rate = _CA_PROV_FLAT_APPROX.get(province, 0.10)
    prov_tax = taxable * prov_rate

    total_annual = federal_tax + prov_tax + cpp_total
    quarterly = total_annual / 4

    lines = [f"## CRA Instalment Estimate — {year}\n"]
    lines.append(f"**YTD Net self-employment income:** {fmt(net_income)} ({start} to {end})")
    lines.append(f"**Province:** {province}\n")

    lines.append(f"### CPP (self-employed — both halves){cpp_year_note}")
    lines.append(f"  Base CPP: {fmt(base_cpp)} — 11.9% on earnings between "
                 f"{fmt(_CPP_BASIC_EXEMPTION)} and YMPE {fmt(ympe)}")
    lines.append(f"  CPP2: {fmt(cpp2)} — 8% on earnings between YMPE {fmt(ympe)} "
                 f"and YAMPE {fmt(yampe)}")
    lines.append(f"  **Total CPP: {fmt(cpp_total)}** (half of base CPP — "
                 f"{fmt(base_cpp / 2)} — is deductible)\n")

    lines.append("### Income tax (approximate 2025/2026 brackets)")
    lines.append(f"  Federal (approx.): {fmt(federal_tax)}")
    lines.append(f"  {province} provincial (flat ~{prov_rate * 100:g}%, approx.): {fmt(prov_tax)}")
    if province == "QC":
        lines.append("  *Québec: Revenu Québec collects its own tax and requires "
                     "separate provincial instalments (form TP-1026.A-V; the "
                     "federal instalment threshold is $1,800 for Québec residents); "
                     "QPP replaces CPP — QPP rates differ slightly from the CPP "
                     "shown above.*")

    lines.append(f"\n**Total estimated annual tax + CPP: {fmt(total_annual)}**")
    lines.append(f"**Each quarterly instalment: {fmt(quarterly)}**\n")

    lines.append("### Instalment schedule (individuals)")
    for due in _CRA_INSTALMENT_DATES:
        lines.append(f"  {due}, {year}: {fmt(quarterly)}")

    if total_annual > _CRA_INSTALMENT_THRESHOLD:
        lines.append(
            f"\nInstalments are required when net tax owing exceeds "
            f"{fmt(_CRA_INSTALMENT_THRESHOLD)} in the current year AND either of the "
            f"two prior years — this estimate exceeds the threshold."
        )
    else:
        lines.append(
            f"\nEstimated net tax owing is at or below {fmt(_CRA_INSTALMENT_THRESHOLD)} — "
            f"instalments likely not required (threshold applies to the current "
            f"year and either of the two prior years)."
        )

    lines.append(
        "\n### GST/HST instalments\n"
        f"  Annual GST/HST filers owing {fmt(_CRA_INSTALMENT_THRESHOLD)} or more pay "
        f"quarterly GST/HST instalments due one month after each fiscal quarter end."
    )
    lines.append(
        "\n---\n*Rough planning estimate — income tax uses approximate 2025/2026 "
        "brackets and a flat provincial factor. CPP amounts and instalment dates "
        "are exact. Confirm with CRA My Account and your accountant.*"
    )

    _audit_log("ESTIMATE_INSTALMENTS", f"year={year} net={fmt(net_income)} total={fmt(total_annual)}")
    return "\n".join(lines) + tax_data_footer(year)


@mcp.tool(annotations={"readOnlyHint": True})
async def qb_tax_data_info() -> str:
    """Show the provenance of every tax rate and threshold this server uses:
    per-table sources, verified dates, review cadence, covered years, and
    the append-only tax-data ledger status. This is the transparency layer —
    every tax tool's footer points here."""
    lines = [
        "## Tax Data Registry",
        f"**Version:** TAX_DATA v{TAX_DATA_VERSION} · verified {TAX_DATA_VERIFIED}",
        "\nEvery value below carries a source and review date; changes ship "
        "only through an append-only, hash-chained ledger reviewed by a "
        "human. Future-year requests use the latest tables with a visible "
        "note — never silently.",
    ]

    by_jur: dict = {}
    for name, entry in TABLES.items():
        by_jur.setdefault(entry["jurisdiction"], []).append((name, entry))

    for jur in sorted(by_jur):
        lines.append(f"\n### {jur}")
        for name, e in sorted(by_jur[jur]):
            years = _tt.table_year_keys(e) if e.get("year_keyed") else []
            vintage = (f"{years[0]}–{years[-1]}" if years else
                       {"stable_statute": "statutory", "approximation": "planning approx.",
                        "exact": "current"}[e["kind"]])
            lines.append(
                f"- **{e['description']}** — {vintage} · {e['kind']} · "
                f"verified {e['verified']} · review: {e['review']}\n"
                f"  Source: {e['source']}"
            )

    rows = load_ledger()
    superseded = {r["supersedes"] for r in rows if r.get("supersedes")}
    chain_ok = verify_ledger_chain(rows)
    lines.append(
        f"\n### Ledger\n"
        f"- {len(rows)} rows ({len(rows) - len(superseded)} live, "
        f"{len(superseded)} superseded)\n"
        f"- Hash chain: {'✓ verified' if chain_ok else '⚠️ FAILED VERIFICATION'}\n"
        f"- Latest entry: {max(r['verified_date'] for r in rows) if rows else 'n/a'}"
    )
    return "\n".join(lines)


# ===================================================================
# LICENSE GATING — AUTO-WRAP PAID TOOLS
# ===================================================================
# Instead of manually decorating each tool, we wrap all non-free tools
# at startup. This is cleaner and means adding a new tool automatically
# gets gated unless you add it to FREE_TOOLS.

def _apply_license_gating():
    """Wrap all registered MCP tools that aren't in FREE_TOOLS."""
    # Only gate when license infrastructure is configured
    if not LICENSE_KEY and not _LICENSE_VALIDATION_URL:
        logger.info("No license system configured — all tools unlocked (dev mode)")
        return

    gated_count = 0
    for tool_name in list(mcp._tool_manager._tools.keys()):
        if tool_name not in FREE_TOOLS:
            tool = mcp._tool_manager._tools[tool_name]
            original_fn = tool.fn
            tool.fn = require_license(original_fn)
            gated_count += 1

    logger.info(
        f"License gating active: {len(FREE_TOOLS)} free tools, "
        f"{gated_count} paid tools"
    )

def _apply_usage_tracking():
    """Wrap all registered MCP tools with usage tracking.

    Wrapping is unconditional: the effective license is resolved per call in
    the wrapper (single-tenant uses QB_LICENSE_KEY; the remote multi-tenant
    server sets ctx.license_key per request from the JWT, so the module-level
    LICENSE_KEY is empty there). The wrapper no-ops when no license is in
    effect, so dev/no-license runs still emit nothing."""
    tracked_count = 0
    for tool_name in list(mcp._tool_manager._tools.keys()):
        tool = mcp._tool_manager._tools[tool_name]
        original_fn = tool.fn
        tool.fn = track_usage(original_fn)
        tracked_count += 1

    logger.info(
        f"Usage tracking active: {tracked_count} tools wrapped "
        f"(runtime-gated on effective license)"
    )

# Apply gating and tracking after all tools are registered
_apply_license_gating()
_apply_usage_tracking()


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    mcp.run()
