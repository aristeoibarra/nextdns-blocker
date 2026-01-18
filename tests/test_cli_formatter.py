"""Tests for CLI formatter utility."""

from unittest.mock import patch

from nextdns_blocker.cli_formatter import CLIOutput, out


class TestCLIOutput:
    """Tests for CLIOutput class."""

    def test_error_default_prefix(self):
        """Should print error with default 'Error' prefix."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.error("Something went wrong")
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "[red]Error: Something went wrong[/red]" in call_args

    def test_error_custom_prefix(self):
        """Should print error with custom prefix."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.error("Connection failed", prefix="API")
            call_args = mock_console.print.call_args[0][0]
            assert "[red]API: Connection failed[/red]" in call_args

    def test_warning_default_prefix(self):
        """Should print warning with default 'Warning' prefix."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.warning("This might cause issues")
            call_args = mock_console.print.call_args[0][0]
            assert "[yellow]Warning: This might cause issues[/yellow]" in call_args

    def test_warning_custom_prefix(self):
        """Should print warning with custom prefix."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.warning("Deprecated feature", prefix="Deprecation")
            call_args = mock_console.print.call_args[0][0]
            assert "[yellow]Deprecation: Deprecated feature[/yellow]" in call_args

    def test_success(self):
        """Should print success message in green."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.success("Operation completed")
            call_args = mock_console.print.call_args[0][0]
            assert "[green]Operation completed[/green]" in call_args

    def test_info(self):
        """Should print info message."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.info("Some information")
            call_args = mock_console.print.call_args[0][0]
            assert "Some information" in call_args

    def test_info_block(self):
        """Should print info message with newlines."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.info_block("Standalone message")
            call_args = mock_console.print.call_args[0][0]
            assert "Standalone message" in call_args
            assert call_args.startswith("\n")

    def test_item_added(self):
        """Should print added item with green plus."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_added("example.com")
            call_args = mock_console.print.call_args[0][0]
            assert "[green]+[/green]" in call_args
            assert "example.com" in call_args

    def test_item_removed(self):
        """Should print removed item with red minus."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_removed("example.com")
            call_args = mock_console.print.call_args[0][0]
            assert "[red]-[/red]" in call_args
            assert "example.com" in call_args

    def test_item_skipped_no_reason(self):
        """Should print skipped item with yellow tilde."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_skipped("example.com")
            call_args = mock_console.print.call_args[0][0]
            assert "[yellow]~[/yellow]" in call_args
            assert "example.com" in call_args

    def test_item_skipped_with_reason(self):
        """Should print skipped item with reason."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_skipped("example.com", reason="already exists")
            call_args = mock_console.print.call_args[0][0]
            assert "[yellow]~[/yellow]" in call_args
            assert "example.com" in call_args
            assert "(already exists)" in call_args

    def test_item_ok(self):
        """Should print item with green checkmark."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_ok("Config valid")
            call_args = mock_console.print.call_args[0][0]
            assert "[green]✓[/green]" in call_args
            assert "Config valid" in call_args

    def test_item_fail(self):
        """Should print item with red X mark."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_fail("API connection")
            call_args = mock_console.print.call_args[0][0]
            assert "[red]✗[/red]" in call_args
            assert "API connection" in call_args

    def test_header(self):
        """Should print bold header."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.header("Section Title")
            call_args = mock_console.print.call_args[0][0]
            assert "[bold]Section Title[/bold]" in call_args

    def test_divider(self):
        """Should print empty line as divider."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.divider()
            mock_console.print.assert_called_once_with()

    def test_key_value_default_color(self):
        """Should print key-value with default cyan color."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.key_value("Profile", "abc123")
            call_args = mock_console.print.call_args[0][0]
            assert "Profile" in call_args
            assert "[cyan]abc123[/cyan]" in call_args

    def test_key_value_custom_color(self):
        """Should print key-value with custom color."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.key_value("Status", "OK", color="green")
            call_args = mock_console.print.call_args[0][0]
            assert "[green]OK[/green]" in call_args

    def test_stat(self):
        """Should print statistic with label and value."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.stat("Blocks", 42, color="red")
            call_args = mock_console.print.call_args[0][0]
            assert "Blocks:" in call_args
            assert "[red]42[/red]" in call_args


class TestOutAlias:
    """Tests for the 'out' convenience alias."""

    def test_out_is_cli_output(self):
        """Should be an alias for CLIOutput."""
        assert out is CLIOutput

    def test_out_methods_work(self):
        """Should be able to call methods on out."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            out.success("It works!")
            mock_console.print.assert_called_once()


class TestOutputConsistency:
    """Tests for consistent output formatting."""

    def test_error_has_newlines(self):
        """Error messages should have surrounding newlines."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.error("Test")
            call_args = mock_console.print.call_args[0][0]
            assert call_args.startswith("\n")
            assert call_args.endswith("\n")

    def test_warning_has_newlines(self):
        """Warning messages should have surrounding newlines."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.warning("Test")
            call_args = mock_console.print.call_args[0][0]
            assert call_args.startswith("\n")
            assert call_args.endswith("\n")

    def test_success_has_newlines(self):
        """Success messages should have surrounding newlines."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.success("Test")
            call_args = mock_console.print.call_args[0][0]
            assert call_args.startswith("\n")
            assert call_args.endswith("\n")

    def test_info_has_indentation(self):
        """Info messages should have consistent indentation."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.info("Test")
            call_args = mock_console.print.call_args[0][0]
            assert call_args.startswith("  ")

    def test_items_have_indentation(self):
        """Item messages should have consistent indentation."""
        with patch("nextdns_blocker.cli_formatter.console") as mock_console:
            CLIOutput.item_added("test")
            call_args = mock_console.print.call_args[0][0]
            assert call_args.startswith("  ")
