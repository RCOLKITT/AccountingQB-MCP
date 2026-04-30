"""Entry point for running the AccountingQB MCP server."""

from .server import mcp

def main():
    """Run the AccountingQB MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
