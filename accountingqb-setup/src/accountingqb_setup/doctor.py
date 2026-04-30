"""Doctor command - diagnose AccountingQB setup issues."""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from .config import mask_license_key, read_config
from .license import validate_license
from .paths import get_config_path


@dataclass
class CheckResult:
    """Result of a diagnostic check."""
    name: str
    passed: bool
    message: str
    details: Optional[str] = None
    fix: Optional[str] = None


def check_uv_installed() -> CheckResult:
    """Check if uv/uvx is installed and accessible."""
    uvx_path = shutil.which("uvx")

    if uvx_path:
        return CheckResult(
            name="uv installed",
            passed=True,
            message=f"uvx found at {uvx_path}",
        )

    # Check for uv without uvx
    uv_path = shutil.which("uv")
    if uv_path:
        return CheckResult(
            name="uv installed",
            passed=True,
            message=f"uv found at {uv_path} (uvx available via 'uv tool run')",
        )

    return CheckResult(
        name="uv installed",
        passed=False,
        message="uv/uvx not found in PATH",
        fix="Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
    )


def check_config_exists(config_path: Path) -> CheckResult:
    """Check if Claude Desktop config file exists."""
    if config_path.exists():
        return CheckResult(
            name="Config file exists",
            passed=True,
            message=str(config_path),
        )

    return CheckResult(
        name="Config file exists",
        passed=False,
        message=f"Not found: {config_path}",
        fix="Run: uvx accountingqb-setup",
    )


def check_config_valid(config_path: Path) -> CheckResult:
    """Check if config file contains valid JSON."""
    if not config_path.exists():
        return CheckResult(
            name="Config valid JSON",
            passed=False,
            message="Config file does not exist",
        )

    try:
        read_config(config_path)
        return CheckResult(
            name="Config valid JSON",
            passed=True,
            message="Config file is valid JSON",
        )
    except Exception as e:
        return CheckResult(
            name="Config valid JSON",
            passed=False,
            message=f"Invalid JSON: {e}",
            fix="Fix the JSON syntax or delete the file and run setup again",
        )


def check_accountingqb_configured(config_path: Path) -> tuple[CheckResult, Optional[str]]:
    """Check if accountingqb is configured. Returns (result, license_key)."""
    if not config_path.exists():
        return CheckResult(
            name="AccountingQB configured",
            passed=False,
            message="Config file does not exist",
            fix="Run: uvx accountingqb-setup",
        ), None

    try:
        config = read_config(config_path)
    except Exception:
        return CheckResult(
            name="AccountingQB configured",
            passed=False,
            message="Could not read config file",
        ), None

    mcp_servers = config.get("mcpServers", {})
    entry = mcp_servers.get("accountingqb")

    if entry is None:
        return CheckResult(
            name="AccountingQB configured",
            passed=False,
            message="accountingqb not found in mcpServers",
            fix="Run: uvx accountingqb-setup",
        ), None

    license_key = entry.get("env", {}).get("QB_LICENSE_KEY", "")

    if not license_key:
        return CheckResult(
            name="AccountingQB configured",
            passed=False,
            message="QB_LICENSE_KEY not set in config",
            fix="Run: uvx accountingqb-setup --license-key YOUR_KEY",
        ), None

    return CheckResult(
        name="AccountingQB configured",
        passed=True,
        message=f"License key: {mask_license_key(license_key)}",
    ), license_key


def check_license_valid(license_key: str) -> CheckResult:
    """Check if license key is valid with the server."""
    is_valid, message = validate_license(license_key, skip_server=False)

    if is_valid:
        return CheckResult(
            name="License valid",
            passed=True,
            message=message,
        )

    return CheckResult(
        name="License valid",
        passed=False,
        message=message,
        fix="Check your license key at https://accountingqb.com/dashboard",
    )


def check_quickbooks_connected(license_key: str) -> CheckResult:
    """Check if QuickBooks is connected for this license."""
    try:
        response = httpx.get(
            f"https://accountingqb.com/api/license/status",
            params={"license_key": license_key},
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            companies = data.get("companies", [])

            if companies:
                company_names = [c.get("company_name", c.get("realm_id", "Unknown")) for c in companies]
                return CheckResult(
                    name="QuickBooks connected",
                    passed=True,
                    message=f"{len(companies)} company(ies): {', '.join(company_names)}",
                )
            else:
                return CheckResult(
                    name="QuickBooks connected",
                    passed=False,
                    message="No QuickBooks companies connected",
                    fix=f"Connect at: https://accountingqb.com/api/oauth/start?license_key={license_key}",
                )
        else:
            return CheckResult(
                name="QuickBooks connected",
                passed=False,
                message=f"Could not check status (HTTP {response.status_code})",
            )

    except httpx.TimeoutException:
        return CheckResult(
            name="QuickBooks connected",
            passed=False,
            message="Request timed out",
            details="Could not reach AccountingQB server",
        )
    except Exception as e:
        return CheckResult(
            name="QuickBooks connected",
            passed=False,
            message=f"Error: {e}",
        )


def check_mcp_server_starts(license_key: str) -> CheckResult:
    """Check if the MCP server can start (quick smoke test)."""
    try:
        # Try to run the server with --help or a quick command
        result = subprocess.run(
            ["uvx", "accountingqb", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**dict(__import__("os").environ), "QB_LICENSE_KEY": license_key},
        )

        if result.returncode == 0:
            return CheckResult(
                name="MCP server starts",
                passed=True,
                message="accountingqb package loads successfully",
            )
        else:
            return CheckResult(
                name="MCP server starts",
                passed=False,
                message="Server failed to start",
                details=result.stderr[:500] if result.stderr else None,
            )

    except subprocess.TimeoutExpired:
        # Timeout might actually mean it started and is waiting for input
        return CheckResult(
            name="MCP server starts",
            passed=True,
            message="Server appears to start (timed out waiting, which is expected)",
        )
    except FileNotFoundError:
        return CheckResult(
            name="MCP server starts",
            passed=False,
            message="uvx not found",
            fix="Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
        )
    except Exception as e:
        return CheckResult(
            name="MCP server starts",
            passed=False,
            message=f"Error: {e}",
        )


def run_doctor(config_path: Optional[Path] = None) -> list[CheckResult]:
    """Run all diagnostic checks."""
    if config_path is None:
        config_path = get_config_path()

    results = []
    license_key = None

    # Check 1: uv installed
    results.append(check_uv_installed())

    # Check 2: Config file exists
    results.append(check_config_exists(config_path))

    # Check 3: Config is valid JSON
    if config_path.exists():
        results.append(check_config_valid(config_path))

    # Check 4: AccountingQB configured
    config_result, license_key = check_accountingqb_configured(config_path)
    results.append(config_result)

    # Remaining checks require a license key
    if license_key:
        # Check 5: License valid
        results.append(check_license_valid(license_key))

        # Check 6: QuickBooks connected
        results.append(check_quickbooks_connected(license_key))

        # Check 7: MCP server starts
        results.append(check_mcp_server_starts(license_key))

    return results
