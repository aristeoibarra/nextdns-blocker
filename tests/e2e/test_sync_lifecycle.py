"""E2E tests for the sync lifecycle.

Tests the complete block/unblock cycle including:
- Blocking domains during restricted hours
- Unblocking domains during allowed hours
- Protected domains that never get unblocked
- Dry-run mode
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
    add_allowlist_mock,
    add_denylist_mock,
)

# Use UTC for predictable schedule evaluation with freezegun
TEST_TIMEZONE = "UTC"


class TestSyncBlocksDuringRestrictedHours:
    """Tests for blocking domains outside allowed schedule."""

    @responses.activate
    @freeze_time("2024-01-15 20:00:00")  # Monday 8pm (outside 09:00-17:00)
    def test_sync_blocks_domain_during_restricted_hours(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync blocks domains outside their allowed schedule."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        # Create config files
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
                                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Mock API: domain not currently blocked (allow multiple GET calls)
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"id": "youtube.com", "active": True},
            status=200,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir), "-v"],
                )

        assert result.exit_code == 0, f"Sync failed: {result.output}"
        assert "1 blocked" in result.output or "Blocked" in result.output.lower()

    @responses.activate
    @freeze_time("2024-01-15 12:00:00")  # Monday noon (inside 09:00-17:00)
    def test_sync_unblocks_domain_during_allowed_hours(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync unblocks domains during their allowed schedule."""
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
                                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Mock API: domain currently blocked
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": [{"id": "youtube.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/youtube.com",
            json={"success": True},
            status=200,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir), "-v"],
                )

        assert result.exit_code == 0, f"Sync failed: {result.output}"
        assert "1 unblocked" in result.output or "unblocked" in result.output.lower()


class TestSyncProtectedDomains:
    """Tests for protected domains that should never be unblocked."""

    @responses.activate
    @freeze_time("2024-01-15 12:00:00")  # Monday noon
    def test_protected_domain_stays_blocked(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that protected domains are never unblocked even during allowed hours."""
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
                    "protected": True,
                    "schedule": None,  # No schedule means always blocked
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Mock API: domain currently blocked
        add_denylist_mock(responses, domains=["gambling.com"])
        add_allowlist_mock(responses, domains=[])
        # No unblock mock needed - it should not be called

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir), "-v"],
                )

        assert result.exit_code == 0
        # Should not attempt to unblock
        assert "unblocked" not in result.output.lower() or "0 unblocked" in result.output


class TestSyncDryRun:
    """Tests for dry-run mode."""

    @responses.activate
    @freeze_time("2024-01-15 20:00:00")  # Monday 8pm (restricted time)
    def test_dry_run_shows_changes_without_applying(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that --dry-run shows what would happen without making changes."""
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

        # Only mock GET endpoints - POST should not be called in dry-run
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
            json={"data": []},
            status=200,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--dry-run", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Would BLOCK" in result.output


class TestFullDayCycle:
    """Tests simulating a full day cycle with time changes."""

    @responses.activate
    def test_full_day_cycle_block_unblock(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test a complete day cycle: restricted time (block) → allowed time (unblock)."""
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
                                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Phase 1: Morning before allowed hours (7am) - should block
        with freeze_time("2024-01-15 07:00:00"):  # Monday 7am
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
                json={"data": []},
                status=200,
            )
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
                json={"data": []},
                status=200,
            )
            responses.add(
                responses.POST,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
                json={"id": "youtube.com", "active": True},
                status=200,
            )

            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                    result = runner.invoke(
                        main,
                        ["sync", "--config-dir", str(config_dir)],
                    )

            assert result.exit_code == 0
            assert "1 blocked" in result.output

        # Clear responses for next phase
        responses.reset()

        # Phase 2: During allowed hours (10am) - should unblock
        with freeze_time("2024-01-15 10:00:00"):  # Monday 10am
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
                json={"data": [{"id": "youtube.com", "active": True}]},
                status=200,
            )
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
                json={"data": []},
                status=200,
            )
            responses.add(
                responses.DELETE,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/youtube.com",
                json={"success": True},
                status=200,
            )

            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                    result = runner.invoke(
                        main,
                        ["sync", "--config-dir", str(config_dir)],
                    )

            assert result.exit_code == 0
            assert "1 unblocked" in result.output

        # Clear responses for next phase
        responses.reset()

        # Phase 3: After allowed hours (8pm) - should block again
        with freeze_time("2024-01-15 20:00:00"):  # Monday 8pm
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
                json={"data": []},
                status=200,
            )
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
                json={"data": []},
                status=200,
            )
            responses.add(
                responses.POST,
                f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
                json={"id": "youtube.com", "active": True},
                status=200,
            )

            with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                    result = runner.invoke(
                        main,
                        ["sync", "--config-dir", str(config_dir)],
                    )

            assert result.exit_code == 0
            assert "1 blocked" in result.output


class TestSyncMultipleDomains:
    """Tests for syncing multiple domains with different schedules."""

    @responses.activate
    @freeze_time("2024-01-13 15:00:00")  # Saturday 3pm
    def test_sync_handles_mixed_schedules(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test sync correctly handles domains with different schedules."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # youtube: weekdays 9-17 (should be blocked on Saturday)
        # twitter: weekends 10-22 (should be allowed on Saturday 3pm)
        domains_data = {
            "blocklist": [
                {
                    "domain": "youtube.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                },
                {
                    "domain": "twitter.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["saturday", "sunday"],
                                "time_ranges": [{"start": "10:00", "end": "22:00"}],
                            }
                        ]
                    },
                },
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Mock API: both domains currently not blocked
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
            json={"data": []},
            status=200,
        )
        # Only youtube should be blocked (Saturday is not in its schedule)
        # twitter should NOT be blocked (Saturday 3pm is within 10-22)
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"id": "youtube.com", "active": True},
            status=200,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        # Only 1 domain should be blocked (youtube), twitter is allowed on Saturday 3pm
        assert "1 blocked" in result.output


class TestSyncNoChanges:
    """Tests for sync when no changes are needed."""

    @responses.activate
    @freeze_time("2024-01-15 20:00:00")  # Monday 8pm
    def test_sync_no_changes_when_state_matches(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync reports no changes when state already matches."""
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

        # Domain is already blocked (correct state for 8pm)
        add_denylist_mock(responses, domains=["youtube.com"])
        add_allowlist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir), "-v"],
                )

        assert result.exit_code == 0
        # Should indicate no changes
        assert "No changes" in result.output or (
            "0 blocked" not in result.output and "blocked" not in result.output.lower()
        )
