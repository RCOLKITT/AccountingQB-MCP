#!/usr/bin/env python3
"""
QuickBooks MCP Server — Interactive Setup

Walks you through connecting your QuickBooks Online account:
1. Creates/validates your Intuit Developer App credentials
2. Runs the OAuth 2.0 authorization flow locally
3. Writes your Claude Desktop configuration automatically

Usage:
    python setup.py
    python setup.py --sandbox     # Use sandbox environment
    python setup.py --reconfigure # Re-run setup with existing credentials
"""

import argparse
import http.server
import json
import os
import platform
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OAUTH_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES = "com.intuit.quickbooks.accounting"
REDIRECT_PORT = 8080
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
CONFIG_FILE = ".env"

# ANSI colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header():
    print(f"""
{BOLD}╔══════════════════════════════════════════════════════╗
║       QuickBooks MCP Server — Setup Wizard           ║
║                                                      ║
║   Connect your QuickBooks Online to Claude Desktop    ║
╚══════════════════════════════════════════════════════╝{RESET}
""")


def print_step(step_num, total, message):
    print(f"\n{BLUE}[Step {step_num}/{total}]{RESET} {BOLD}{message}{RESET}")


def print_success(message):
    print(f"  {GREEN}✓{RESET} {message}")


def print_warning(message):
    print(f"  {YELLOW}⚠{RESET} {message}")


def print_error(message):
    print(f"  {RED}✗{RESET} {message}")


# ---------------------------------------------------------------------------
# OAuth callback handler
# ---------------------------------------------------------------------------
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles the OAuth redirect from Intuit."""
    auth_code = None
    realm_id = None
    error = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback":
            if "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                OAuthCallbackHandler.realm_id = params.get("realmId", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <html><body style="font-family: system-ui; text-align: center; padding: 60px;">
                <h1 style="color: #22c55e;">&#10003; Connected!</h1>
                <p>QuickBooks authorization successful. You can close this tab.</p>
                <script>setTimeout(() => window.close(), 3000)</script>
                </body></html>
                """)
            elif "error" in params:
                OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"""
                <html><body style="font-family: system-ui; text-align: center; padding: 60px;">
                <h1 style="color: #ef4444;">Authorization Failed</h1>
                <p>{OAuthCallbackHandler.error}</p>
                </body></html>
                """.encode())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def exchange_code_for_tokens(client_id: str, client_secret: str, auth_code: str) -> dict:
    """Exchange the authorization code for access and refresh tokens."""
    try:
        import httpx
    except ImportError:
        print_error("httpx not installed. Run: pip install httpx")
        sys.exit(1)

    resp = httpx.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
        headers={"Accept": "application/json"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------------
# Claude Desktop config
# ---------------------------------------------------------------------------
def get_claude_config_path() -> Path:
    """Get the Claude Desktop config file path based on OS."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".claude" / "claude_desktop_config.json"


def find_python() -> str:
    """Find the best Python executable."""
    candidates = [sys.executable, "python3", "python"]
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and "Python 3" in result.stdout:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return sys.executable


def update_claude_config(env_vars: dict, server_py_path: str, python_path: str):
    """Add or update the QuickBooks MCP server entry in Claude Desktop config."""
    config_path = get_claude_config_path()

    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            print_warning("Existing Claude config was invalid, creating new one.")

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["quickbooks"] = {
        "command": python_path,
        "args": [server_py_path],
        "env": env_vars,
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def save_env_file(env_vars: dict, directory: str):
    """Save credentials to .env file (gitignored, local reference only)."""
    env_path = Path(directory) / CONFIG_FILE
    lines = [
        "# QuickBooks MCP Server credentials",
        "# This file is gitignored and should NEVER be committed.",
        "# It is a local backup of your credentials.",
        "",
    ]
    for key, value in env_vars.items():
        lines.append(f"{key}={value}")
    lines.append("")
    env_path.write_text("\n".join(lines))
    os.chmod(env_path, 0o600)  # Owner read/write only
    return env_path


# ---------------------------------------------------------------------------
# Main setup flow
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="QuickBooks MCP Server Setup")
    parser.add_argument("--sandbox", action="store_true", help="Use Intuit sandbox environment")
    parser.add_argument("--reconfigure", action="store_true", help="Re-run setup even if already configured")
    args = parser.parse_args()

    print_header()

    total_steps = 4
    server_dir = str(Path(__file__).parent.resolve())
    server_py = str(Path(server_dir) / "server.py")

    # -----------------------------------------------------------------------
    # Step 1: Collect Intuit Developer App credentials
    # -----------------------------------------------------------------------
    print_step(1, total_steps, "Intuit Developer App Credentials")
    print()
    print("  If you don't have an Intuit Developer App yet:")
    print(f"  1. Go to {BOLD}https://developer.intuit.com{RESET}")
    print("  2. Sign in and create a new app")
    print('  3. Select "QuickBooks Online and Payments"')
    print(f"  4. Set redirect URI to: {BOLD}{REDIRECT_URI}{RESET}")
    print(f"  5. Copy your {BOLD}Client ID{RESET} and {BOLD}Client Secret{RESET}")
    print()

    client_id = input(f"  Enter Client ID: ").strip()
    if not client_id:
        print_error("Client ID is required.")
        sys.exit(1)

    client_secret = input(f"  Enter Client Secret: ").strip()
    if not client_secret:
        print_error("Client Secret is required.")
        sys.exit(1)

    print_success("Credentials received.")

    # -----------------------------------------------------------------------
    # Step 2: Run OAuth flow
    # -----------------------------------------------------------------------
    print_step(2, total_steps, "QuickBooks Authorization")
    print()
    print("  Opening your browser to authorize access to your QuickBooks company...")
    print("  (If the browser doesn't open, copy the URL below)")
    print()

    state = secrets.token_urlsafe(32)
    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": state,
    })
    auth_url = f"{OAUTH_AUTH_URL}?{auth_params}"

    # Start local server to receive callback
    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print(f"  {BLUE}{auth_url}{RESET}")
    print()
    webbrowser.open(auth_url)

    print("  Waiting for authorization... (press Ctrl+C to cancel)")
    server_thread.join(timeout=300)  # 5 minute timeout
    server.server_close()

    if OAuthCallbackHandler.error:
        print_error(f"Authorization failed: {OAuthCallbackHandler.error}")
        sys.exit(1)

    if not OAuthCallbackHandler.auth_code:
        print_error("Authorization timed out. Please try again.")
        sys.exit(1)

    print_success("Authorization received!")

    # Exchange code for tokens
    print("  Exchanging authorization code for tokens...")
    try:
        tokens = exchange_code_for_tokens(client_id, client_secret, OAuthCallbackHandler.auth_code)
    except Exception as e:
        print_error(f"Token exchange failed: {e}")
        sys.exit(1)

    refresh_token = tokens.get("refresh_token", "")
    realm_id = OAuthCallbackHandler.realm_id or ""

    if not refresh_token:
        print_error("No refresh token received. Please try again.")
        sys.exit(1)

    if not realm_id:
        realm_id = input("  Enter your QuickBooks Company ID (Realm ID): ").strip()

    print_success(f"Connected to QuickBooks company: {realm_id}")

    # -----------------------------------------------------------------------
    # Step 3: Save configuration
    # -----------------------------------------------------------------------
    print_step(3, total_steps, "Saving Configuration")

    environment = "sandbox" if args.sandbox else "production"
    env_vars = {
        "QB_CLIENT_ID": client_id,
        "QB_CLIENT_SECRET": client_secret,
        "QB_REALM_ID": realm_id,
        "QB_REFRESH_TOKEN": refresh_token,
        "QB_ENVIRONMENT": environment,
    }

    # Save .env as local backup
    env_path = save_env_file(env_vars, server_dir)
    print_success(f"Credentials saved to {env_path} (chmod 600)")

    # Update Claude Desktop config
    python_path = find_python()
    try:
        config_path = update_claude_config(env_vars, server_py, python_path)
        print_success(f"Claude Desktop config updated: {config_path}")
    except Exception as e:
        print_warning(f"Could not update Claude Desktop config: {e}")
        print_warning("You'll need to add the server manually (see README).")

    # -----------------------------------------------------------------------
    # Step 4: Verify
    # -----------------------------------------------------------------------
    print_step(4, total_steps, "Verification")

    print("  Testing QuickBooks connection...")
    try:
        import httpx

        # Quick test: refresh the token to verify credentials work
        resp = httpx.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            new_tokens = resp.json()
            # Update refresh token if rotated
            new_refresh = new_tokens.get("refresh_token")
            if new_refresh and new_refresh != refresh_token:
                env_vars["QB_REFRESH_TOKEN"] = new_refresh
                save_env_file(env_vars, server_dir)
                update_claude_config(env_vars, server_py, python_path)
                print_success("Refresh token rotated and saved.")
            print_success("QuickBooks connection verified!")
        else:
            print_warning(f"Connection test returned status {resp.status_code}.")
            print_warning("Credentials saved — you can retry by running setup again.")
    except ImportError:
        print_warning("httpx not available — skipping connection test.")
        print_warning("Install with: pip install httpx")
    except Exception as e:
        print_warning(f"Connection test failed: {e}")
        print_warning("Credentials saved — you may need to re-authorize.")

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════════╗
║                  Setup Complete!                     ║
╚══════════════════════════════════════════════════════╝{RESET}

{BOLD}Next steps:{RESET}
  1. Restart Claude Desktop to load the new server
  2. Ask Claude: "What's my company info in QuickBooks?"

{BOLD}Security notes:{RESET}
  • Your credentials are stored in Claude Desktop's config
  • The .env file is a local backup (gitignored, chmod 600)
  • Refresh tokens rotate automatically — don't share them
  • Token expires after 100 days of inactivity

{BOLD}Environment:{RESET} {environment}
{BOLD}Company ID:{RESET} {realm_id}

{YELLOW}Need help?{RESET} https://github.com/RCOLKITT/AccountingQB-MCP/issues
""")


if __name__ == "__main__":
    main()
