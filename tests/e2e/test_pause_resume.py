"""E2E tests for the pause/resume flow.

Tests the complete pause/resume cycle including:
- Pause command creates pause file
- Sync skips when paused
- Resume clears pause state
- Sync works normally after resume
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import responses
from click.testing import CliRunner
from freezegun import freeze_time

from nextdns_blocker.cli import main
from nextdns_blocker.client import API_URL

from .conftest import (
    TEST_API_KEY,
    TEST_PROFILE_ID,
    TEST_TIMEZONE,
    add_allowlist_mock,
    add_block_mock,
    add_denylist_mock,
)


class TestPauseCommand:
    """Tests for the pause command."""

    def test_pause_creates_pause_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that pause command creates a pause state file."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["pause", "30"])

        assert result.exit_code == 0
        assert "paused for 30 minutes" in result.output.lower()

        # Verify pause file exists
        pause_file = log_dir / ".paused"
        assert pause_file.exists()

    def test_pause_default_duration(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that pause with no argument uses default duration."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["pause"])

        assert result.exit_code == 0
        assert "paused" in result.output.lower()

    def test_pause_with_custom_duration(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test pause with custom duration."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["pause", "60"])

        assert result.exit_code == 0
        assert "60 minutes" in result.output


class TestResumeCommand:
    """Tests for the resume command."""

    def test_resume_clears_pause(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that resume clears the pause state."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                # First pause
                runner.invoke(main, ["pause", "30"])

                # Then resume
                result = runner.invoke(main, ["resume"])

        assert result.exit_code == 0
        assert "resumed" in result.output.lower()

        # Verify pause file is gone
        pause_file = log_dir / ".paused"
        assert not pause_file.exists()

    def test_resume_when_not_paused(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test resume when not currently paused."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(main, ["resume"])

        assert result.exit_code == 0
        assert "not currently paused" in result.output.lower()


class TestSyncWhilePaused:
    """Tests for sync behavior during pause."""

    @responses.activate
    @freeze_time("2024-01-15 20:00:00")  # Monday 8pm (restricted time)
    def test_sync_skips_when_paused(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync command skips execution when paused."""
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
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                # First pause
                runner.invoke(main, ["pause", "30"])

                # Try to sync - should skip
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "paused" in result.output.lower()
        assert "skipping sync" in result.output.lower()


class TestPauseResumeWorkflow:
    """Tests for the complete pause → sync → resume workflow."""

    @responses.activate
    @freeze_time("2024-01-15 20:00:00")  # Monday 8pm (restricted time)
    def test_complete_pause_resume_workflow(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete workflow: pause → sync (skipped) → resume → sync (executes)."""
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
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                # Step 1: Pause for 30 minutes
                result = runner.invoke(main, ["pause", "30"])
                assert result.exit_code == 0
                assert "paused" in result.output.lower()

                # Step 2: Try to sync - should be skipped
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )
                assert result.exit_code == 0
                assert "skipping sync" in result.output.lower()

                # Step 3: Resume
                result = runner.invoke(main, ["resume"])
                assert result.exit_code == 0
                assert "resumed" in result.output.lower()

                # Step 4: Sync should now execute
                # Set up API mocks
                add_denylist_mock(responses, domains=[])
                add_allowlist_mock(responses, domains=[])
                add_block_mock(responses, "youtube.com")

                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )
                assert result.exit_code == 0
                # Should actually sync now
                assert "skipping" not in result.output.lower()


class TestPauseExpiration:
    """Tests for pause expiration behavior."""

    @responses.activate
    def test_sync_works_after_pause_expires(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync works normally after pause expires."""
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
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # First pause at 8pm
        with freeze_time("2024-01-15 20:00:00"):
            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                    result = runner.invoke(main, ["pause", "30"])
                    assert result.exit_code == 0

        # Try sync at 8:35pm (after 30 min pause expires)
        with freeze_time("2024-01-15 20:35:00"):
            add_denylist_mock(responses, domains=[])
            add_allowlist_mock(responses, domains=[])
            add_block_mock(responses, "youtube.com")

            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                    result = runner.invoke(
                        main,
                        ["sync", "--config-dir", str(config_dir)],
                    )

            assert result.exit_code == 0
            # Should not say paused/skipping
            assert "skipping" not in result.output.lower()


class TestManualUnblockDuringPause:
    """Tests for manual unblock during pause."""

    @responses.activate
    def test_unblock_works_while_paused(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that manual unblock command works even when paused."""
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
                    "schedule": None,  # Always blocked
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Set up mocks for unblock
        add_denylist_mock(responses, domains=["youtube.com"])
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/youtube.com",
            json={"success": True},
            status=200,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                # First pause
                runner.invoke(main, ["pause", "30"])

                # Manual unblock should still work
                result = runner.invoke(
                    main,
                    ["unblock", "youtube.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "unblocked" in result.output.lower()
