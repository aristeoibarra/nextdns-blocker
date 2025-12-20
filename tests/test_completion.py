"""Tests for shell completion functions."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.completion import (
    complete_allowlist_domains,
    complete_blocklist_domains,
    complete_pending_action_ids,
    get_completion_script,
)


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_blocklist():
    """Mock blocklist domains for completion tests."""
    return [
        {"domain": "reddit.com", "description": "Social media"},
        {"domain": "twitter.com", "description": "Social network"},
        {"domain": "facebook.com"},
    ]


@pytest.fixture
def mock_allowlist():
    """Mock allowlist domains for completion tests."""
    return [
        {"domain": "aws.amazon.com", "description": "AWS Console"},
        {"domain": "docs.google.com", "description": "Google Docs"},
    ]


@pytest.fixture
def mock_pending_actions():
    """Mock pending actions for completion tests."""
    return [
        {
            "id": "pnd_20251215_143022_abc123",
            "domain": "reddit.com",
            "status": "pending",
        },
        {
            "id": "pnd_20251215_150000_def456",
            "domain": "twitter.com",
            "status": "pending",
        },
        {
            "id": "pnd_20251214_120000_old789",
            "domain": "facebook.com",
            "status": "executed",
        },
    ]


class TestCompleteBlocklistDomains:
    """Tests for blocklist domain completion."""

    def test_returns_matching_domains(self, mock_blocklist, mock_allowlist):
        """Test that completion returns domains starting with incomplete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "red")

                assert len(results) == 1
                assert results[0].value == "reddit.com"
                assert results[0].help == "Social media"

    def test_returns_all_domains_for_empty_incomplete(self, mock_blocklist, mock_allowlist):
        """Test that empty incomplete returns all domains."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "")

                assert len(results) == 3
                domains = [r.value for r in results]
                assert "reddit.com" in domains
                assert "twitter.com" in domains
                assert "facebook.com" in domains

    def test_case_insensitive_matching(self, mock_blocklist, mock_allowlist):
        """Test that matching is case insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "RED")

                assert len(results) == 1
                assert results[0].value == "reddit.com"

    def test_returns_empty_on_no_match(self, mock_blocklist, mock_allowlist):
        """Test that non-matching incomplete returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "nonexistent")

                assert len(results) == 0

    def test_handles_missing_config(self):
        """Test that missing config returns empty list without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("nextdns_blocker.config.get_config_dir", return_value=Path(tmpdir)):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                # Should not raise, just return empty (no config.json)
                results = complete_blocklist_domains(ctx, param, "")

                assert results == []

    def test_handles_exception_gracefully(self):
        """Test that exceptions are caught and empty list returned."""
        # Use OSError which is one of the specifically caught exceptions
        with patch(
            "nextdns_blocker.config.get_config_dir",
            side_effect=OSError("Test error"),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_blocklist_domains(ctx, param, "test")

            assert results == []


class TestCompleteAllowlistDomains:
    """Tests for allowlist domain completion."""

    def test_returns_matching_allowlist_domains(self, mock_blocklist, mock_allowlist):
        """Test that completion returns allowlist domains starting with incomplete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "aws")

                assert len(results) == 1
                assert results[0].value == "aws.amazon.com"
                assert results[0].help == "AWS Console"

    def test_returns_all_allowlist_for_empty_incomplete(self, mock_blocklist, mock_allowlist):
        """Test that empty incomplete returns all allowlist domains."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "")

                assert len(results) == 2
                domains = [r.value for r in results]
                assert "aws.amazon.com" in domains
                assert "docs.google.com" in domains

    def test_handles_missing_allowlist(self, mock_blocklist):
        """Test that missing allowlist returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, []),  # Empty allowlist
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "")

                assert results == []


class TestCompletePendingActionIds:
    """Tests for pending action ID completion."""

    def test_returns_matching_action_ids(self, mock_pending_actions):
        """Test that completion returns action IDs starting with incomplete."""
        pending_only = [a for a in mock_pending_actions if a["status"] == "pending"]
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            return_value=pending_only,
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "pnd_20251215_143")

            assert len(results) == 1
            assert results[0].value == "pnd_20251215_143022_abc123"
            assert "reddit.com" in results[0].help

    def test_matches_by_suffix(self, mock_pending_actions):
        """Test that completion can match by suffix."""
        pending_only = [a for a in mock_pending_actions if a["status"] == "pending"]
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            return_value=pending_only,
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "abc")

            assert len(results) == 1
            assert results[0].value == "pnd_20251215_143022_abc123"

    def test_returns_all_pending_for_empty_incomplete(self, mock_pending_actions):
        """Test that empty incomplete returns all pending actions."""
        pending_only = [a for a in mock_pending_actions if a["status"] == "pending"]
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            return_value=pending_only,
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")

            assert len(results) == 2  # Only pending, not executed

    def test_handles_no_pending_actions(self):
        """Test that no pending actions returns empty list."""
        with patch("nextdns_blocker.pending.get_pending_actions", return_value=[]):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")

            assert results == []

    def test_handles_exception_gracefully(self):
        """Test that exceptions are caught and empty list returned."""
        # Use OSError which is one of the specifically caught exceptions
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            side_effect=OSError("Test error"),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "test")

            assert results == []


class TestGetCompletionScript:
    """Tests for completion script generation."""

    def test_bash_script(self):
        """Test that bash script is generated correctly."""
        script = get_completion_script("bash")

        assert "Bash completion" in script
        assert "_NEXTDNS_BLOCKER_COMPLETE=bash_source" in script
        assert "nextdns-blocker" in script

    def test_zsh_script(self):
        """Test that zsh script is generated correctly."""
        script = get_completion_script("zsh")

        assert "Zsh completion" in script
        assert "_NEXTDNS_BLOCKER_COMPLETE=zsh_source" in script
        assert "nextdns-blocker" in script

    def test_fish_script(self):
        """Test that fish script is generated correctly."""
        script = get_completion_script("fish")

        assert "Fish completion" in script
        assert "_NEXTDNS_BLOCKER_COMPLETE=fish_source" in script
        assert "nextdns-blocker" in script

    def test_unsupported_shell_raises_error(self):
        """Test that unsupported shell raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_completion_script("powershell")

        assert "Unsupported shell" in str(exc_info.value)


class TestCompletionCommand:
    """Tests for the completion CLI command."""

    def test_completion_bash(self, runner):
        """Test completion command outputs bash script."""
        result = runner.invoke(main, ["completion", "bash"])

        assert result.exit_code == 0
        assert "_NEXTDNS_BLOCKER_COMPLETE=bash_source" in result.output

    def test_completion_zsh(self, runner):
        """Test completion command outputs zsh script."""
        result = runner.invoke(main, ["completion", "zsh"])

        assert result.exit_code == 0
        assert "_NEXTDNS_BLOCKER_COMPLETE=zsh_source" in result.output

    def test_completion_fish(self, runner):
        """Test completion command outputs fish script."""
        result = runner.invoke(main, ["completion", "fish"])

        assert result.exit_code == 0
        assert "_NEXTDNS_BLOCKER_COMPLETE=fish_source" in result.output

    def test_completion_invalid_shell(self, runner):
        """Test completion command rejects invalid shell."""
        result = runner.invoke(main, ["completion", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_completion_help(self, runner):
        """Test completion command shows help."""
        result = runner.invoke(main, ["completion", "--help"])

        assert result.exit_code == 0
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output
