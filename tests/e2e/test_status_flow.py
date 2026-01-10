"""E2E tests for the status command.

Tests the complete status display including:
- Showing profile and timezone information
- Displaying domain blocking status
- Showing pause state
- Displaying scheduler status
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import responses
from click.testing import CliRunner
from freezegun import freeze_time

from nextdns_blocker.cli import main

from .conftest import (
    TEST_API_KEY,
    TEST_PROFILE_ID,
    TEST_TIMEZONE,
    add_allowlist_mock,
    add_denylist_mock,
)


class TestStatusBasic:
    """Tests for basic status command functionality."""

    @responses.activate
    def test_status_shows_profile_info(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status command displays profile information."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {
            "blocklist": [
                {
                    "domain": "youtube.com",
                    "schedule": None,
                }
            ],
            "settings": {"timezone": TEST_TIMEZONE},
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert TEST_PROFILE_ID in result.output
        assert TEST_TIMEZONE in result.output
        assert "Status" in result.output

    @responses.activate
    def test_status_shows_domain_states(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows current domain blocking states."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {
            "blocklist": [
                {"domain": "youtube.com", "schedule": None},
                {"domain": "twitter.com", "schedule": None},
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # youtube is blocked, twitter is not
        add_denylist_mock(responses, domains=["youtube.com"])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        # New UX shows summary counts, not individual domains
        assert "blocked" in result.output.lower()
        # Mismatch is shown for twitter.com (should be blocked but isn't)
        assert "mismatch" in result.output.lower()

    @responses.activate
    def test_status_shows_allowlist(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows allowlist entries."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {
            "blocklist": [
                {"domain": "youtube.com", "schedule": None},
            ],
            "allowlist": [
                {"domain": "trusted-site.com"},
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=["trusted-site.com"])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        # New UX shows allowlist summary, not individual domains
        assert "Allowlist" in result.output
        assert "active" in result.output.lower()


class TestStatusPauseState:
    """Tests for status showing pause state."""

    @responses.activate
    @freeze_time("2024-01-15 12:00:00")
    def test_status_shows_active_pause(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows when blocking is paused."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                # First pause
                runner.invoke(main, ["pause", "30"])

                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                            result = runner.invoke(
                                main,
                                ["status", "--config-dir", str(config_dir)],
                            )

        assert result.exit_code == 0
        assert "ACTIVE" in result.output or "paused" in result.output.lower()

    @responses.activate
    def test_status_shows_inactive_pause(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows when blocking is not paused."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.is_macos", return_value=False):
                    with patch("nextdns_blocker.cli.is_windows", return_value=False):
                        with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                            result = runner.invoke(
                                main,
                                ["status", "--config-dir", str(config_dir)],
                            )

        assert result.exit_code == 0
        # New UX: "silence is golden" - pause not shown when inactive
        # Just verify pause ACTIVE is not shown
        assert "pause" not in result.output.lower() or "active" not in result.output.lower()


class TestStatusScheduler:
    """Tests for status showing scheduler state."""

    @responses.activate
    def test_status_shows_missing_scheduler_linux(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows missing scheduler on Linux."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert "Scheduler" in result.output
        assert "NOT FOUND" in result.output or "install" in result.output.lower()

    @responses.activate
    def test_status_shows_installed_scheduler_linux(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows installed scheduler on Linux."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        existing_cron = "*/2 * * * * /usr/local/bin/nextdns-blocker config sync\n* * * * * /usr/local/bin/nextdns-blocker watchdog check"

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=existing_cron):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert "Scheduler" in result.output
        # New UX shows "running" instead of "ok"
        assert "running" in result.output.lower()

    @responses.activate
    def test_status_shows_scheduler_macos(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows scheduler state on macOS."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=True):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.is_launchd_job_loaded", return_value=True):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert "Scheduler" in result.output


class TestStatusProtectedDomains:
    """Tests for status showing protected domains (unblock_delay indicators)."""

    @responses.activate
    def test_status_shows_protected_flag(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows unblock_delay indicator for protected domains."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {
            "blocklist": [
                {
                    "domain": "gambling.com",
                    "unblock_delay": "never",
                    "schedule": None,
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=["gambling.com"])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        # New UX shows protected domains in a separate line
        assert "protected" in result.output.lower()
        assert "gambling.com" in result.output


class TestStatusErrors:
    """Tests for status command error handling."""

    def test_status_fails_without_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status fails gracefully without configuration."""
        config_dir = tmp_path / "nonexistent"

        result = runner.invoke(
            main,
            ["status", "--config-dir", str(config_dir)],
        )

        # Click validation should catch non-existent directory
        assert result.exit_code != 0


class TestStatusUpdateNotification:
    """Tests for update notification in status command."""

    @responses.activate
    def test_status_shows_update_notification(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows update notification when update is available."""
        import json as json_module

        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        data_dir = tmp_path / "data"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        # Mock update check to return an update
        pypi_response = json_module.dumps({"info": {"version": "99.0.0"}}).encode()

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    with patch(
                        "nextdns_blocker.update_check.user_data_dir",
                        return_value=str(data_dir),
                    ):
                        with patch("urllib.request.urlopen") as mock_urlopen:
                            from unittest.mock import MagicMock

                            mock_response = MagicMock()
                            mock_response.read.return_value = pypi_response
                            mock_response.__enter__ = lambda s: s
                            mock_response.__exit__ = MagicMock(return_value=False)
                            mock_urlopen.return_value = mock_response

                            result = runner.invoke(
                                main,
                                ["status", "--config-dir", str(config_dir)],
                            )

        assert result.exit_code == 0
        assert "Update available" in result.output
        assert "99.0.0" in result.output
        assert "nextdns-blocker update" in result.output

    @responses.activate
    def test_status_no_update_check_flag(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that --no-update-check flag disables update notification."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    with patch("nextdns_blocker.update_check.check_for_update") as mock_check:
                        result = runner.invoke(
                            main,
                            ["status", "--config-dir", str(config_dir), "--no-update-check"],
                        )

        assert result.exit_code == 0
        # check_for_update should not be called when --no-update-check is used
        mock_check.assert_not_called()
        assert "Update available" not in result.output

    @responses.activate
    def test_status_handles_update_check_failure_gracefully(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status works even if update check fails."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        data_dir = tmp_path / "data"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    with patch(
                        "nextdns_blocker.update_check.user_data_dir",
                        return_value=str(data_dir),
                    ):
                        with patch("urllib.request.urlopen") as mock_urlopen:
                            import urllib.error

                            # Simulate network error
                            mock_urlopen.side_effect = urllib.error.URLError("Network error")

                            result = runner.invoke(
                                main,
                                ["status", "--config-dir", str(config_dir)],
                            )

        # Status should still work even if update check fails
        assert result.exit_code == 0
        assert "Status" in result.output
        assert TEST_PROFILE_ID in result.output
        # No update notification shown
        assert "Update available" not in result.output

    @responses.activate
    def test_status_no_notification_when_up_to_date(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows no notification when already up to date."""
        import json as json_module

        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        data_dir = tmp_path / "data"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        # Mock PyPI to return same version as current
        with patch("nextdns_blocker.cli.__version__", "1.0.0"):
            pypi_response = json_module.dumps({"info": {"version": "1.0.0"}}).encode()

            with patch("nextdns_blocker.cli.is_macos", return_value=False):
                with patch("nextdns_blocker.cli.is_windows", return_value=False):
                    with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                        with patch(
                            "nextdns_blocker.update_check.user_data_dir",
                            return_value=str(data_dir),
                        ):
                            with patch("urllib.request.urlopen") as mock_urlopen:
                                from unittest.mock import MagicMock

                                mock_response = MagicMock()
                                mock_response.read.return_value = pypi_response
                                mock_response.__enter__ = lambda s: s
                                mock_response.__exit__ = MagicMock(return_value=False)
                                mock_urlopen.return_value = mock_response

                                result = runner.invoke(
                                    main,
                                    ["status", "--config-dir", str(config_dir)],
                                )

        assert result.exit_code == 0
        assert "Update available" not in result.output


class TestStatusParentalControl:
    """Tests for parental control display in status command."""

    @responses.activate
    def test_status_shows_parental_control_categories(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows active parental control categories."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "test.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_parental_control_mock(
            responses,
            categories=[
                {"id": "gambling", "active": True},
                {"id": "porn", "active": True},
                {"id": "dating", "active": False},
            ],
            services=[],
            safe_search=True,
            block_bypass=True,
        )

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "NextDNS Parental Control" in result.output
        assert "Categories" in result.output
        assert "gambling" in result.output
        assert "porn" in result.output
        assert "dating" not in result.output  # Not active
        assert "(2 active)" in result.output
        assert "safe_search" in result.output

    @responses.activate
    def test_status_shows_parental_control_services(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows active parental control services."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "test.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_parental_control_mock(
            responses,
            categories=[],
            services=[
                {"id": "tiktok", "active": True},
                {"id": "whatsapp", "active": True},
            ],
            youtube_restricted=True,
        )

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "NextDNS Parental Control" in result.output
        assert "Services" in result.output
        assert "tiktok" in result.output
        assert "whatsapp" in result.output
        assert "(2 active)" in result.output
        assert "youtube_restricted" in result.output

    @responses.activate
    def test_status_shows_parental_control_settings(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows parental control settings correctly."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "test.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_parental_control_mock(
            responses,
            categories=[],
            services=[],
            safe_search=True,
            youtube_restricted=False,
            block_bypass=True,
        )

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "Settings" in result.output
        # Check for enabled settings (should show checkmark)
        assert "safe_search" in result.output
        assert "block_bypass" in result.output
        assert "youtube_restricted" in result.output

    @responses.activate
    def test_status_hides_parental_control_when_empty(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status hides parental control section when nothing configured."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "test.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_parental_control_mock(
            responses,
            categories=[],
            services=[],
            safe_search=False,
            youtube_restricted=False,
            block_bypass=False,
        )

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        # Section should be hidden when nothing is configured
        assert "NextDNS Parental Control" not in result.output

    @responses.activate
    def test_status_handles_parental_control_api_failure(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status handles parental control API failure gracefully."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "test.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        # Mock parental control API failure
        responses.add(
            responses.GET,
            f"https://api.nextdns.io/profiles/{TEST_PROFILE_ID}/parentalControl",
            json={"error": "Unauthorized"},
            status=401,
        )

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        # Should still work, just without parental control info
        assert result.exit_code == 0
        assert "NextDNS Parental Control" not in result.output


class TestStatusAllowlistScheduled:
    """Tests for scheduled allowlist display in status command."""

    @responses.activate
    def test_status_shows_allowlist_with_scheduled_entries(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows breakdown of scheduled allowlist entries."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # Create config with mix of scheduled and always-active allowlist entries
        domains_data = {
            "blocklist": [{"domain": "test.com", "schedule": None}],
            "allowlist": [
                {"domain": "always1.com"},
                {"domain": "always2.com"},
                {
                    "domain": "scheduled1.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "00:00", "end": "01:00"}],
                            }
                        ]
                    },
                },
                {
                    "domain": "scheduled2.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "00:00", "end": "01:00"}],
                            }
                        ]
                    },
                },
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=["always1.com", "always2.com"])
        add_parental_control_mock(responses)

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "Allowlist" in result.output
        assert "2 always active" in result.output
        assert "2 scheduled" in result.output

    @responses.activate
    def test_status_shows_simple_allowlist_without_schedules(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that status shows simple count when no scheduled entries."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # Only always-active entries
        domains_data = {
            "blocklist": [{"domain": "test.com", "schedule": None}],
            "allowlist": [
                {"domain": "always1.com"},
                {"domain": "always2.com"},
                {"domain": "always3.com"},
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=["always1.com", "always2.com", "always3.com"])
        add_parental_control_mock(responses)

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "Allowlist" in result.output
        assert "3 active" in result.output
        # Should not show "scheduled" or "always active" breakdown
        assert "scheduled" not in result.output
        assert "always active" not in result.output

    @responses.activate
    def test_status_shows_all_scheduled_allowlist(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test status when all allowlist entries are scheduled."""
        from .conftest import add_parental_control_mock

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # Only scheduled entries
        domains_data = {
            "blocklist": [{"domain": "test.com", "schedule": None}],
            "allowlist": [
                {
                    "domain": "scheduled1.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "00:00", "end": "01:00"}],
                            }
                        ]
                    },
                },
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_parental_control_mock(responses)

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=""):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir), "--no-update-check"],
                    )

        assert result.exit_code == 0
        assert "Allowlist" in result.output
        assert "1 scheduled" in result.output
        # When no always-active, should not show that part
        assert "always active" not in result.output
