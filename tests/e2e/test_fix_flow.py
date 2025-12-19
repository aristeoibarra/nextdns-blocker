"""E2E tests for the fix command.

Tests the fix command including:
- Configuration verification
- Installation detection
- Scheduler reinstallation
- Sync execution after fix
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nextdns_blocker.cli import main


class TestFixBasic:
    """Tests for basic fix command functionality."""

    def test_fix_verifies_configuration(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix command verifies configuration first."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            "NEXTDNS_API_KEY=test-key\nNEXTDNS_PROFILE_ID=abc123\nTIMEZONE=UTC\n"
        )
        (config_dir / "config.json").write_text('{"blocklist": []}')

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": config_dir,
            }
            with patch("subprocess.run", return_value=mock_process):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Checking configuration" in result.output
        assert "Config: OK" in result.output

    def test_fix_fails_without_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix fails when configuration is missing."""
        from nextdns_blocker.exceptions import ConfigurationError

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("No configuration found")
            result = runner.invoke(main, ["fix"])

        assert result.exit_code != 0
        assert "Config" in result.output
        assert "FAILED" in result.output or "init" in result.output.lower()


class TestFixInstallationDetection:
    """Tests for fix command installation detection."""

    def test_fix_detects_pipx_installation(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix detects pipx installation."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/home/user/.local/pipx/venvs/nextdns-blocker/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Type: pipx" in result.output

    def test_fix_detects_module_installation(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix detects module installation."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="python -m nextdns_blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Type: module" in result.output


class TestFixSchedulerReinstall:
    """Tests for fix command scheduler reinstallation."""

    def test_fix_reinstalls_scheduler_linux(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix reinstalls scheduler on Linux."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process) as mock_run:
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Reinstalling scheduler" in result.output
        assert "Scheduler: OK" in result.output

        # Verify watchdog install was called
        calls = [str(call) for call in mock_run.call_args_list]
        watchdog_call = any("watchdog" in str(call) and "install" in str(call) for call in calls)
        assert watchdog_call

    def test_fix_reinstalls_scheduler_macos(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix reinstalls scheduler on macOS."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process) as mock_run:
                with patch("nextdns_blocker.cli.is_macos", return_value=True):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        # macOS should unload launchd jobs first
        calls = [str(call) for call in mock_run.call_args_list]
        launchctl_call = any("launchctl" in str(call) for call in calls)
        assert launchctl_call

    def test_fix_handles_scheduler_failure(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix handles scheduler reinstallation failure."""
        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = ""
        mock_success.stderr = ""

        mock_failure = MagicMock()
        mock_failure.returncode = 1
        mock_failure.stdout = ""
        mock_failure.stderr = "Failed to install scheduler"

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # Fail on watchdog install (typically the 2nd or 3rd call)
            if "watchdog" in str(args) and "install" in str(args):
                return mock_failure
            return mock_success

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", side_effect=side_effect):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code != 0
        assert "FAILED" in result.output


class TestFixSyncExecution:
    """Tests for fix command sync execution."""

    def test_fix_runs_sync_after_scheduler(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix runs sync after reinstalling scheduler."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process) as mock_run:
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Running sync" in result.output
        assert "Sync: OK" in result.output

        # Verify sync was called
        calls = [str(call) for call in mock_run.call_args_list]
        sync_call = any("sync" in str(call) for call in calls)
        assert sync_call

    def test_fix_handles_sync_timeout(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that fix handles sync timeout."""
        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = ""
        mock_success.stderr = ""

        def side_effect(*args, **kwargs):
            if "sync" in str(args):
                raise subprocess.TimeoutExpired(cmd="sync", timeout=60)
            return mock_success

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", side_effect=side_effect):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        # Should complete but show timeout for sync
        assert "Fix complete" in result.output
        assert "TIMEOUT" in result.output


class TestFixComplete:
    """Tests for complete fix workflow."""

    def test_fix_complete_workflow(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete fix workflow: verify → reinstall → sync."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with patch("nextdns_blocker.cli.load_config") as mock_load:
            mock_load.return_value = {
                "api_key": "test-key",
                "profile_id": "abc123",
                "timeout": 30,
                "retries": 3,
                "timezone": "UTC",
                "script_dir": tmp_path,
            }
            with patch("subprocess.run", return_value=mock_process):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch(
                            "nextdns_blocker.cli.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "[1/5] Checking configuration" in result.output
        assert "[2/5] Detecting installation" in result.output
        assert "[3/5] Reinstalling scheduler" in result.output
        assert "[4/5] Running sync" in result.output
        assert "[5/5] Checking shell completion" in result.output
        assert "Fix complete" in result.output
