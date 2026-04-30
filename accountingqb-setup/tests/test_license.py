"""Tests for license module."""

import pytest

from accountingqb_setup.license import validate_format


class TestValidateFormat:
    """Tests for validate_format."""

    def test_valid_format(self):
        """Valid license key format passes."""
        assert validate_format("LK-0123456789ABCDEF0123456789ABCDEF") is True

    def test_valid_format_lowercase(self):
        """Lowercase hex chars are valid."""
        assert validate_format("LK-0123456789abcdef0123456789abcdef") is True

    def test_invalid_prefix(self):
        """Invalid prefix fails."""
        assert validate_format("XX-0123456789ABCDEF0123456789ABCDEF") is False

    def test_too_short(self):
        """Too short fails."""
        assert validate_format("LK-01234567") is False

    def test_too_long(self):
        """Too long fails."""
        assert validate_format("LK-0123456789ABCDEF0123456789ABCDEFEXTRA") is False

    def test_invalid_chars(self):
        """Non-hex chars fail."""
        assert validate_format("LK-0123456789ABCDEF0123456789ABCDGH") is False

    def test_empty_string(self):
        """Empty string fails."""
        assert validate_format("") is False

    def test_missing_dash(self):
        """Missing dash fails."""
        assert validate_format("LK0123456789ABCDEF0123456789ABCDEF") is False
