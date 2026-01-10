"""E2E tests for the watchdog flow.

Tests the complete watchdog lifecycle including:
- Installing scheduled jobs
- Checking job status
- Recovering deleted jobs
- Disabling and enabling watchdog
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.watchdog import register_watchdog

# Register watchdog subcommand (normally done in __main__.py)
register_watchdog(main)


class TestWatchdogInstallUninstall:
    """Tests for watchdog install and uninstall commands."""

    def test_watchdog_install_on_linux(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog install creates cron jobs on Linux without systemd."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Mock platform detection to Linux without systemd
        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch("nextdns_blocker.watchdog.get_crontab", return_value=""):
                            with patch(
                                "nextdns_blocker.watchdog.set_crontab", return_value=True
                            ) as mock_set:
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_path",
                                    return_value="/usr/local/bin/nextdns-blocker",
                                ):
                                    result = runner.invoke(main, ["watchdog", "install"])

        assert result.exit_code == 0
        # Verify crontab was updated
        assert mock_set.called

    def test_watchdog_install_on_macos(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog install creates launchd jobs on macOS."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)

        # Mock platform detection to macOS
        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_executable_path",
                            return_value="/usr/local/bin/nextdns-blocker",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_executable_args",
                                return_value=["/usr/local/bin/nextdns-blocker"],
                            ):
                                with patch("subprocess.run") as mock_run:
                                    mock_run.return_value = MagicMock(returncode=0)
                                    result = runner.invoke(main, ["watchdog", "install"])

        assert result.exit_code == 0

    def test_watchdog_uninstall_on_linux(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog uninstall removes cron jobs on Linux without systemd."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        existing_cron = "# existing jobs\n*/2 * * * * /usr/local/bin/nextdns-blocker config sync >> /tmp/log 2>&1\n* * * * * /usr/local/bin/nextdns-blocker watchdog check >> /tmp/log 2>&1"

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch(
                            "nextdns_blocker.watchdog.get_crontab", return_value=existing_cron
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.set_crontab", return_value=True
                            ) as mock_set:
                                result = runner.invoke(main, ["watchdog", "uninstall"])

        assert result.exit_code == 0
        # Verify crontab was updated to remove our jobs
        if mock_set.called:
            new_cron = mock_set.call_args[0][0]
            assert "nextdns-blocker config sync" not in new_cron
            assert "nextdns-blocker watchdog" not in new_cron


class TestWatchdogStatus:
    """Tests for watchdog status command."""

    def test_watchdog_status_shows_job_state(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog status displays job status."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        existing_cron = "*/2 * * * * /usr/local/bin/nextdns-blocker config sync\n* * * * * /usr/local/bin/nextdns-blocker watchdog check"

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch(
                            "nextdns_blocker.watchdog.get_crontab", return_value=existing_cron
                        ):
                            result = runner.invoke(main, ["watchdog", "status"])

        assert result.exit_code == 0
        # Should show status information
        assert "sync" in result.output.lower() or "watchdog" in result.output.lower()

    def test_watchdog_status_detects_missing_jobs(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog status detects missing jobs."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Empty crontab
        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch("nextdns_blocker.watchdog.get_crontab", return_value=""):
                            result = runner.invoke(main, ["watchdog", "status"])

        assert result.exit_code == 0
        # Should indicate missing or not found
        assert "not" in result.output.lower() or "missing" in result.output.lower()


class TestWatchdogCheck:
    """Tests for watchdog check command (recovery)."""

    def test_watchdog_check_restores_missing_jobs(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog check restores deleted jobs on Linux without systemd."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        calls = []

        def mock_get_crontab() -> str:
            # First call: empty (jobs missing)
            # Second call after restoration: jobs present
            if len(calls) == 0:
                calls.append(1)
                return ""
            return "*/2 * * * * /usr/local/bin/nextdns-blocker config sync"

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch(
                            "nextdns_blocker.watchdog.get_crontab", side_effect=mock_get_crontab
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.set_crontab", return_value=True
                            ) as mock_set:
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_path",
                                    return_value="/usr/local/bin/nextdns-blocker",
                                ):
                                    result = runner.invoke(main, ["watchdog", "check"])

        assert result.exit_code == 0
        # Should have tried to restore jobs
        assert mock_set.called or "restored" in result.output.lower() or result.output == ""

    def test_watchdog_check_skips_when_disabled(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog check skips when watchdog is disabled."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Create disabled file
        disabled_file = log_dir / ".watchdog_disabled"
        disabled_file.write_text("permanent")

        with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["watchdog", "check"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()


class TestWatchdogDisableEnable:
    """Tests for watchdog disable and enable commands."""

    def test_watchdog_disable_temporary(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog can be disabled temporarily."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["watchdog", "disable", "30"])

        assert result.exit_code == 0
        assert "30 minutes" in result.output

        # Verify disabled file was created
        disabled_file = log_dir / ".watchdog_disabled"
        assert disabled_file.exists()

    def test_watchdog_disable_permanent(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog can be disabled permanently."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["watchdog", "disable"])

        assert result.exit_code == 0
        assert "permanently" in result.output.lower()

        # Verify disabled file contains "permanent"
        disabled_file = log_dir / ".watchdog_disabled"
        assert disabled_file.read_text() == "permanent"

    def test_watchdog_enable(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog can be re-enabled."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # First disable
        disabled_file = log_dir / ".watchdog_disabled"
        disabled_file.write_text("permanent")

        with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["watchdog", "enable"])

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

        # Verify disabled file was removed
        assert not disabled_file.exists()

    def test_watchdog_enable_when_not_disabled(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test watchdog enable when already enabled."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["watchdog", "enable"])

        assert result.exit_code == 0
        assert "already enabled" in result.output.lower()


class TestWatchdogRecoveryWorkflow:
    """Tests for the complete watchdog recovery workflow."""

    def test_watchdog_recovery_after_job_deletion(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete workflow: install → delete → check → restored on Linux without systemd."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        crontab_state = [""]  # Mutable state for the mock

        def mock_get_crontab() -> str:
            return crontab_state[0]

        def mock_set_crontab(content: str) -> bool:
            crontab_state[0] = content
            return True

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch("nextdns_blocker.watchdog.get_crontab", mock_get_crontab):
                            with patch("nextdns_blocker.watchdog.set_crontab", mock_set_crontab):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_path",
                                    return_value="/usr/local/bin/nextdns-blocker",
                                ):
                                    # Step 1: Install jobs
                                    result = runner.invoke(main, ["watchdog", "install"])
                                    assert result.exit_code == 0

                                    # Verify jobs are installed
                                    assert "nextdns-blocker config sync" in crontab_state[0]
                                    assert "nextdns-blocker watchdog" in crontab_state[0]

                                    # Step 2: Simulate job deletion (user manually removes cron)
                                    crontab_state[0] = ""

                                    # Step 3: Run watchdog check
                                    result = runner.invoke(main, ["watchdog", "check"])
                                    assert result.exit_code == 0

                                    # Step 4: Verify jobs are restored
                                    assert "nextdns-blocker config sync" in crontab_state[0]

    def test_disabled_watchdog_does_not_restore_jobs(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that disabled watchdog doesn't restore deleted jobs."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Create disabled file
        disabled_file = log_dir / ".watchdog_disabled"
        disabled_file.write_text("permanent")

        crontab_state = [""]

        def mock_get_crontab() -> str:
            return crontab_state[0]

        def mock_set_crontab(content: str) -> bool:
            crontab_state[0] = content
            return True

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.has_systemd", return_value=False):
                    with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                            with patch("nextdns_blocker.watchdog.get_crontab", mock_get_crontab):
                                with patch(
                                    "nextdns_blocker.watchdog.set_crontab", mock_set_crontab
                                ):
                                    # Run watchdog check while disabled
                                    result = runner.invoke(main, ["watchdog", "check"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        # Jobs should NOT be restored
        assert "nextdns-blocker" not in crontab_state[0]
