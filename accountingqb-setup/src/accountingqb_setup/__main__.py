"""CLI entry point for accountingqb-setup."""

import getpass
import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from . import __version__
from .config import (
    backup_config,
    create_accountingqb_entry,
    format_entry_diff,
    mask_license_key,
    merge_config,
    read_config,
    remove_accountingqb,
    validate_round_trip,
    write_config,
)
from .doctor import run_doctor
from .license import validate_license
from .paths import get_config_path, get_os_name, get_restart_instruction

app = typer.Typer(
    name="accountingqb-setup",
    help="Setup helper for the AccountingQB MCP server in Claude Desktop.",
    add_completion=False,
)

console = Console()


def print_header():
    """Print the setup header."""
    console.print()
    console.print("[bold cyan]AccountingQB Setup[/bold cyan]")
    console.print("─" * 40)


def get_license_key_interactive() -> str:
    """Prompt for license key with hidden input."""
    console.print()
    console.print("[dim]Enter your license key (input is hidden):[/dim]")
    key = getpass.getpass("License key: ")
    return key.strip()


@app.command()
def main(
    license_key: Optional[str] = typer.Option(
        None,
        "--license-key",
        "-k",
        help="Your AccountingQB license key (or set QB_LICENSE_KEY env var)",
        envvar="QB_LICENSE_KEY",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom config file path (for testing)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts (non-interactive mode)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would change without writing",
    ),
    status: bool = typer.Option(
        False,
        "--status",
        "-s",
        help="Show current AccountingQB configuration status",
    ),
    uninstall: bool = typer.Option(
        False,
        "--uninstall",
        "-u",
        help="Remove AccountingQB from Claude Desktop config",
    ),
    skip_validation: bool = typer.Option(
        False,
        "--skip-validation",
        help="Skip server-side license validation",
    ),
    doctor: bool = typer.Option(
        False,
        "--doctor",
        "-d",
        help="Run diagnostic checks on your AccountingQB setup",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
    ),
):
    """
    Configure AccountingQB MCP server for Claude Desktop.

    Run without arguments for interactive setup. Your license key is
    never echoed to the terminal.
    """
    # Version check
    if version:
        console.print(f"accountingqb-setup {__version__}")
        raise typer.Exit(0)

    print_header()

    # Detect OS and config path
    os_name = get_os_name()
    config_path = get_config_path(config)

    console.print(f"[dim]Detected:[/dim] {os_name}")
    console.print(f"[dim]Config:[/dim] {config_path}")

    # Doctor check
    if doctor:
        do_doctor(config_path)
        raise typer.Exit(0)

    # Status check
    if status:
        show_status(config_path)
        raise typer.Exit(0)

    # Uninstall
    if uninstall:
        do_uninstall(config_path, yes, dry_run)
        raise typer.Exit(0)

    # Get license key
    if not license_key:
        license_key = get_license_key_interactive()

    if not license_key:
        console.print("[red]Error:[/red] No license key provided.")
        raise typer.Exit(1)

    # Validate license
    console.print()
    console.print("[dim]Validating license...[/dim]")
    is_valid, message = validate_license(license_key, skip_server=skip_validation)

    if not is_valid:
        console.print(f"[red]Error:[/red] {message}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {message}")

    # Read existing config
    try:
        current_config = read_config(config_path)
    except json.JSONDecodeError as e:
        console.print()
        console.print("[red]Error:[/red] Your Claude Desktop config file contains invalid JSON.")
        console.print(f"[dim]Details: {e}[/dim]")
        console.print()
        console.print("Please fix the JSON syntax manually, or delete the file to start fresh.")
        console.print(f"[dim]File: {config_path}[/dim]")
        raise typer.Exit(1)

    # Count existing servers
    existing_servers = list(current_config.get("mcpServers", {}).keys())
    if existing_servers:
        other_servers = [s for s in existing_servers if s != "accountingqb"]
        if other_servers:
            console.print(f"[dim]Found {len(other_servers)} other MCP server(s): {', '.join(other_servers)}[/dim]")

    # Merge
    new_config, changed, old_entry = merge_config(current_config, license_key)
    new_entry = create_accountingqb_entry(license_key)

    if not changed:
        console.print()
        console.print("[green]✓[/green] AccountingQB is already configured with this license key.")
        console.print("[dim]Nothing to do.[/dim]")
        raise typer.Exit(0)

    # Show what will change
    console.print()
    diff_text = format_entry_diff(old_entry, new_entry)
    console.print(Panel(diff_text, title="Changes", border_style="cyan"))

    # Dry run
    if dry_run:
        console.print()
        console.print("[yellow]Dry run:[/yellow] No changes written.")
        raise typer.Exit(0)

    # Confirm
    if not yes:
        console.print()
        if not Confirm.ask("Proceed with these changes?"):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Backup
    if config_path.exists():
        backup_path = backup_config(config_path)
        console.print(f"[dim]Backup created: {backup_path}[/dim]")

    # Write
    try:
        write_config(config_path, new_config)
    except Exception as e:
        console.print(f"[red]Error writing config:[/red] {e}")
        raise typer.Exit(1)

    # Validate round-trip
    if not validate_round_trip(config_path, new_config):
        console.print("[red]Warning:[/red] Config file doesn't match expected content after write.")
        console.print("[dim]Your backup is still available.[/dim]")
        raise typer.Exit(1)

    # Success
    console.print()
    console.print("[green]✓[/green] AccountingQB configured successfully!")
    console.print()
    console.print(Panel(
        get_restart_instruction(),
        title="Next Step",
        border_style="green"
    ))
    console.print()
    console.print('[dim]After restarting, ask Claude: "What QuickBooks tools do you have?"[/dim]')


def show_status(config_path: Path):
    """Show current AccountingQB configuration status."""
    console.print()

    if not config_path.exists():
        console.print("[yellow]Config file does not exist.[/yellow]")
        console.print("[dim]AccountingQB is not configured.[/dim]")
        return

    try:
        config = read_config(config_path)
    except json.JSONDecodeError:
        console.print("[red]Config file contains invalid JSON.[/red]")
        return

    mcp_servers = config.get("mcpServers", {})
    entry = mcp_servers.get("accountingqb")

    if entry is None:
        console.print("[yellow]AccountingQB is not configured.[/yellow]")
        console.print(f"[dim]Found {len(mcp_servers)} other MCP server(s).[/dim]")
        return

    console.print("[green]✓[/green] AccountingQB is configured")

    # Show masked license key
    license_key = entry.get("env", {}).get("QB_LICENSE_KEY", "")
    if license_key:
        console.print(f"[dim]License key: {mask_license_key(license_key)}[/dim]")

    console.print()
    console.print("[bold]Current entry:[/bold]")
    # Mask the key in the output
    display_entry = entry.copy()
    if "env" in display_entry and "QB_LICENSE_KEY" in display_entry["env"]:
        display_entry["env"] = display_entry["env"].copy()
        display_entry["env"]["QB_LICENSE_KEY"] = mask_license_key(
            display_entry["env"]["QB_LICENSE_KEY"]
        )
    console.print(Syntax(json.dumps(display_entry, indent=2), "json"))


def do_uninstall(config_path: Path, yes: bool, dry_run: bool):
    """Remove AccountingQB from the config."""
    console.print()

    if not config_path.exists():
        console.print("[dim]Config file does not exist. Nothing to uninstall.[/dim]")
        return

    try:
        config = read_config(config_path)
    except json.JSONDecodeError:
        console.print("[red]Config file contains invalid JSON. Cannot proceed.[/red]")
        raise typer.Exit(1)

    new_config, removed = remove_accountingqb(config)

    if not removed:
        console.print("[dim]AccountingQB is not configured. Nothing to uninstall.[/dim]")
        return

    console.print("[yellow]This will remove the AccountingQB entry from your Claude Desktop config.[/yellow]")

    if dry_run:
        console.print()
        console.print("[yellow]Dry run:[/yellow] No changes written.")
        return

    if not yes:
        if not Confirm.ask("Proceed?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    # Backup
    backup_path = backup_config(config_path)
    console.print(f"[dim]Backup created: {backup_path}[/dim]")

    # Write
    try:
        write_config(config_path, new_config)
    except Exception as e:
        console.print(f"[red]Error writing config:[/red] {e}")
        raise typer.Exit(1)

    console.print()
    console.print("[green]✓[/green] AccountingQB removed from Claude Desktop config.")
    console.print()
    console.print(Panel(
        get_restart_instruction(),
        title="Next Step",
        border_style="green"
    ))


def do_doctor(config_path: Path):
    """Run diagnostic checks."""
    console.print()
    console.print("[bold cyan]AccountingQB Doctor[/bold cyan]")
    console.print("Running diagnostic checks...")
    console.print()

    results = run_doctor(config_path)

    passed = 0
    failed = 0

    for result in results:
        if result.passed:
            console.print(f"[green]✓[/green] {result.name}")
            console.print(f"  [dim]{result.message}[/dim]")
            passed += 1
        else:
            console.print(f"[red]✗[/red] {result.name}")
            console.print(f"  [red]{result.message}[/red]")
            if result.details:
                console.print(f"  [dim]{result.details}[/dim]")
            if result.fix:
                console.print(f"  [yellow]Fix:[/yellow] {result.fix}")
            failed += 1
        console.print()

    # Summary
    console.print("─" * 40)
    if failed == 0:
        console.print(f"[green]All {passed} checks passed![/green]")
        console.print()
        console.print("[dim]Your AccountingQB setup looks healthy.[/dim]")
    else:
        console.print(f"[yellow]{passed} passed, {failed} failed[/yellow]")
        console.print()
        console.print("[dim]Fix the issues above and run --doctor again.[/dim]")


if __name__ == "__main__":
    app()
