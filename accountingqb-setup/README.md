# accountingqb-setup

Setup helper for the AccountingQB MCP server in Claude Desktop.

Edits your `claude_desktop_config.json` safely: parses it as JSON (never regex),
preserves your other MCP servers, makes a `.bak` before writing, validates the
result round-trips, and gives you a clear restart instruction.

## Install and run (end users)

```sh
uvx accountingqb-setup
```

You'll be prompted for your license key (input is hidden, never echoed). The
helper detects your OS, finds your Claude Desktop config, shows you exactly
what it's about to change, and asks for confirmation before writing.

After it finishes, fully quit Claude Desktop:

- **macOS:** Cmd+Q. Closing the window is not enough.
- **Windows:** Right-click the Claude tray icon -> Quit.

Then reopen Claude Desktop. Ask "What QuickBooks tools do you have?" to
verify the connection.

## Common flags

```sh
# Non-interactive (CI, scripts, retries)
accountingqb-setup --license-key LK-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX --yes

# See what would change without writing
accountingqb-setup --license-key LK-... --dry-run

# Check current state
accountingqb-setup --status

# Diagnose issues (checks config, license, QB connection, server)
accountingqb-setup --doctor

# Remove
accountingqb-setup --uninstall

# Test against a config file in a different location
accountingqb-setup --config /tmp/test_config.json
```

## Doctor command

The `--doctor` flag runs comprehensive diagnostic checks:

1. **uv installed** - Checks if uvx is available in PATH
2. **Config file exists** - Verifies Claude Desktop config file is present
3. **Config valid JSON** - Ensures the config file is valid JSON
4. **AccountingQB configured** - Checks if the MCP entry exists with a license key
5. **License valid** - Validates the license key with the server
6. **QuickBooks connected** - Checks if any QuickBooks companies are connected
7. **MCP server starts** - Verifies the accountingqb package can load

Example output:

```
AccountingQB Doctor
Running diagnostic checks...

✓ uv installed
  uvx found at /usr/local/bin/uvx

✓ Config file exists
  /Users/you/Library/Application Support/Claude/claude_desktop_config.json

✓ Config valid JSON
  Config file is valid JSON

✓ AccountingQB configured
  License key: LK-****************************7F93

✓ License valid
  License valid (tier: solopreneur)

✓ QuickBooks connected
  1 company(ies): My Business LLC

✓ MCP server starts
  accountingqb package loads successfully

────────────────────────────────────────
All 7 checks passed!

Your AccountingQB setup looks healthy.
```

You can also pass the key via the `QB_LICENSE_KEY` environment variable
instead of `--license-key`.

## What gets written

The helper merges this entry into the `mcpServers` object in your Claude
Desktop config:

```json
"accountingqb": {
  "command": "uvx",
  "args": ["accountingqb"],
  "env": {
    "QB_LICENSE_KEY": "<your key>"
  }
}
```

If `accountingqb` is already configured, the helper compares the existing
entry to the new one. If the license key has changed, it shows you the diff
and confirms before updating. If the entry is identical, it exits with a
"nothing to do" message.

## Safety

- **JSON-aware merge.** The config is parsed as JSON, the entry is added,
  the result is serialized back. No regex edits. Existing servers, custom
  top-level keys (e.g. `globalShortcut`), and formatting preferences are
  all preserved structurally.
- **Backup first.** Before writing, the existing config is copied to
  `claude_desktop_config.json.bak`.
- **Atomic write.** The new config is written to a temp file in the same
  directory, then renamed over the original. A crash mid-write can't
  corrupt your config.
- **Round-trip validation.** After writing, the file is reloaded and
  compared to what we intended to write. Any mismatch raises an error
  (and the backup is still on disk).
- **No license-key echoing.** Keys entered interactively use `getpass`
  (no terminal echo). Keys are masked when shown in confirmation output.
- **Refuses to repair invalid JSON.** If your existing config is broken,
  the helper tells you to fix it manually rather than guessing.

## Develop locally

```sh
git clone https://github.com/RCOLKITT/AccountingQB-MCP.git
cd AccountingQB-MCP/accountingqb-setup
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## License

MIT
