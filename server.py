"""AccountingQB MCP server — repo-root shim.

The canonical server implementation lives in mcpb/src/accountingqb/server.py
(the same code that ships in the MCPB desktop extension and the PyPI
package). This shim keeps the original OSS entry point working:

    python server.py

It simply puts mcpb/src on sys.path and runs the packaged server.
"""

import os
import sys

_PKG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcpb", "src")
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from accountingqb.server import mcp  # noqa: E402


def main() -> None:
    """Console-script entry point (see [project.scripts] in pyproject.toml)."""
    mcp.run()


if __name__ == "__main__":
    main()
