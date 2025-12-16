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
            "domains": [
                {
                    "domain": "youtube.com",
                    "schedule": None,
                }
            ]
        }
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
            "domains": [
                {"domain": "youtube.com", "schedule": None},
                {"domain": "twitter.com", "schedule": None},
            ]
        }
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
        assert "youtube.com" in result.output
        assert "twitter.com" in result.output
        assert "blocked" in result.output.lower()

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
            "domains": [
                {"domain": "youtube.com", "schedule": None},
            ],
            "allowlist": [
                {"domain": "trusted-site.com"},
            ],
        }
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
        assert "Allowlist" in result.output
        assert "trusted-site.com" in result.output


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

        domains_data = {"domains": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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

        domains_data = {"domains": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
        assert "inactive" in result.output.lower()


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

        domains_data = {"domains": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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

        domains_data = {"domains": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])

        existing_cron = "*/2 * * * * /usr/local/bin/nextdns-blocker sync\n* * * * * /usr/local/bin/nextdns-blocker watchdog check"

        with patch("nextdns_blocker.cli.is_macos", return_value=False):
            with patch("nextdns_blocker.cli.is_windows", return_value=False):
                with patch("nextdns_blocker.cli.get_crontab", return_value=existing_cron):
                    result = runner.invoke(
                        main,
                        ["status", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert "Scheduler" in result.output
        assert "ok" in result.output.lower()

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

        domains_data = {"domains": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
            "domains": [
                {
                    "domain": "gambling.com",
                    "protected": True,
                    "schedule": None,
                }
            ]
        }
        (config_dir / "domains.json").write_text(json.dumps(domains_data))

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
        assert "gambling.com" in result.output
        # Now shows [never] instead of [protected] for backward compatibility
        assert "[never]" in result.output.lower()


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
