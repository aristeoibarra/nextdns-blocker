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

from .cli_helpers import command_context, handle_error
from .common import audit_log, validate_domain
from .notifications import EventType, send_notification

logger = logging.getLogger(__name__)

console = Console(highlight=False)  # Keep for tables


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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
    with command_context(config_dir, "fetching denylist") as (client, _config):
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
    with command_context(config_dir, "exporting denylist") as (client, _config):
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
    except (
        PermissionError,
        FileNotFoundError,
        json.JSONDecodeError,
        csv.Error,
        UnicodeDecodeError,
    ) as e:
        handle_error(e, "reading import file")

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

    with command_context(config_dir, "importing to denylist") as (client, _config):
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

            success, was_added = client.block(domain)
            if success and was_added:
                added += 1
            elif success:
                skipped += 1  # Already exists (shouldn't happen due to check above)
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
    valid, invalid = _validate_domains(list(domains))

    if invalid:
        console.print("\n  [red]Invalid domains:[/red]")
        for error in invalid:
            console.print(f"    {error}")
        if not valid:
            sys.exit(1)

    with command_context(config_dir, "adding to denylist") as (client, config):
        added = 0
        skipped = 0
        failed = 0
        added_domains: list[str] = []

        for domain in valid:
            success, was_added = client.block(domain)
            if success:
                if was_added:
                    console.print(f"  [green]+[/green] {domain}")
                    added += 1
                    added_domains.append(domain)
                else:
                    console.print(f"  [yellow]~[/yellow] {domain} [dim](already exists)[/dim]")
                    skipped += 1
            else:
                console.print(f"  [red]x[/red] {domain} [dim](failed)[/dim]")
                failed += 1

        # Build summary message
        parts = []
        if added > 0:
            parts.append(f"added {added}")
        if skipped > 0:
            parts.append(f"skipped {skipped} (duplicates)")
        if failed > 0:
            parts.append(f"failed {failed}")
        summary = ", ".join(parts) if parts else "no changes"
        console.print(f"\n  {summary.capitalize()}\n")

        if added > 0:
            audit_log("DENYLIST_ADD", f"Added {added} domains: {', '.join(valid)}")
            # Send notifications for each blocked domain
            for domain in added_domains:
                send_notification(EventType.BLOCK, domain, config)

        if failed > 0:
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
    with command_context(config_dir, "removing from denylist") as (client, config):
        removed = 0
        not_found = 0
        failed = 0
        removed_domains: list[str] = []

        for domain in domains:
            success, was_removed = client.unblock(domain)
            if success:
                if was_removed:
                    console.print(f"  [green]-[/green] {domain}")
                    removed += 1
                    removed_domains.append(domain)
                else:
                    console.print(f"  [yellow]?[/yellow] {domain} [dim](not found)[/dim]")
                    not_found += 1
            else:
                console.print(f"  [red]x[/red] {domain} [dim](failed)[/dim]")
                failed += 1

        # Build summary message
        parts = []
        if removed > 0:
            parts.append(f"removed {removed}")
        if not_found > 0:
            parts.append(f"not found {not_found}")
        if failed > 0:
            parts.append(f"failed {failed}")
        summary = ", ".join(parts) if parts else "no changes"
        console.print(f"\n  {summary.capitalize()}\n")

        if removed > 0:
            audit_log("DENYLIST_REMOVE", f"Removed {removed} domains: {', '.join(domains)}")
            # Send notifications for each unblocked domain
            for domain in removed_domains:
                send_notification(EventType.UNBLOCK, domain, config)


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
    with command_context(config_dir, "fetching allowlist") as (client, _config):
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
    with command_context(config_dir, "exporting allowlist") as (client, _config):
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
    except (
        PermissionError,
        FileNotFoundError,
        json.JSONDecodeError,
        csv.Error,
        UnicodeDecodeError,
    ) as e:
        handle_error(e, "reading import file")

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

    with command_context(config_dir, "importing to allowlist") as (client, _config):
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

            success, was_added = client.allow(domain)
            if success and was_added:
                added += 1
            elif success:
                skipped += 1  # Already exists (shouldn't happen due to check above)
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
    valid, invalid = _validate_domains(list(domains))

    if invalid:
        console.print("\n  [red]Invalid domains:[/red]")
        for error in invalid:
            console.print(f"    {error}")
        if not valid:
            sys.exit(1)

    with command_context(config_dir, "adding to allowlist") as (client, config):
        added = 0
        skipped = 0
        failed = 0
        added_domains: list[str] = []

        for domain in valid:
            success, was_added = client.allow(domain)
            if success:
                if was_added:
                    console.print(f"  [green]+[/green] {domain}")
                    added += 1
                    added_domains.append(domain)
                else:
                    console.print(f"  [yellow]~[/yellow] {domain} [dim](already exists)[/dim]")
                    skipped += 1
            else:
                console.print(f"  [red]x[/red] {domain} [dim](failed)[/dim]")
                failed += 1

        # Build summary message
        parts = []
        if added > 0:
            parts.append(f"added {added}")
        if skipped > 0:
            parts.append(f"skipped {skipped} (duplicates)")
        if failed > 0:
            parts.append(f"failed {failed}")
        summary = ", ".join(parts) if parts else "no changes"
        console.print(f"\n  {summary.capitalize()}\n")

        if added > 0:
            audit_log("ALLOWLIST_ADD", f"Added {added} domains: {', '.join(valid)}")
            # Send notifications for each allowed domain
            for domain in added_domains:
                send_notification(EventType.ALLOW, domain, config)

        if failed > 0:
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
    with command_context(config_dir, "removing from allowlist") as (client, config):
        removed = 0
        not_found = 0
        failed = 0
        removed_domains: list[str] = []

        for domain in domains:
            success, was_removed = client.disallow(domain)
            if success:
                if was_removed:
                    console.print(f"  [green]-[/green] {domain}")
                    removed += 1
                    removed_domains.append(domain)
                else:
                    console.print(f"  [yellow]?[/yellow] {domain} [dim](not found)[/dim]")
                    not_found += 1
            else:
                console.print(f"  [red]x[/red] {domain} [dim](failed)[/dim]")
                failed += 1

        # Build summary message
        parts = []
        if removed > 0:
            parts.append(f"removed {removed}")
        if not_found > 0:
            parts.append(f"not found {not_found}")
        if failed > 0:
            parts.append(f"failed {failed}")
        summary = ", ".join(parts) if parts else "no changes"
        console.print(f"\n  {summary.capitalize()}\n")

        if removed > 0:
            audit_log("ALLOWLIST_REMOVE", f"Removed {removed} domains: {', '.join(domains)}")
            # Send notifications for each disallowed domain
            for domain in removed_domains:
                send_notification(EventType.DISALLOW, domain, config)


# =============================================================================
# REGISTRATION
# =============================================================================


def register_denylist(main: click.Group) -> None:
    """Register the denylist command group with the main CLI."""
    main.add_command(denylist_cli)


def register_allowlist(main: click.Group) -> None:
    """Register the allowlist command group with the main CLI."""
    main.add_command(allowlist_cli)
