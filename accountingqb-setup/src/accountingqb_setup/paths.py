"""OS detection and config file path resolution."""

import os
import platform
from pathlib import Path


def get_os_name() -> str:
    """Return the current OS name: 'macos', 'windows', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def get_config_path(custom_path: str | None = None) -> Path:
    """
    Get the Claude Desktop config file path.

    Args:
        custom_path: Override the default path (for testing).

    Returns:
        Path to claude_desktop_config.json
    """
    if custom_path:
        return Path(custom_path)

    os_name = get_os_name()

    if os_name == "macos":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif os_name == "windows":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            raise RuntimeError("APPDATA environment variable not set")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:  # linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_backup_path(config_path: Path) -> Path:
    """Get the backup path for a config file."""
    return config_path.with_suffix(".json.bak")


def ensure_config_dir(config_path: Path) -> None:
    """Ensure the config directory exists."""
    config_path.parent.mkdir(parents=True, exist_ok=True)


def get_restart_instruction() -> str:
    """Get OS-specific restart instruction."""
    os_name = get_os_name()

    if os_name == "macos":
        return (
            "Fully quit Claude Desktop with Cmd+Q (not just close the window), "
            "then reopen it."
        )
    elif os_name == "windows":
        return (
            "Right-click the Claude icon in the system tray (bottom-right, "
            "may be in the overflow menu) and choose Quit. Then reopen Claude Desktop."
        )
    else:
        return (
            "Fully quit Claude Desktop (not just close the window), "
            "then reopen it."
        )
