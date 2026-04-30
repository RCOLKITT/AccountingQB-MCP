"""License key validation."""

import re

import httpx


# License key format: LK-<32 hex chars>
LICENSE_KEY_PATTERN = re.compile(r"^LK-[A-F0-9]{32}$", re.IGNORECASE)

# API endpoint for license validation
LICENSE_API_URL = "https://accountingqb.com/api/license/verify"


def validate_format(license_key: str) -> bool:
    """
    Validate license key format.

    Args:
        license_key: The license key to validate.

    Returns:
        True if the format is valid.
    """
    return bool(LICENSE_KEY_PATTERN.match(license_key))


def validate_with_server(license_key: str, timeout: float = 10.0) -> tuple[bool, str]:
    """
    Validate license key with the AccountingQB server.

    Args:
        license_key: The license key to validate.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (is_valid, message).
    """
    try:
        response = httpx.post(
            LICENSE_API_URL,
            json={"license_key": license_key},
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("valid"):
                tier = data.get("tier", "unknown")
                return True, f"License valid (tier: {tier})"
            else:
                return False, data.get("error", "Invalid license key")
        elif response.status_code == 404:
            return False, "License key not found"
        elif response.status_code == 401:
            return False, "License key is invalid or expired"
        else:
            return False, f"Server error: {response.status_code}"

    except httpx.TimeoutException:
        # Network timeout - allow setup to proceed but warn
        return True, "Could not verify license (network timeout). Proceeding anyway."
    except httpx.RequestError as e:
        # Network error - allow setup to proceed but warn
        return True, f"Could not verify license ({e}). Proceeding anyway."


def validate_license(license_key: str, skip_server: bool = False) -> tuple[bool, str]:
    """
    Validate a license key (format + optional server check).

    Args:
        license_key: The license key to validate.
        skip_server: If True, only check format (for offline use).

    Returns:
        Tuple of (is_valid, message).
    """
    # Check format first
    if not validate_format(license_key):
        return False, (
            "Invalid license key format. "
            "Expected format: LK-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (32 hex chars)"
        )

    # Server validation
    if not skip_server:
        return validate_with_server(license_key)

    return True, "License key format valid (server check skipped)"
