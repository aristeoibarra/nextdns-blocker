"""E2E tests for the update command.

Tests the update command including:
- Checking PyPI for latest version
- Comparing versions
- Update confirmation
- Homebrew, pipx, and pip update execution
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nextdns_blocker.cli import main


class TestUpdateVersionCheck:
    """Tests for update command version checking."""

    def test_update_shows_current_and_latest_version(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update shows current and latest versions."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                result = runner.invoke(main, ["update"], input="n\n")

        assert result.exit_code == 0
        assert "Current version: 1.0.0" in result.output
        assert "Latest version:  2.0.0" in result.output

    def test_update_reports_already_latest(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update reports when already on latest version."""
        pypi_response = json.dumps({"info": {"version": "1.0.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                result = runner.invoke(main, ["update"])

        assert result.exit_code == 0
        assert "already on the latest version" in result.output.lower()

    def test_update_handles_pypi_error(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update handles PyPI fetch errors gracefully."""
        import urllib.error

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Network error")

            result = runner.invoke(main, ["update"])

        assert result.exit_code != 0
        assert "error" in result.output.lower()


class TestUpdateConfirmation:
    """Tests for update command confirmation."""

    def test_update_asks_for_confirmation(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update asks for confirmation before updating."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                result = runner.invoke(main, ["update"], input="n\n")

        assert result.exit_code == 0
        assert "Do you want to update" in result.output
        assert "cancelled" in result.output.lower()

    def test_update_skips_confirmation_with_yes_flag(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update skips confirmation with --yes flag."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process):
                    with patch(
                        "nextdns_blocker.cli.get_executable_path",
                        return_value="/usr/local/bin/nextdns-blocker",
                    ):
                        result = runner.invoke(main, ["update", "--yes"])

        assert result.exit_code == 0
        # Should not ask for confirmation
        assert "Do you want to update" not in result.output


class TestUpdateExecution:
    """Tests for update command execution."""

    def test_update_uses_pipx_when_detected(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update uses pipx when installation is detected as pipx."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        pipx_venv = tmp_path / ".local" / "pipx" / "venvs" / "nextdns-blocker"
        pipx_venv.mkdir(parents=True)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process) as mock_run:
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value=str(pipx_venv / "bin" / "nextdns-blocker"),
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "pipx" in result.output.lower()

        # Verify pipx upgrade was called
        calls = [str(call) for call in mock_run.call_args_list]
        pipx_call = any("pipx" in str(call) and "upgrade" in str(call) for call in calls)
        assert pipx_call

    def test_update_uses_pip_when_not_pipx(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update uses pip when not installed via pipx."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process) as mock_run:
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "pip" in result.output.lower()

        # Verify pip install --upgrade was called
        calls = [str(call) for call in mock_run.call_args_list]
        pip_call = any("pip" in str(call) and "upgrade" in str(call) for call in calls)
        assert pip_call

    def test_update_uses_homebrew_when_detected_via_homebrew_path(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update uses brew when installation is detected via /homebrew/ path."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process) as mock_run:
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/opt/homebrew/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "homebrew" in result.output.lower()

        # Verify brew upgrade was called
        calls = [str(call) for call in mock_run.call_args_list]
        brew_call = any("brew" in str(call) and "upgrade" in str(call) for call in calls)
        assert brew_call

    def test_update_uses_homebrew_when_detected_via_cellar_path(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update uses brew when installation is detected via /Cellar/ path."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process) as mock_run:
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/Cellar/nextdns-blocker/6.0.0/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "homebrew" in result.output.lower()

        # Verify brew upgrade was called
        calls = [str(call) for call in mock_run.call_args_list]
        brew_call = any("brew" in str(call) and "upgrade" in str(call) for call in calls)
        assert brew_call

    def test_update_homebrew_takes_priority_over_pipx(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that Homebrew detection takes priority over pipx when both could match."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        # Create pipx venv directory (but Homebrew should still win)
        pipx_venv = tmp_path / ".local" / "pipx" / "venvs" / "nextdns-blocker"
        pipx_venv.mkdir(parents=True)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process) as mock_run:
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/opt/homebrew/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "homebrew" in result.output.lower()
        assert "pipx" not in result.output.lower()

        # Verify brew upgrade was called, not pipx
        calls = [str(call) for call in mock_run.call_args_list]
        brew_call = any("brew" in str(call) and "upgrade" in str(call) for call in calls)
        pipx_call = any("pipx" in str(call) and "upgrade" in str(call) for call in calls)
        assert brew_call
        assert not pipx_call

    def test_update_handles_update_failure(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update handles update command failure."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Permission denied"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process):
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code != 0
        assert "failed" in result.output.lower()


class TestUpdateVersionComparison:
    """Tests for update command version comparison."""

    def test_update_handles_dev_version_ahead(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update handles dev version ahead of PyPI."""
        pypi_response = json.dumps({"info": {"version": "1.0.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            # Dev version is ahead of PyPI
            with patch("nextdns_blocker.cli.__version__", "1.1.0"):
                result = runner.invoke(main, ["update"])

        assert result.exit_code == 0
        assert "already on the latest version" in result.output.lower()

    def test_update_compares_semantic_versions(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that update correctly compares semantic versions."""
        pypi_response = json.dumps({"info": {"version": "1.10.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            # 1.2.0 should be less than 1.10.0
            with patch("nextdns_blocker.cli.__version__", "1.2.0"):
                result = runner.invoke(main, ["update"], input="n\n")

        assert result.exit_code == 0
        assert "new version is available" in result.output.lower()


class TestUpdateSuccess:
    """Tests for successful update flow."""

    def test_update_shows_success_message(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that update shows success message after updating."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("nextdns_blocker.cli.__version__", "1.0.0"):
                with patch("subprocess.run", return_value=mock_process):
                    with patch("pathlib.Path.home", return_value=tmp_path):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "Successfully updated" in result.output
        assert "2.0.0" in result.output
        assert "restart" in result.output.lower()
