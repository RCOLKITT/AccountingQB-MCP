"""Tests for license module."""

import pytest

from accountingqb_setup.license import validate_format


class TestValidateFormat:
    """Tests for validate_format."""

    def test_valid_format(self):
        """Valid license key format passes."""
        assert validate_format("LK-0E26A74E1349AFE856B595456F357F93") is True

    def test_valid_format_lowercase(self):
        """Lowercase hex chars are valid."""
        assert validate_format("LK-0e26a74e1349afe856b595456f357f93") is True

    def test_invalid_prefix(self):
        """Invalid prefix fails."""
        assert validate_format("XX-0E26A74E1349AFE856B595456F357F93") is False

    def test_too_short(self):
        """Too short fails."""
        assert validate_format("LK-0E26A74E") is False

    def test_too_long(self):
        """Too long fails."""
        assert validate_format("LK-0E26A74E1349AFE856B595456F357F93EXTRA") is False

    def test_invalid_chars(self):
        """Non-hex chars fail."""
        assert validate_format("LK-0E26A74E1349AFE856B595456F357FGH") is False

    def test_empty_string(self):
        """Empty string fails."""
        assert validate_format("") is False

    def test_missing_dash(self):
        """Missing dash fails."""
        assert validate_format("LK0E26A74E1349AFE856B595456F357F93") is False
