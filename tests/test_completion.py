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


class TestDetectShell:
    """Tests for shell detection."""

    def test_detect_shell_from_env_bash(self):
        """Test detecting bash from SHELL env."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            assert detect_shell() == "bash"

    def test_detect_shell_from_env_zsh(self):
        """Test detecting zsh from SHELL env."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/zsh"}):
            assert detect_shell() == "zsh"

    def test_detect_shell_from_env_fish(self):
        """Test detecting fish from SHELL env."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/usr/local/bin/fish"}):
            assert detect_shell() == "fish"

    def test_detect_shell_from_parent_process(self):
        """Test detecting shell from parent process."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/unsupported"}, clear=False):
            mock_result = MagicMock()
            mock_result.stdout = "zsh\n"
            with patch("subprocess.run", return_value=mock_result):
                assert detect_shell() == "zsh"

    def test_detect_shell_parent_with_dash_prefix(self):
        """Test detecting shell from parent process with dash prefix."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/unsupported"}, clear=False):
            mock_result = MagicMock()
            mock_result.stdout = "-bash\n"
            with patch("subprocess.run", return_value=mock_result):
                assert detect_shell() == "bash"

    def test_detect_shell_unsupported(self):
        """Test unsupported shell returns None."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/unsupported"}, clear=False):
            mock_result = MagicMock()
            mock_result.stdout = "unsupported\n"
            with patch("subprocess.run", return_value=mock_result):
                assert detect_shell() is None

    def test_detect_shell_subprocess_error(self):
        """Test that subprocess errors are handled gracefully."""
        from nextdns_blocker.completion import detect_shell

        with patch.dict("os.environ", {"SHELL": "/bin/unsupported"}, clear=False):
            with patch("subprocess.run", side_effect=OSError("Test error")):
                assert detect_shell() is None


class TestGetShellRcFile:
    """Tests for RC file path resolution."""

    def test_get_shell_rc_file_bash_bashrc_exists(self):
        """Test bash returns .bashrc when it exists."""
        from nextdns_blocker.completion import get_shell_rc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bashrc = home / ".bashrc"
            bashrc.touch()

            with patch.object(Path, "home", return_value=home):
                result = get_shell_rc_file("bash")
                assert result == bashrc

    def test_get_shell_rc_file_bash_profile_fallback(self):
        """Test bash falls back to .bash_profile."""
        from nextdns_blocker.completion import get_shell_rc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bash_profile = home / ".bash_profile"
            bash_profile.touch()

            with patch.object(Path, "home", return_value=home):
                result = get_shell_rc_file("bash")
                assert result == bash_profile

    def test_get_shell_rc_file_bash_creates_bashrc(self):
        """Test bash returns .bashrc path if neither exists."""
        from nextdns_blocker.completion import get_shell_rc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)

            with patch.object(Path, "home", return_value=home):
                result = get_shell_rc_file("bash")
                assert result == home / ".bashrc"

    def test_get_shell_rc_file_zsh(self):
        """Test zsh returns .zshrc."""
        from nextdns_blocker.completion import get_shell_rc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)

            with patch.object(Path, "home", return_value=home):
                result = get_shell_rc_file("zsh")
                assert result == home / ".zshrc"

    def test_get_shell_rc_file_fish(self):
        """Test fish returns completions file."""
        from nextdns_blocker.completion import get_shell_rc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)

            with patch.object(Path, "home", return_value=home):
                result = get_shell_rc_file("fish")
                assert result == home / ".config" / "fish" / "completions" / "nextdns-blocker.fish"

    def test_get_shell_rc_file_unsupported(self):
        """Test unsupported shell returns None."""
        from nextdns_blocker.completion import get_shell_rc_file

        result = get_shell_rc_file("powershell")
        assert result is None


class TestIsCompletionInstalled:
    """Tests for completion installation check."""

    def test_is_completion_installed_no_rc_file(self):
        """Test returns False when RC file doesn't exist."""
        from nextdns_blocker.completion import is_completion_installed

        with patch(
            "nextdns_blocker.completion.get_shell_rc_file", return_value=Path("/nonexistent")
        ):
            assert is_completion_installed("bash") is False

    def test_is_completion_installed_with_marker(self):
        """Test returns True when marker is present."""
        from nextdns_blocker.completion import COMPLETION_MARKER, is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.write_text(f"# some config\n{COMPLETION_MARKER}\neval ...\n")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                assert is_completion_installed("bash") is True

    def test_is_completion_installed_bash_line(self):
        """Test returns True when bash completion line is present."""
        from nextdns_blocker.completion import COMPLETION_LINE_BASH, is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.write_text(f"# some config\n{COMPLETION_LINE_BASH}\n")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                assert is_completion_installed("bash") is True

    def test_is_completion_installed_zsh_line(self):
        """Test returns True when zsh completion line is present."""
        from nextdns_blocker.completion import COMPLETION_LINE_ZSH, is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".zshrc"
            rc_file.write_text(f"# some config\n{COMPLETION_LINE_ZSH}\n")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                assert is_completion_installed("zsh") is True

    def test_is_completion_installed_fish_line(self):
        """Test returns True when fish completion line is present."""
        from nextdns_blocker.completion import COMPLETION_LINE_FISH, is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / "nextdns-blocker.fish"
            rc_file.write_text(f"# some config\n{COMPLETION_LINE_FISH}\n")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                assert is_completion_installed("fish") is True

    def test_is_completion_installed_not_installed(self):
        """Test returns False when completion is not installed."""
        from nextdns_blocker.completion import is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.write_text("# some other config\n")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                assert is_completion_installed("bash") is False

    def test_is_completion_installed_read_error(self):
        """Test returns False on read error."""
        from nextdns_blocker.completion import is_completion_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.touch()

            with (
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
                patch.object(Path, "read_text", side_effect=OSError("Test error")),
            ):
                assert is_completion_installed("bash") is False


class TestInstallCompletion:
    """Tests for completion installation."""

    def test_install_completion_already_installed(self):
        """Test returns success message when already installed."""
        from nextdns_blocker.completion import install_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"

            with (
                patch("nextdns_blocker.completion.is_completion_installed", return_value=True),
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
            ):
                success, message = install_completion("bash")
                assert success is True
                assert "Already installed" in message

    def test_install_completion_bash(self):
        """Test installing bash completion."""
        from nextdns_blocker.completion import COMPLETION_LINE_BASH, install_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.write_text("# existing config\n")

            with (
                patch("nextdns_blocker.completion.is_completion_installed", return_value=False),
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
            ):
                success, message = install_completion("bash")
                assert success is True
                assert "Installed" in message

                content = rc_file.read_text()
                assert COMPLETION_LINE_BASH in content

    def test_install_completion_fish(self):
        """Test installing fish completion."""
        from nextdns_blocker.completion import COMPLETION_LINE_FISH, install_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            fish_dir = Path(tmpdir) / ".config" / "fish" / "completions"
            rc_file = fish_dir / "nextdns-blocker.fish"

            with (
                patch("nextdns_blocker.completion.is_completion_installed", return_value=False),
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
            ):
                success, message = install_completion("fish")
                assert success is True
                assert "Installed" in message

                content = rc_file.read_text()
                assert COMPLETION_LINE_FISH in content

    def test_install_completion_no_rc_file(self):
        """Test failure when RC file cannot be determined."""
        from nextdns_blocker.completion import install_completion

        with (
            patch("nextdns_blocker.completion.is_completion_installed", return_value=False),
            patch("nextdns_blocker.completion.get_shell_rc_file", return_value=None),
        ):
            success, message = install_completion("bash")
            assert success is False
            assert "Could not determine RC file" in message

    def test_install_completion_permission_error(self):
        """Test failure on permission error."""
        from nextdns_blocker.completion import install_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"

            with (
                patch("nextdns_blocker.completion.is_completion_installed", return_value=False),
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
                patch("builtins.open", side_effect=PermissionError("Test error")),
            ):
                success, message = install_completion("bash")
                assert success is False
                assert "Permission denied" in message


class TestUninstallCompletion:
    """Tests for completion uninstallation."""

    def test_uninstall_completion_no_rc_file(self):
        """Test uninstall when RC file doesn't exist."""
        from nextdns_blocker.completion import uninstall_completion

        with patch(
            "nextdns_blocker.completion.get_shell_rc_file", return_value=Path("/nonexistent")
        ):
            success, message = uninstall_completion("bash")
            assert success is True
            assert "Nothing to remove" in message

    def test_uninstall_completion_fish(self):
        """Test uninstalling fish completion."""
        from nextdns_blocker.completion import uninstall_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / "nextdns-blocker.fish"
            rc_file.write_text("# completion")

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                success, message = uninstall_completion("fish")
                assert success is True
                assert "Removed" in message
                assert not rc_file.exists()

    def test_uninstall_completion_bash(self):
        """Test uninstalling bash completion."""
        from nextdns_blocker.completion import (
            COMPLETION_LINE_BASH,
            COMPLETION_MARKER,
            uninstall_completion,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.write_text(
                f"# existing config\n{COMPLETION_MARKER}\n{COMPLETION_LINE_BASH}\n# more config\n"
            )

            with patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file):
                success, message = uninstall_completion("bash")
                assert success is True
                assert "Removed from" in message

                content = rc_file.read_text()
                assert COMPLETION_MARKER not in content
                assert COMPLETION_LINE_BASH not in content
                assert "# existing config" in content
                assert "# more config" in content

    def test_uninstall_completion_permission_error(self):
        """Test failure on permission error."""
        from nextdns_blocker.completion import uninstall_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            rc_file = Path(tmpdir) / ".bashrc"
            rc_file.touch()

            with (
                patch("nextdns_blocker.completion.get_shell_rc_file", return_value=rc_file),
                patch.object(Path, "read_text", side_effect=PermissionError("Test error")),
            ):
                success, message = uninstall_completion("bash")
                assert success is False
                assert "Permission denied" in message


class TestBlocklistCompletionWithEnvFile:
    """Tests for blocklist completion with .env file."""

    def test_reads_script_dir_from_env_file(self, mock_blocklist, mock_allowlist):
        """Test that completion reads NEXTDNS_SCRIPT_DIR from .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")
            env_file = config_dir / ".env"
            env_file.write_text('NEXTDNS_SCRIPT_DIR="/custom/path"\n')

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    return_value=(mock_blocklist, mock_allowlist),
                ) as mock_load,
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                complete_blocklist_domains(ctx, param, "")

                mock_load.assert_called_once_with("/custom/path")


class TestBlocklistCompletionExceptionHandlers:
    """Tests for blocklist completion exception handlers."""

    def test_handles_file_not_found_error(self):
        """Test FileNotFoundError returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=FileNotFoundError("Test"),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "")
                assert results == []

    def test_handles_json_decode_error(self):
        """Test JSONDecodeError returns empty list."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=json.JSONDecodeError("Test", "doc", 0),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "")
                assert results == []

    def test_handles_key_error(self):
        """Test KeyError returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=KeyError("Test"),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "")
                assert results == []

    def test_handles_type_error(self):
        """Test TypeError returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=TypeError("Test"),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_blocklist_domains(ctx, param, "")
                assert results == []


class TestAllowlistCompletionExceptionHandlers:
    """Tests for allowlist completion exception handlers."""

    def test_handles_file_not_found_error(self):
        """Test FileNotFoundError returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=FileNotFoundError("Test"),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "")
                assert results == []

    def test_handles_json_decode_error(self):
        """Test JSONDecodeError returns empty list."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=json.JSONDecodeError("Test", "doc", 0),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "")
                assert results == []

    def test_handles_key_error(self):
        """Test KeyError returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text("{}")

            with (
                patch("nextdns_blocker.config.get_config_dir", return_value=config_dir),
                patch(
                    "nextdns_blocker.config.load_domains",
                    side_effect=KeyError("Test"),
                ),
            ):
                ctx = MagicMock(spec=click.Context)
                param = MagicMock(spec=click.Parameter)

                results = complete_allowlist_domains(ctx, param, "")
                assert results == []


class TestPendingCompletionExceptionHandlers:
    """Tests for pending action completion exception handlers."""

    def test_handles_file_not_found_error(self):
        """Test FileNotFoundError returns empty list."""
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            side_effect=FileNotFoundError("Test"),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")
            assert results == []

    def test_handles_json_decode_error(self):
        """Test JSONDecodeError returns empty list."""
        import json

        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            side_effect=json.JSONDecodeError("Test", "doc", 0),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")
            assert results == []

    def test_handles_key_error(self):
        """Test KeyError returns empty list."""
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            side_effect=KeyError("Test"),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")
            assert results == []

    def test_handles_type_error(self):
        """Test TypeError returns empty list."""
        with patch(
            "nextdns_blocker.pending.get_pending_actions",
            side_effect=TypeError("Test"),
        ):
            ctx = MagicMock(spec=click.Context)
            param = MagicMock(spec=click.Parameter)

            results = complete_pending_action_ids(ctx, param, "")
            assert results == []
