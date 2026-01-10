"""Denylist and Allowlist command groups for NextDNS Blocker."""

import csv
import json
import logging
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from .client import NextDNSClient
from .common import audit_log, validate_domain
from .config import load_config

logger = logging.getLogger(__name__)

console = Console(highlight=False)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_client(config_dir: Optional[Path] = None) -> NextDNSClient:
    """Create a NextDNS client from config."""
    config = load_config(config_dir)
    return NextDNSClient(config["api_key"], config["profile_id"])


def _export_to_json(domains: list[dict[str, Any]]) -> str:
    """Export domains to JSON format."""
    # Extract just the domain names and active status
    export_data = [{"domain": d.get("id", ""), "active": d.get("active", True)} for d in domains]
    return json.dumps(export_data, indent=2)


def _export_to_csv(domains: list[dict[str, Any]]) -> str:
    """Export domains to CSV format."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["domain", "active"])
    for d in domains:
        writer.writerow([d.get("id", ""), d.get("active", True)])
    return output.getvalue()


def _parse_import_file(
    file_path: Path,
) -> tuple[list[str], list[str]]:
    """
    Parse import file (JSON or CSV) and return list of domains.

    Returns:
        Tuple of (domains_to_add, errors)
    """
    content = file_path.read_text(encoding="utf-8")
    domains: list[str] = []
    errors: list[str] = []

    # Try JSON first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    domains.append(item)
                elif isinstance(item, dict) and "domain" in item:
                    # Only add active domains (or all if active not specified)
                    if item.get("active", True):
                        domains.append(item["domain"])
        elif isinstance(data, dict) and "domains" in data:
            # Support {"domains": ["a.com", "b.com"]} format
            for d in data["domains"]:
                if isinstance(d, str):
                    domains.append(d)
        return domains, errors
    except json.JSONDecodeError:
        pass

    # Try CSV
    try:
        reader = csv.DictReader(StringIO(content))
        for row in reader:
            domain = row.get("domain", "").strip()
            if domain:
                # Only add active domains
                active = row.get("active", "true").lower() in ("true", "1", "yes", "")
                if active:
                    domains.append(domain)
        if domains:
            return domains, errors
    except (csv.Error, KeyError):
        pass

    # Try plain text (one domain per line)
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.append(line)

    return domains, errors


def _validate_domains(domains: list[str]) -> tuple[list[str], list[str]]:
    """Validate domains and return valid/invalid lists."""
    valid = []
    invalid = []
    for domain in domains:
        if validate_domain(domain):
            valid.append(domain)
        else:
            invalid.append(f"{domain}: invalid format")
    return valid, invalid


# =============================================================================
# DENYLIST COMMAND GROUP
# =============================================================================


@click.group("denylist")
def denylist_cli() -> None:
    """Manage NextDNS denylist (blocked domains).

    Export, import, add, or remove domains from your NextDNS denylist.
    """
    pass


@denylist_cli.command("list")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def denylist_list(config_dir: Optional[Path]) -> None:
    """List all domains in the denylist."""
    try:
        client = _get_client(config_dir)
        domains = client.get_denylist(use_cache=False)

        if domains is None:
            console.print("\n  [red]Failed to fetch denylist from NextDNS[/red]\n")
            sys.exit(1)

        if not domains:
            console.print("\n  [yellow]Denylist is empty[/yellow]\n")
            return

        table = Table(title="Denylist", show_header=True, header_style="bold")
        table.add_column("Domain", style="cyan")
        table.add_column("Active", style="green")

        for d in domains:
            active = "Yes" if d.get("active", True) else "No"
            table.add_row(d.get("id", ""), active)

        console.print()
        console.print(table)
        console.print(f"\n  Total: {len(domains)} domains\n")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@denylist_cli.command("export")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output file (default: stdout)",
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def denylist_export(output_format: str, output: Optional[Path], config_dir: Optional[Path]) -> None:
    """Export denylist to JSON or CSV file."""
    try:
        client = _get_client(config_dir)
        domains = client.get_denylist(use_cache=False)

        if domains is None:
            console.print("\n  [red]Failed to fetch denylist from NextDNS[/red]\n")
            sys.exit(1)

        if output_format == "json":
            content = _export_to_json(domains)
        else:
            content = _export_to_csv(domains)

        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"\n  [green]Exported {len(domains)} domains to {output}[/green]\n")
        else:
            click.echo(content)

        audit_log("DENYLIST_EXPORT", f"Exported {len(domains)} domains")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@denylist_cli.command("import")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Show what would be imported")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def denylist_import(file: Path, dry_run: bool, config_dir: Optional[Path]) -> None:
    """Import domains to denylist from a file.

    Supports JSON, CSV, or plain text (one domain per line).
    """
    try:
        domains, parse_errors = _parse_import_file(file)

        if parse_errors:
            for error in parse_errors:
                console.print(f"  [yellow]Warning: {error}[/yellow]")

        if not domains:
            console.print("\n  [yellow]No domains found in file[/yellow]\n")
            return

        valid, invalid = _validate_domains(domains)

        if invalid:
            console.print("\n  [yellow]Invalid domains (skipped):[/yellow]")
            for error in invalid[:10]:
                console.print(f"    {error}")
            if len(invalid) > 10:
                console.print(f"    ... and {len(invalid) - 10} more")

        if not valid:
            console.print("\n  [red]No valid domains to import[/red]\n")
            sys.exit(1)

        if dry_run:
            console.print(f"\n  [cyan]Would import {len(valid)} domains:[/cyan]")
            for domain in valid[:20]:
                console.print(f"    {domain}")
            if len(valid) > 20:
                console.print(f"    ... and {len(valid) - 20} more")
            console.print()
            return

        client = _get_client(config_dir)

        # Get existing domains to avoid duplicates
        existing = client.get_denylist(use_cache=False) or []
        existing_domains = {d.get("id", "") for d in existing}

        added = 0
        skipped = 0
        failed = 0

        console.print(f"\n  Importing {len(valid)} domains...")

        for domain in valid:
            if domain in existing_domains:
                skipped += 1
                continue

            if client.block(domain):
                added += 1
            else:
                failed += 1

        console.print(
            f"\n  [green]Added: {added}[/green]  "
            f"[yellow]Skipped (existing): {skipped}[/yellow]  "
            f"[red]Failed: {failed}[/red]\n"
        )

        audit_log(
            "DENYLIST_IMPORT",
            f"Added {added}, skipped {skipped}, failed {failed} from {file.name}",
        )

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@denylist_cli.command("add")
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def denylist_add(domains: tuple[str, ...], config_dir: Optional[Path]) -> None:
    """Add one or more domains to the denylist.

    Example: nextdns-blocker denylist add example.com test.org
    """
    try:
        valid, invalid = _validate_domains(list(domains))

        if invalid:
            console.print("\n  [red]Invalid domains:[/red]")
            for error in invalid:
                console.print(f"    {error}")
            if not valid:
                sys.exit(1)

        client = _get_client(config_dir)

        added = 0
        failed = 0

        for domain in valid:
            if client.block(domain):
                console.print(f"  [green]+[/green] {domain}")
                added += 1
            else:
                console.print(f"  [red]x[/red] {domain} (failed)")
                failed += 1

        console.print(f"\n  Added {added} domain(s) to denylist\n")

        if added > 0:
            audit_log("DENYLIST_ADD", f"Added {added} domains: {', '.join(valid)}")

        if failed > 0:
            sys.exit(1)

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@denylist_cli.command("remove")
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def denylist_remove(domains: tuple[str, ...], config_dir: Optional[Path]) -> None:
    """Remove one or more domains from the denylist.

    Example: nextdns-blocker denylist remove example.com test.org
    """
    try:
        client = _get_client(config_dir)

        removed = 0
        failed = 0

        for domain in domains:
            if client.unblock(domain):
                console.print(f"  [green]-[/green] {domain}")
                removed += 1
            else:
                console.print(f"  [red]x[/red] {domain} (not found or failed)")
                failed += 1

        console.print(f"\n  Removed {removed} domain(s) from denylist\n")

        if removed > 0:
            audit_log("DENYLIST_REMOVE", f"Removed {removed} domains: {', '.join(domains)}")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


# =============================================================================
# ALLOWLIST COMMAND GROUP
# =============================================================================


@click.group("allowlist")
def allowlist_cli() -> None:
    """Manage NextDNS allowlist (whitelisted domains).

    Export, import, add, or remove domains from your NextDNS allowlist.
    """
    pass


@allowlist_cli.command("list")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allowlist_list(config_dir: Optional[Path]) -> None:
    """List all domains in the allowlist."""
    try:
        client = _get_client(config_dir)
        domains = client.get_allowlist(use_cache=False)

        if domains is None:
            console.print("\n  [red]Failed to fetch allowlist from NextDNS[/red]\n")
            sys.exit(1)

        if not domains:
            console.print("\n  [yellow]Allowlist is empty[/yellow]\n")
            return

        table = Table(title="Allowlist", show_header=True, header_style="bold")
        table.add_column("Domain", style="cyan")
        table.add_column("Active", style="green")

        for d in domains:
            active = "Yes" if d.get("active", True) else "No"
            table.add_row(d.get("id", ""), active)

        console.print()
        console.print(table)
        console.print(f"\n  Total: {len(domains)} domains\n")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@allowlist_cli.command("export")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output file (default: stdout)",
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allowlist_export(
    output_format: str, output: Optional[Path], config_dir: Optional[Path]
) -> None:
    """Export allowlist to JSON or CSV file."""
    try:
        client = _get_client(config_dir)
        domains = client.get_allowlist(use_cache=False)

        if domains is None:
            console.print("\n  [red]Failed to fetch allowlist from NextDNS[/red]\n")
            sys.exit(1)

        if output_format == "json":
            content = _export_to_json(domains)
        else:
            content = _export_to_csv(domains)

        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"\n  [green]Exported {len(domains)} domains to {output}[/green]\n")
        else:
            click.echo(content)

        audit_log("ALLOWLIST_EXPORT", f"Exported {len(domains)} domains")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@allowlist_cli.command("import")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Show what would be imported")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allowlist_import(file: Path, dry_run: bool, config_dir: Optional[Path]) -> None:
    """Import domains to allowlist from a file.

    Supports JSON, CSV, or plain text (one domain per line).
    """
    try:
        domains, parse_errors = _parse_import_file(file)

        if parse_errors:
            for error in parse_errors:
                console.print(f"  [yellow]Warning: {error}[/yellow]")

        if not domains:
            console.print("\n  [yellow]No domains found in file[/yellow]\n")
            return

        valid, invalid = _validate_domains(domains)

        if invalid:
            console.print("\n  [yellow]Invalid domains (skipped):[/yellow]")
            for error in invalid[:10]:
                console.print(f"    {error}")
            if len(invalid) > 10:
                console.print(f"    ... and {len(invalid) - 10} more")

        if not valid:
            console.print("\n  [red]No valid domains to import[/red]\n")
            sys.exit(1)

        if dry_run:
            console.print(f"\n  [cyan]Would import {len(valid)} domains:[/cyan]")
            for domain in valid[:20]:
                console.print(f"    {domain}")
            if len(valid) > 20:
                console.print(f"    ... and {len(valid) - 20} more")
            console.print()
            return

        client = _get_client(config_dir)

        # Get existing domains to avoid duplicates
        existing = client.get_allowlist(use_cache=False) or []
        existing_domains = {d.get("id", "") for d in existing}

        added = 0
        skipped = 0
        failed = 0

        console.print(f"\n  Importing {len(valid)} domains...")

        for domain in valid:
            if domain in existing_domains:
                skipped += 1
                continue

            if client.allow(domain):
                added += 1
            else:
                failed += 1

        console.print(
            f"\n  [green]Added: {added}[/green]  "
            f"[yellow]Skipped (existing): {skipped}[/yellow]  "
            f"[red]Failed: {failed}[/red]\n"
        )

        audit_log(
            "ALLOWLIST_IMPORT",
            f"Added {added}, skipped {skipped}, failed {failed} from {file.name}",
        )

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@allowlist_cli.command("add")
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allowlist_add(domains: tuple[str, ...], config_dir: Optional[Path]) -> None:
    """Add one or more domains to the allowlist.

    Example: nextdns-blocker allowlist add example.com test.org
    """
    try:
        valid, invalid = _validate_domains(list(domains))

        if invalid:
            console.print("\n  [red]Invalid domains:[/red]")
            for error in invalid:
                console.print(f"    {error}")
            if not valid:
                sys.exit(1)

        client = _get_client(config_dir)

        added = 0
        failed = 0

        for domain in valid:
            if client.allow(domain):
                console.print(f"  [green]+[/green] {domain}")
                added += 1
            else:
                console.print(f"  [red]x[/red] {domain} (failed)")
                failed += 1

        console.print(f"\n  Added {added} domain(s) to allowlist\n")

        if added > 0:
            audit_log("ALLOWLIST_ADD", f"Added {added} domains: {', '.join(valid)}")

        if failed > 0:
            sys.exit(1)

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@allowlist_cli.command("remove")
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allowlist_remove(domains: tuple[str, ...], config_dir: Optional[Path]) -> None:
    """Remove one or more domains from the allowlist.

    Example: nextdns-blocker allowlist remove example.com test.org
    """
    try:
        client = _get_client(config_dir)

        removed = 0
        failed = 0

        for domain in domains:
            if client.disallow(domain):
                console.print(f"  [green]-[/green] {domain}")
                removed += 1
            else:
                console.print(f"  [red]x[/red] {domain} (not found or failed)")
                failed += 1

        console.print(f"\n  Removed {removed} domain(s) from allowlist\n")

        if removed > 0:
            audit_log("ALLOWLIST_REMOVE", f"Removed {removed} domains: {', '.join(domains)}")

    except Exception as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


# =============================================================================
# REGISTRATION
# =============================================================================


def register_denylist(main: click.Group) -> None:
    """Register the denylist command group with the main CLI."""
    main.add_command(denylist_cli)


def register_allowlist(main: click.Group) -> None:
    """Register the allowlist command group with the main CLI."""
    main.add_command(allowlist_cli)
