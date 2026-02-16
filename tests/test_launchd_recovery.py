"""Tests for launchd recovery and edge case branches in watchdog.py.

These tests cover the recovery scenarios when launchd jobs are missing
or fail to load, improving coverage of _check_launchd_jobs() and
_run_sync_after_restore().
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nextdns_blocker import watchdog
from nextdns_blocker.watchdog import (
    LAUNCHD_SYNC_LABEL,
    LAUNCHD_WATCHDOG_LABEL,
    _run_sync_after_restore,
)


class TestCheckLaunchdJobsRecovery:
    """Tests for _check_launchd_jobs recovery scenarios."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    def test_check_launchd_restores_sync_from_existing_plist(self, runner, tmp_path):
        """Should restore sync job from existing plist file."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        sync_plist = launch_agents / "com.nextdns-blocker.sync.plist"
        sync_plist.write_text("<plist>test</plist>")

        loaded_jobs = set()

        def mock_is_loaded(label):
            return label in loaded_jobs

        def mock_load_job(path):
            loaded_jobs.add(LAUNCHD_SYNC_LABEL)
            return True

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path", return_value=sync_plist
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                    side_effect=mock_is_loaded,
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.load_launchd_job",
                                        side_effect=mock_load_job,
                                    ):
                                        with patch("subprocess.run") as mock_sync:
                                            mock_sync.return_value = MagicMock(returncode=0)
                                            result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "sync launchd job restored" in result.output

    def test_check_launchd_recreates_sync_plist(self, runner, tmp_path):
        """Should recreate sync plist when missing."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        sync_plist = launch_agents / "com.nextdns-blocker.sync.plist"
        watchdog_plist = launch_agents / "com.nextdns-blocker.watchdog.plist"

        # Watchdog plist exists, sync does not
        watchdog_plist.write_text("<plist>test</plist>")

        loaded_jobs = set()

        def mock_is_loaded(label):
            if label == LAUNCHD_WATCHDOG_LABEL:
                return True
            return label in loaded_jobs

        def mock_load_job(path):
            loaded_jobs.add(LAUNCHD_SYNC_LABEL)
            return True

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path", return_value=sync_plist
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=watchdog_plist,
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        with patch(
                                            "nextdns_blocker.watchdog.load_launchd_job",
                                            side_effect=mock_load_job,
                                        ):
                                            with patch("subprocess.run") as mock_sync:
                                                mock_sync.return_value = MagicMock(returncode=0)
                                                result = runner.invoke(
                                                    watchdog.watchdog_cli, ["check"]
                                                )

        assert result.exit_code == 0
        assert "sync launchd job recreated" in result.output

    def test_check_launchd_load_fails_cleanup_plist(self, runner, tmp_path):
        """Should cleanup orphaned plist when load fails after recreation."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        sync_plist = launch_agents / "com.nextdns-blocker.sync.plist"
        watchdog_plist = launch_agents / "com.nextdns-blocker.watchdog.plist"

        def mock_is_loaded(label):
            if label == LAUNCHD_WATCHDOG_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path", return_value=sync_plist
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=watchdog_plist,
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        # _create_sync_plist succeeds but load fails
                                        with patch(
                                            "nextdns_blocker.watchdog._write_plist_file",
                                            return_value=True,
                                        ):
                                            with patch(
                                                "nextdns_blocker.watchdog.load_launchd_job",
                                                return_value=False,
                                            ):
                                                with patch("nextdns_blocker.watchdog._safe_unlink"):
                                                    result = runner.invoke(
                                                        watchdog.watchdog_cli, ["check"]
                                                    )

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to load sync launchd job" in result.output.lower()

    def test_check_launchd_create_plist_fails(self, runner, tmp_path):
        """Should show warning when plist creation fails."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)

        def mock_is_loaded(label):
            if label == LAUNCHD_WATCHDOG_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        with patch(
                                            "nextdns_blocker.watchdog._write_plist_file",
                                            return_value=False,
                                        ):
                                            result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to create sync plist" in result.output.lower()

    def test_check_launchd_restore_existing_plist_fails(self, runner, tmp_path):
        """Should show warning when loading existing plist fails."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        sync_plist = launch_agents / "sync.plist"
        sync_plist.write_text("<plist>test</plist>")

        def mock_is_loaded(label):
            if label == LAUNCHD_WATCHDOG_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path", return_value=sync_plist
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                    side_effect=mock_is_loaded,
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.load_launchd_job",
                                        return_value=False,
                                    ):
                                        result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to restore sync launchd job" in result.output.lower()

    def test_check_launchd_restores_watchdog_job(self, runner, tmp_path):
        """Should restore watchdog job when missing."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        watchdog_plist = launch_agents / "wd.plist"
        watchdog_plist.write_text("<plist>test</plist>")

        def mock_is_loaded(label):
            if label == LAUNCHD_SYNC_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=watchdog_plist,
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                    side_effect=mock_is_loaded,
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.load_launchd_job",
                                        return_value=True,
                                    ):
                                        with patch("subprocess.run") as mock_sync:
                                            mock_sync.return_value = MagicMock(returncode=0)
                                            result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "watchdog launchd job restored" in result.output

    def test_check_launchd_recreates_watchdog_plist(self, runner, tmp_path):
        """Should recreate watchdog plist when missing."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)

        loaded_jobs = set()

        def mock_is_loaded(label):
            if label == LAUNCHD_SYNC_LABEL:
                return True
            return label in loaded_jobs

        def mock_load_job(path):
            loaded_jobs.add(LAUNCHD_WATCHDOG_LABEL)
            return True

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        with patch(
                                            "nextdns_blocker.watchdog.load_launchd_job",
                                            side_effect=mock_load_job,
                                        ):
                                            with patch("subprocess.run") as mock_sync:
                                                mock_sync.return_value = MagicMock(returncode=0)
                                                result = runner.invoke(
                                                    watchdog.watchdog_cli, ["check"]
                                                )

        assert result.exit_code == 0
        assert "watchdog launchd job recreated" in result.output

    def test_check_launchd_watchdog_load_fails_cleanup(self, runner, tmp_path):
        """Should cleanup watchdog plist when load fails after recreation."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)

        def mock_is_loaded(label):
            if label == LAUNCHD_SYNC_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        with patch(
                                            "nextdns_blocker.watchdog._write_plist_file",
                                            return_value=True,
                                        ):
                                            with patch(
                                                "nextdns_blocker.watchdog.load_launchd_job",
                                                return_value=False,
                                            ):
                                                with patch("nextdns_blocker.watchdog._safe_unlink"):
                                                    result = runner.invoke(
                                                        watchdog.watchdog_cli, ["check"]
                                                    )

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to load watchdog launchd job" in result.output.lower()

    def test_check_launchd_watchdog_plist_creation_fails(self, runner, tmp_path):
        """Should show warning when watchdog plist creation fails."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)

        def mock_is_loaded(label):
            if label == LAUNCHD_SYNC_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=launch_agents / "wd.plist",
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.get_executable_args",
                                    return_value=["nextdns-blocker"],
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                        side_effect=mock_is_loaded,
                                    ):
                                        with patch(
                                            "nextdns_blocker.watchdog._write_plist_file",
                                            return_value=False,
                                        ):
                                            result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to create watchdog plist" in result.output.lower()

    def test_check_launchd_restore_watchdog_existing_fails(self, runner, tmp_path):
        """Should show warning when loading existing watchdog plist fails."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        launch_agents = tmp_path / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        watchdog_plist = launch_agents / "wd.plist"
        watchdog_plist.write_text("<plist>test</plist>")

        def mock_is_loaded(label):
            if label == LAUNCHD_SYNC_LABEL:
                return True
            return False

        with patch("nextdns_blocker.watchdog.is_macos", return_value=True):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=False):
                with patch("nextdns_blocker.watchdog.get_log_dir", return_value=log_dir):
                    with patch(
                        "nextdns_blocker.watchdog.get_launch_agents_dir", return_value=launch_agents
                    ):
                        with patch(
                            "nextdns_blocker.watchdog.get_sync_plist_path",
                            return_value=launch_agents / "sync.plist",
                        ):
                            with patch(
                                "nextdns_blocker.watchdog.get_watchdog_plist_path",
                                return_value=watchdog_plist,
                            ):
                                with patch(
                                    "nextdns_blocker.watchdog.is_launchd_job_loaded",
                                    side_effect=mock_is_loaded,
                                ):
                                    with patch(
                                        "nextdns_blocker.watchdog.load_launchd_job",
                                        return_value=False,
                                    ):
                                        result = runner.invoke(watchdog.watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        assert "failed to restore watchdog launchd job" in result.output.lower()


class TestRunSyncAfterRestore:
    """Tests for _run_sync_after_restore function."""

    def test_run_sync_success(self, tmp_path):
        """Should run sync command successfully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch(
            "nextdns_blocker.watchdog.get_executable_args", return_value=["nextdns-blocker"]
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                _run_sync_after_restore()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "config" in args
        assert "push" in args

    def test_run_sync_timeout(self, tmp_path):
        """Should handle sync timeout gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch(
            "nextdns_blocker.watchdog.get_executable_args", return_value=["nextdns-blocker"]
        ):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
                # Should not raise exception
                _run_sync_after_restore()

    def test_run_sync_oserror(self, tmp_path):
        """Should handle OSError gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch(
            "nextdns_blocker.watchdog.get_executable_args", return_value=["nextdns-blocker"]
        ):
            with patch("subprocess.run", side_effect=OSError("File not found")):
                # Should not raise exception
                _run_sync_after_restore()

    def test_run_sync_subprocess_error(self, tmp_path):
        """Should handle SubprocessError gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch(
            "nextdns_blocker.watchdog.get_executable_args", return_value=["nextdns-blocker"]
        ):
            with patch("subprocess.run", side_effect=subprocess.SubprocessError("Failed")):
                # Should not raise exception
                _run_sync_after_restore()
