"""PIN verification helper for CLI commands."""

import sys

import rich_click as click

from .cli_formatter import console
from .exceptions import EXIT_PIN_ERROR


def require_pin_verification(command_name: str) -> bool:
    """
    Check if PIN verification is required and prompt if needed.

    This function should be called at the start of dangerous commands.
    It will prompt for PIN if enabled and no valid session exists.

    Args:
        command_name: Name of the command being executed

    Returns:
        True if command can proceed, False if blocked

    Raises:
        SystemExit: If PIN verification fails
    """
    from .protection import (
        PIN_MAX_ATTEMPTS,
        get_failed_attempts_count,
        get_lockout_remaining,
        is_pin_enabled,
        is_pin_locked_out,
        is_pin_session_valid,
        verify_pin,
    )

    # No PIN protection = proceed
    if not is_pin_enabled():
        return True

    # Valid session = proceed
    if is_pin_session_valid():
        return True

    # Check lockout
    if is_pin_locked_out():
        remaining = get_lockout_remaining()
        console.print(
            f"\n  [red]PIN locked out due to failed attempts. Try again in {remaining}[/red]\n"
        )
        sys.exit(EXIT_PIN_ERROR)

    # Prompt for PIN
    console.print(f"\n  [yellow]PIN required for '{command_name}'[/yellow]")

    pin = click.prompt("  Enter PIN", hide_input=True, default="", show_default=False)

    if not pin:
        console.print("\n  [red]PIN verification cancelled[/red]\n")
        sys.exit(EXIT_PIN_ERROR)

    if verify_pin(pin):
        return True
    else:
        if is_pin_locked_out():
            remaining = get_lockout_remaining()
            console.print(f"\n  [red]Too many failed attempts. Locked out for {remaining}[/red]\n")
        else:
            attempts_left = PIN_MAX_ATTEMPTS - get_failed_attempts_count()
            console.print(f"\n  [red]Incorrect PIN. {attempts_left} attempts remaining.[/red]\n")
        sys.exit(EXIT_PIN_ERROR)
