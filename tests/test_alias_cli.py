"""Tests for alias CLI commands."""

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from nextdns_blocker.alias_cli import (
    ALIAS_MARKER_END,
    ALIAS_MARKER_START,
    _detect_shell,
    _find_existing_alias,
    _generate_alias_block,
    _generate_alias_line,
    _get_shell_config_path,
    _install_alias,
    _remove_alias_block,
    _uninstall_alias,
    _validate_alias_name,
    alias_cli,
)


class TestValidateAliasName:
    """Tests for alias name validation."""

    def test_valid_names(self) -> None:
        """Test that valid alias names are accepted."""
        valid_names = ["ndb", "ndns", "block", "my_alias", "my-alias", "NDB", "ndb123"]
        for name in valid_names:
            assert _validate_alias_name(name), f"'{name}' should be valid"

    def test_invalid_names(self) -> None:
        """Test that invalid alias names are rejected."""
        invalid_names = [
            "n",  # Too short
            "123abc",  # Starts with number
            "-alias",  # Starts with dash
            "_alias",  # Starts with underscore
            "my alias",  # Contains space
            "alias!",  # Contains special char
            "a" * 25,  # Too long
            "",  # Empty
        ]
        for name in invalid_names:
            assert not _validate_alias_name(name), f"'{name}' should be invalid"


class TestDetectShell:
    """Tests for shell detection."""

    def test_detect_zsh(self) -> None:
        """Test detection of zsh shell."""
        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch("nextdns_blocker.alias_cli.is_windows", return_value=False):
                assert _detect_shell() == "zsh"

    def test_detect_bash(self) -> None:
        """Test detection of bash shell."""
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            with patch("nextdns_blocker.alias_cli.is_windows", return_value=False):
                assert _detect_shell() == "bash"

    def test_detect_fish(self) -> None:
        """Test detection of fish shell."""
        with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}):
            with patch("nextdns_blocker.alias_cli.is_windows", return_value=False):
                assert _detect_shell() == "fish"

    def test_detect_powershell_on_windows(self) -> None:
        """Test detection of PowerShell on Windows."""
        with patch("nextdns_blocker.alias_cli.is_windows", return_value=True):
            assert _detect_shell() == "powershell"

    def test_fallback_to_zsh_on_macos(self) -> None:
        """Test fallback to zsh on macOS when SHELL not set."""
        with patch.dict(os.environ, {"SHELL": ""}):
            with patch("nextdns_blocker.alias_cli.is_windows", return_value=False):
                with patch("nextdns_blocker.alias_cli.is_macos", return_value=True):
                    assert _detect_shell() == "zsh"


class TestGenerateAliasLine:
    """Tests for alias line generation."""

    def test_bash_alias(self) -> None:
        """Test bash alias generation."""
        result = _generate_alias_line("ndb", "bash")
        assert result == "alias ndb='nextdns-blocker'"

    def test_zsh_alias(self) -> None:
        """Test zsh alias generation."""
        result = _generate_alias_line("ndb", "zsh")
        assert result == "alias ndb='nextdns-blocker'"

    def test_fish_alias(self) -> None:
        """Test fish alias generation."""
        result = _generate_alias_line("ndb", "fish")
        assert result == "alias ndb 'nextdns-blocker'"

    def test_powershell_alias(self) -> None:
        """Test PowerShell alias generation."""
        result = _generate_alias_line("ndb", "powershell")
        assert result == "Set-Alias -Name ndb -Value nextdns-blocker"


class TestGenerateAliasBlock:
    """Tests for alias block generation."""

    def test_block_contains_markers(self) -> None:
        """Test that alias block contains markers."""
        block = _generate_alias_block("ndb", "bash")
        assert ALIAS_MARKER_START in block
        assert ALIAS_MARKER_END in block
        assert "alias ndb='nextdns-blocker'" in block


class TestRemoveAliasBlock:
    """Tests for alias block removal."""

    def test_remove_block(self) -> None:
        """Test removal of alias block from content."""
        content = f"""# Some config
export PATH="/usr/local/bin:$PATH"

{ALIAS_MARKER_START}
alias ndb='nextdns-blocker'
{ALIAS_MARKER_END}

# More config
"""
        result = _remove_alias_block(content)
        assert ALIAS_MARKER_START not in result
        assert ALIAS_MARKER_END not in result
        assert "ndb" not in result
        assert "Some config" in result
        assert "More config" in result

    def test_no_block_to_remove(self) -> None:
        """Test when there's no block to remove."""
        content = "# Some config\nexport PATH=/usr/local/bin\n"
        result = _remove_alias_block(content)
        assert result == content


class TestFindExistingAlias:
    """Tests for finding existing aliases."""

    def test_find_bash_alias(self, tmp_path: Path) -> None:
        """Test finding bash/zsh alias."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"{ALIAS_MARKER_START}\nalias ndb='nextdns-blocker'\n{ALIAS_MARKER_END}\n"
        )
        assert _find_existing_alias(config_file) == "ndb"

    def test_find_powershell_alias(self, tmp_path: Path) -> None:
        """Test finding PowerShell alias."""
        config_file = tmp_path / "profile.ps1"
        config_file.write_text(
            f"{ALIAS_MARKER_START}\nSet-Alias -Name ndns -Value nextdns-blocker\n{ALIAS_MARKER_END}\n"
        )
        assert _find_existing_alias(config_file) == "ndns"

    def test_no_alias_found(self, tmp_path: Path) -> None:
        """Test when no alias is found."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# Just some config\n")
        assert _find_existing_alias(config_file) is None

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test when config file doesn't exist."""
        config_file = tmp_path / ".bashrc"
        assert _find_existing_alias(config_file) is None


class TestInstallAlias:
    """Tests for alias installation."""

    def test_install_new_alias(self, tmp_path: Path) -> None:
        """Test installing a new alias."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# Existing config\n")

        success, message = _install_alias("ndb", "bash", config_file)

        assert success
        assert "ndb" in message
        content = config_file.read_text()
        assert ALIAS_MARKER_START in content
        assert "alias ndb='nextdns-blocker'" in content

    def test_install_creates_file(self, tmp_path: Path) -> None:
        """Test installing alias creates file if it doesn't exist."""
        config_file = tmp_path / ".bashrc"

        success, message = _install_alias("ndb", "bash", config_file)

        assert success
        assert config_file.exists()
        content = config_file.read_text()
        assert "alias ndb='nextdns-blocker'" in content

    def test_install_replaces_existing(self, tmp_path: Path) -> None:
        """Test installing alias replaces existing one."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# Config\n{ALIAS_MARKER_START}\nalias old='nextdns-blocker'\n{ALIAS_MARKER_END}\n"
        )

        success, message = _install_alias("new", "bash", config_file)

        assert success
        content = config_file.read_text()
        assert "alias new='nextdns-blocker'" in content
        assert "alias old" not in content

    def test_install_same_alias(self, tmp_path: Path) -> None:
        """Test installing same alias returns success without changes."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"{ALIAS_MARKER_START}\nalias ndb='nextdns-blocker'\n{ALIAS_MARKER_END}\n"
        )

        success, message = _install_alias("ndb", "bash", config_file)

        assert success
        assert "already installed" in message


class TestUninstallAlias:
    """Tests for alias uninstallation."""

    def test_uninstall_existing(self, tmp_path: Path) -> None:
        """Test uninstalling existing alias."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# Config\n{ALIAS_MARKER_START}\nalias ndb='nextdns-blocker'\n{ALIAS_MARKER_END}\n# More\n"
        )

        success, message = _uninstall_alias(config_file)

        assert success
        content = config_file.read_text()
        assert ALIAS_MARKER_START not in content
        assert "ndb" not in content
        assert "# Config" in content
        assert "# More" in content

    def test_uninstall_no_alias(self, tmp_path: Path) -> None:
        """Test uninstalling when no alias exists."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# Config\n")

        success, message = _uninstall_alias(config_file)

        assert not success
        assert "No nextdns-blocker alias found" in message

    def test_uninstall_file_not_exists(self, tmp_path: Path) -> None:
        """Test uninstalling when file doesn't exist."""
        config_file = tmp_path / ".bashrc"

        success, message = _uninstall_alias(config_file)

        assert not success
        assert "not found" in message


class TestAliasCLI:
    """Tests for alias CLI commands."""

    def test_install_command(self, tmp_path: Path) -> None:
        """Test alias install command."""
        config_file = tmp_path / ".bashrc"

        runner = CliRunner()
        with patch("nextdns_blocker.alias_cli._detect_shell", return_value="bash"):
            with patch(
                "nextdns_blocker.alias_cli._get_shell_config_path", return_value=config_file
            ):
                result = runner.invoke(alias_cli, ["install", "ndb"])

        assert result.exit_code == 0
        assert "ndb" in result.output
        assert config_file.exists()

    def test_install_invalid_name(self) -> None:
        """Test alias install with invalid name."""
        runner = CliRunner()
        result = runner.invoke(alias_cli, ["install", "123"])

        assert result.exit_code == 1
        assert "Invalid alias name" in result.output

    def test_uninstall_command(self, tmp_path: Path) -> None:
        """Test alias uninstall command."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"{ALIAS_MARKER_START}\nalias ndb='nextdns-blocker'\n{ALIAS_MARKER_END}\n"
        )

        runner = CliRunner()
        with patch("nextdns_blocker.alias_cli._detect_shell", return_value="bash"):
            with patch(
                "nextdns_blocker.alias_cli._get_shell_config_path", return_value=config_file
            ):
                result = runner.invoke(alias_cli, ["uninstall"])

        assert result.exit_code == 0
        assert "removed" in result.output.lower() or "Alias removed" in result.output

    def test_status_command_installed(self, tmp_path: Path) -> None:
        """Test alias status command when alias is installed."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"{ALIAS_MARKER_START}\nalias ndb='nextdns-blocker'\n{ALIAS_MARKER_END}\n"
        )

        runner = CliRunner()
        with patch("nextdns_blocker.alias_cli._detect_shell", return_value="bash"):
            with patch(
                "nextdns_blocker.alias_cli._get_shell_config_path", return_value=config_file
            ):
                result = runner.invoke(alias_cli, ["status"])

        assert result.exit_code == 0
        assert "ndb" in result.output
        assert "installed" in result.output.lower()

    def test_status_command_not_installed(self, tmp_path: Path) -> None:
        """Test alias status command when alias is not installed."""
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# No alias\n")

        runner = CliRunner()
        with patch("nextdns_blocker.alias_cli._detect_shell", return_value="bash"):
            with patch(
                "nextdns_blocker.alias_cli._get_shell_config_path", return_value=config_file
            ):
                result = runner.invoke(alias_cli, ["status"])

        assert result.exit_code == 0
        assert "not installed" in result.output.lower() or "No alias" in result.output


class TestGetShellConfigPath:
    """Tests for shell config path detection."""

    def test_bash_existing_bashrc(self, tmp_path: Path) -> None:
        """Test finding existing .bashrc."""
        bashrc = tmp_path / ".bashrc"
        bashrc.touch()

        with patch("nextdns_blocker.alias_cli.Path.home", return_value=tmp_path):
            result = _get_shell_config_path("bash")

        assert result == bashrc

    def test_zsh_existing_zshrc(self, tmp_path: Path) -> None:
        """Test finding existing .zshrc."""
        zshrc = tmp_path / ".zshrc"
        zshrc.touch()

        with patch("nextdns_blocker.alias_cli.Path.home", return_value=tmp_path):
            result = _get_shell_config_path("zsh")

        assert result == zshrc

    def test_fish_creates_path(self, tmp_path: Path) -> None:
        """Test fish config path (may not exist)."""
        with patch("nextdns_blocker.alias_cli.Path.home", return_value=tmp_path):
            result = _get_shell_config_path("fish")

        assert result is not None
        assert "fish" in str(result)
        assert "config.fish" in str(result)
