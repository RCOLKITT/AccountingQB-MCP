"""Shared test setup for the AccountingQB MCP server test suite.

Environment is scrubbed BEFORE the server module is imported (module import
reads env and initializes the default QBContext), and QB_DATA_DIR is pointed
at a throwaway directory so tests never touch real cached tokens.
"""

import os
import sys
import tempfile

# --- must run before accountingqb.server is imported anywhere ---
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PKG_DIR = os.path.join(_REPO_ROOT, "mcpb", "src")
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

os.environ["QB_DATA_DIR"] = tempfile.mkdtemp(prefix="qb_test_data_")
for _var in (
    "QB_LICENSE_KEY",
    "QB_CLIENT_ID",
    "QB_CLIENT_SECRET",
    "QB_REFRESH_TOKEN",
    "QB_REALM_ID",
    "QB_API_URL",
    "QB_ENVIRONMENT",
):
    os.environ.pop(_var, None)
# -----------------------------------------------------------------

import pytest

import accountingqb.server as qb_server
from accountingqb.context import QBContext, get_ctx, set_ctx, reset_ctx


@pytest.fixture
def server():
    """The (already imported) canonical server module."""
    return qb_server


@pytest.fixture
def qb_ctx():
    """Install a fresh, non-persisting QBContext for the duration of a test."""
    ctx = QBContext(persist_tokens=False)
    token = set_ctx(ctx)
    yield ctx
    reset_ctx(token)
