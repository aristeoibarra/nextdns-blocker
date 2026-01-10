"""Tests for the __main__.py entry point module."""

from click.testing import CliRunner


def test_main_module_imports():
    """Test that __main__ module can be imported without errors."""
    from nextdns_blocker import __main__

    # Verify main function exists
    assert hasattr(__main__, "main")

    # Verify register_watchdog was called (watchdog should be registered)
    from nextdns_blocker.cli import main

    # Check that watchdog command is registered
    assert "watchdog" in main.commands


def test_main_module_has_main_function():
    """Test that the main function is callable."""
    from nextdns_blocker.__main__ import main

    assert callable(main)


def test_cli_help_via_click_runner():
    """Test running the CLI with --help works via Click runner."""
    from nextdns_blocker.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "NextDNS Blocker" in result.output


def test_cli_version_via_click_runner():
    """Test running the CLI with --version works via Click runner."""
    from nextdns_blocker.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "nextdns-blocker" in result.output


def test_watchdog_subcommand_registered():
    """Test that watchdog subcommand is properly registered."""
    from nextdns_blocker.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["watchdog", "--help"])
    assert result.exit_code == 0
    assert "Watchdog commands" in result.output


def test_main_invocation_without_command():
    """Test invoking main without a subcommand shows help."""
    from nextdns_blocker.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    # Should show help with available commands
    assert "Commands:" in result.output or "Usage:" in result.output


def test_all_subcommands_available():
    """Test that all expected subcommands are registered."""
    from nextdns_blocker.__main__ import main

    expected_commands = [
        "init",
        "config",  # sync and validate are now under config
        "status",
        "pause",
        "resume",
        "unblock",
        "allow",
        "disallow",
        "health",
        "stats",
        "watchdog",
    ]

    for cmd in expected_commands:
        assert cmd in main.commands, f"Command '{cmd}' not found in CLI"
