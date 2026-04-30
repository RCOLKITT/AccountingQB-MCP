"""Tests for config module."""

import json
import tempfile
from pathlib import Path

import pytest

from accountingqb_setup.config import (
    create_accountingqb_entry,
    mask_license_key,
    merge_config,
    read_config,
    remove_accountingqb,
    write_config,
)


class TestReadConfig:
    """Tests for read_config."""

    def test_nonexistent_file_returns_empty_mcp_servers(self, tmp_path):
        """Non-existent file returns {"mcpServers": {}}."""
        config_path = tmp_path / "nonexistent.json"
        result = read_config(config_path)
        assert result == {"mcpServers": {}}

    def test_empty_file_returns_empty_mcp_servers(self, tmp_path):
        """Empty file returns {"mcpServers": {}}."""
        config_path = tmp_path / "empty.json"
        config_path.write_text("")
        result = read_config(config_path)
        assert result == {"mcpServers": {}}

    def test_valid_json_parsed(self, tmp_path):
        """Valid JSON is parsed correctly."""
        config_path = tmp_path / "valid.json"
        config_path.write_text('{"mcpServers": {"existing": {}}, "other": "value"}')
        result = read_config(config_path)
        assert result == {"mcpServers": {"existing": {}}, "other": "value"}

    def test_invalid_json_raises_error(self, tmp_path):
        """Invalid JSON raises JSONDecodeError."""
        config_path = tmp_path / "invalid.json"
        config_path.write_text("{invalid json")
        with pytest.raises(json.JSONDecodeError):
            read_config(config_path)


class TestMergeConfig:
    """Tests for merge_config."""

    def test_add_to_empty_config(self):
        """Adding to empty config creates mcpServers."""
        config = {}
        new_config, changed, old_entry = merge_config(config, "LK-TEST")

        assert changed is True
        assert old_entry is None
        assert "mcpServers" in new_config
        assert "accountingqb" in new_config["mcpServers"]

    def test_add_preserves_existing_servers(self):
        """Adding preserves existing MCP servers."""
        config = {
            "mcpServers": {
                "existing1": {"command": "test1"},
                "existing2": {"command": "test2"},
            }
        }
        new_config, changed, old_entry = merge_config(config, "LK-TEST")

        assert changed is True
        assert "existing1" in new_config["mcpServers"]
        assert "existing2" in new_config["mcpServers"]
        assert "accountingqb" in new_config["mcpServers"]

    def test_update_existing_entry(self):
        """Updating existing entry returns old entry."""
        config = {
            "mcpServers": {
                "accountingqb": {
                    "command": "uvx",
                    "args": ["accountingqb"],
                    "env": {"QB_LICENSE_KEY": "OLD-KEY"}
                }
            }
        }
        new_config, changed, old_entry = merge_config(config, "LK-NEW")

        assert changed is True
        assert old_entry is not None
        assert old_entry["env"]["QB_LICENSE_KEY"] == "OLD-KEY"
        assert new_config["mcpServers"]["accountingqb"]["env"]["QB_LICENSE_KEY"] == "LK-NEW"

    def test_identical_entry_no_change(self):
        """Identical entry returns changed=False."""
        config = {
            "mcpServers": {
                "accountingqb": create_accountingqb_entry("LK-SAME")
            }
        }
        new_config, changed, old_entry = merge_config(config, "LK-SAME")

        assert changed is False

    def test_preserves_other_top_level_keys(self):
        """Merge preserves other top-level keys."""
        config = {
            "mcpServers": {},
            "globalShortcut": "Cmd+Shift+A",
            "theme": "dark"
        }
        new_config, changed, old_entry = merge_config(config, "LK-TEST")

        assert new_config["globalShortcut"] == "Cmd+Shift+A"
        assert new_config["theme"] == "dark"


class TestRemoveAccountingqb:
    """Tests for remove_accountingqb."""

    def test_remove_existing_entry(self):
        """Removes accountingqb entry."""
        config = {
            "mcpServers": {
                "accountingqb": create_accountingqb_entry("LK-TEST"),
                "other": {}
            }
        }
        new_config, removed = remove_accountingqb(config)

        assert removed is True
        assert "accountingqb" not in new_config["mcpServers"]
        assert "other" in new_config["mcpServers"]

    def test_remove_nonexistent_entry(self):
        """Removing non-existent entry returns removed=False."""
        config = {"mcpServers": {"other": {}}}
        new_config, removed = remove_accountingqb(config)

        assert removed is False

    def test_remove_from_empty_config(self):
        """Removing from empty config returns removed=False."""
        config = {}
        new_config, removed = remove_accountingqb(config)

        assert removed is False


class TestWriteConfig:
    """Tests for write_config."""

    def test_creates_directory_if_needed(self, tmp_path):
        """Creates parent directory if it doesn't exist."""
        config_path = tmp_path / "subdir" / "config.json"
        config = {"mcpServers": {"test": {}}}

        write_config(config_path, config)

        assert config_path.exists()
        assert json.loads(config_path.read_text()) == config

    def test_atomic_write(self, tmp_path):
        """Write is atomic (no partial writes)."""
        config_path = tmp_path / "config.json"
        config = {"mcpServers": {"accountingqb": create_accountingqb_entry("LK-TEST")}}

        write_config(config_path, config)

        # File should be valid JSON
        result = json.loads(config_path.read_text())
        assert result == config

    def test_pretty_print(self, tmp_path):
        """Config is pretty-printed with 2-space indent."""
        config_path = tmp_path / "config.json"
        config = {"mcpServers": {"test": {"key": "value"}}}

        write_config(config_path, config)

        content = config_path.read_text()
        assert "\n" in content  # Multi-line
        assert "  " in content  # Indented


class TestMaskLicenseKey:
    """Tests for mask_license_key."""

    def test_mask_standard_key(self):
        """Standard key is masked correctly."""
        key = "LK-0E26A74E1349AFE856B595456F357F93"
        masked = mask_license_key(key)

        assert masked.startswith("LK-")
        assert masked.endswith("7F93")
        assert "*" in masked
        assert len(masked) == len(key)

    def test_mask_short_key(self):
        """Short key is fully masked."""
        key = "SHORT"
        masked = mask_license_key(key)

        assert masked == "*****"
