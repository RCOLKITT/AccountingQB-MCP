# Installation Guide

## Three Ways to Connect

1. **Remote connector (no install):** Add AccountingQB as a custom connector in Claude on the web, desktop, or mobile — nothing to install.
2. **Desktop extension (.mcpb):** One file with bundled dependencies — download from your dashboard and open with Claude Desktop.
3. **Manual uvx/pip install:** The self-hosted setup, documented below.

## Prerequisites
- Claude Desktop installed (download from https://claude.ai/download)
- QuickBooks Online account (any plan)
- AccountingQB license key (get one at accountingqb.com)
- uv package manager (we'll install this)

## Step 1: Install uv Package Manager

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
winget install astral-sh.uv
```

After installing, restart your terminal.

## Step 2: Add to Claude Desktop Config

Find your config file:
- **macOS:** ~/Library/Application Support/Claude/claude_desktop_config.json
- **Windows:** %APPDATA%\Claude\claude_desktop_config.json
- **Linux:** ~/.config/Claude/claude_desktop_config.json

Add this configuration (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "accountingqb": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "YOUR_LICENSE_KEY_HERE"
      }
    }
  }
}
```

Replace `YOUR_LICENSE_KEY_HERE` with your actual license key (starts with LK-).

## Step 3: Restart Claude Desktop

Completely quit Claude Desktop (not just close the window) and reopen it.

## Step 4: Connect QuickBooks

Visit https://accountingqb.com/dashboard and click "Connect QuickBooks" to authorize access to your QuickBooks Online company.

---

## Common Installation Issues

### "uvx not found" error
The uv package manager isn't installed or not in your PATH.
**Fix:** Run the install command above, then restart your terminal AND Claude Desktop.

### Config file doesn't exist
Create it manually at the path shown above. Copy and paste the full JSON config.

### Claude doesn't show AccountingQB tools
1. Verify your config file is valid JSON (check at jsonlint.com)
2. Make sure you saved the file
3. Completely quit and restart Claude Desktop (not just close the window)
4. Check that your license key is correct

### JSON syntax error
Common issues:
- Missing commas between entries
- Extra comma after the last entry
- Using single quotes instead of double quotes

Use jsonlint.com to validate your JSON.

### Adding to existing config
If you already have other MCP servers, add the accountingqb entry inside the existing "mcpServers" object:

```json
{
  "mcpServers": {
    "existingServer": { ... },
    "accountingqb": {
      "command": "uvx",
      "args": ["accountingqb"],
      "env": {
        "QB_LICENSE_KEY": "YOUR_KEY"
      }
    }
  }
}
```
