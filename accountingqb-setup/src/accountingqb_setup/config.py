"""Safe config file operations with backup and atomic write."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .paths import get_backup_path, ensure_config_dir


def read_config(config_path: Path) -> dict[str, Any]:
    """
    Read and parse the Claude Desktop config file.

    Args:
        config_path: Path to the config file.

    Returns:
        Parsed config as a dict. Returns {"mcpServers": {}} if file doesn't exist.

    Raises:
        json.JSONDecodeError: If the file exists but contains invalid JSON.
    """
    if not config_path.exists():
        return {"mcpServers": {}}

    content = config_path.read_text(encoding="utf-8")

    # Handle empty file
    if not content.strip():
        return {"mcpServers": {}}

    return json.loads(content)


def create_accountingqb_entry(license_key: str) -> dict[str, Any]:
    """Create the accountingqb MCP server entry."""
    return {
        "command": "uvx",
        "args": ["accountingqb"],
        "env": {
            "QB_LICENSE_KEY": license_key
        }
    }


def merge_config(
    config: dict[str, Any],
    license_key: str
) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    """
    Merge the accountingqb entry into the config.

    Args:
        config: The current config dict.
        license_key: The license key to use.

    Returns:
        Tuple of (new_config, changed, old_entry).
        - new_config: The updated config.
        - changed: True if the config was modified.
        - old_entry: The previous accountingqb entry if it existed, else None.
    """
    new_entry = create_accountingqb_entry(license_key)

    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    old_entry = config["mcpServers"].get("accountingqb")

    # Check if identical
    if old_entry == new_entry:
        return config, False, old_entry

    # Update
    config["mcpServers"]["accountingqb"] = new_entry

    return config, True, old_entry


def remove_accountingqb(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Remove the accountingqb entry from the config.

    Args:
        config: The current config dict.

    Returns:
        Tuple of (new_config, removed).
    """
    if "mcpServers" not in config:
        return config, False

    if "accountingqb" not in config["mcpServers"]:
        return config, False

    del config["mcpServers"]["accountingqb"]
    return config, True


def backup_config(config_path: Path) -> Path:
    """
    Create a backup of the config file.

    Args:
        config_path: Path to the config file.

    Returns:
        Path to the backup file.
    """
    backup_path = get_backup_path(config_path)

    if config_path.exists():
        content = config_path.read_bytes()
        backup_path.write_bytes(content)

    return backup_path


def write_config(config_path: Path, config: dict[str, Any]) -> None:
    """
    Write the config file atomically.

    Creates a temp file in the same directory, writes to it, then renames
    over the original. This ensures a crash mid-write can't corrupt the config.

    Args:
        config_path: Path to the config file.
        config: The config dict to write.
    """
    ensure_config_dir(config_path)

    # Serialize with pretty printing
    content = json.dumps(config, indent=2, ensure_ascii=False) + "\n"

    # Write to temp file in same directory (for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=".claude_config_",
        suffix=".tmp"
    )

    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)

        # Atomic rename
        os.replace(temp_path, config_path)
    except Exception:
        # Clean up temp file on error
        os.close(fd) if fd else None
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def validate_round_trip(config_path: Path, expected: dict[str, Any]) -> bool:
    """
    Verify the config file round-trips correctly.

    Args:
        config_path: Path to the config file.
        expected: The expected config dict.

    Returns:
        True if the file matches expected.
    """
    actual = read_config(config_path)
    return actual == expected


def mask_license_key(key: str) -> str:
    """Mask a license key for display, showing only first 3 and last 4 chars."""
    if len(key) <= 10:
        return "*" * len(key)
    return key[:3] + "*" * (len(key) - 7) + key[-4:]


def format_entry_diff(old_entry: dict[str, Any] | None, new_entry: dict[str, Any]) -> str:
    """Format a diff between old and new entries for display."""
    lines = []

    if old_entry is None:
        lines.append("Adding new entry:")
        lines.append(json.dumps(new_entry, indent=2))
    else:
        old_key = old_entry.get("env", {}).get("QB_LICENSE_KEY", "")
        new_key = new_entry.get("env", {}).get("QB_LICENSE_KEY", "")

        if old_key != new_key:
            lines.append("Updating license key:")
            lines.append(f"  Old: {mask_license_key(old_key)}")
            lines.append(f"  New: {mask_license_key(new_key)}")
        else:
            lines.append("Updating entry configuration:")
            lines.append(f"  Old: {json.dumps(old_entry, indent=2)}")
            lines.append(f"  New: {json.dumps(new_entry, indent=2)}")

    return "\n".join(lines)
