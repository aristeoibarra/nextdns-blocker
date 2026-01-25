"""E2E tests for the stats command.

Tests the statistics display including:
- Reading audit log from SQLite database
- Counting different action types
- Handling empty database
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nextdns_blocker import database as db
from nextdns_blocker.cli import main


def _recent_timestamp(hours_ago: int = 0, minutes_ago: int = 0) -> str:
    """Generate a recent ISO timestamp within the default 7-day window."""
    dt = datetime.now() - timedelta(hours=hours_ago, minutes=minutes_ago)
    return dt.isoformat()


@pytest.fixture
def use_temp_database(tmp_path: Path):
    """Use a temporary database for each test."""
    test_db_path = tmp_path / "test.db"

    with patch.object(db, "get_db_path", return_value=test_db_path):
        if hasattr(db._local, "connection"):
            db._local.connection = None
        db.init_database()
        yield test_db_path
        db.close_connection()


def _add_audit_entry(
    event_type: str,
    domain: str | None = None,
    hours_ago: int = 0,
    minutes_ago: int = 0,
) -> None:
    """Add an audit log entry to the database."""
    ts = _recent_timestamp(hours_ago, minutes_ago)
    metadata = None
    db.add_audit_log(event_type=event_type, domain=domain, metadata=metadata, created_at=ts)


class TestStatsBasic:
    """Tests for basic stats command functionality."""

    def test_stats_shows_action_counts(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats command shows action counts from audit log."""
        # Add various actions to database
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)
        _add_audit_entry("BLOCK", "twitter.com", hours_ago=1, minutes_ago=5)
        _add_audit_entry("UNBLOCK", "youtube.com", hours_ago=1, minutes_ago=10)
        _add_audit_entry("PAUSE", None, hours_ago=1, minutes_ago=15)
        _add_audit_entry("RESUME", None, hours_ago=0, minutes_ago=45)
        _add_audit_entry("BLOCK", "facebook.com", hours_ago=0)

        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Blocks:" in result.output or "BLOCK" in result.output
        assert "Unblocks:" in result.output or "UNBLOCK" in result.output
        assert "Total entries:" in result.output

    def test_stats_handles_empty_log(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats handles empty audit log gracefully."""
        # Database is empty by default
        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "No activity" in result.output or "Total entries: 0" in result.output

    def test_stats_handles_no_database(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats handles missing database gracefully."""
        # Use a path that doesn't exist
        non_existent_db = tmp_path / "nonexistent.db"

        with patch.object(db, "get_db_path", return_value=non_existent_db):
            if hasattr(db._local, "connection"):
                db._local.connection = None
            db.init_database()
            result = runner.invoke(main, ["stats"])
            db.close_connection()

        assert result.exit_code == 0
        assert "No activity" in result.output or "Statistics" in result.output


class TestStatsWatchdogEntries:
    """Tests for stats handling watchdog entries."""

    def test_stats_parses_watchdog_entries(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats correctly parses WD-prefixed entries."""
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)
        _add_audit_entry("WD_RESTORE", None, hours_ago=1, minutes_ago=5)
        _add_audit_entry("WD_CHECK", None, hours_ago=1, minutes_ago=10)
        _add_audit_entry("UNBLOCK", "youtube.com", hours_ago=1, minutes_ago=15)

        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Blocks:" in result.output or "Total entries:" in result.output


class TestStatsActionTypes:
    """Tests for stats with various action types."""

    def test_stats_shows_allow_disallow_actions(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats shows ALLOW and DISALLOW actions."""
        _add_audit_entry("ALLOW", "trusted-site.com", hours_ago=1)
        _add_audit_entry("ALLOW", "another-trusted.com", hours_ago=1, minutes_ago=5)
        _add_audit_entry("DISALLOW", "untrusted.com", hours_ago=1, minutes_ago=10)

        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Allows:" in result.output or "ALLOW" in result.output
        assert "Disallows:" in result.output or "DISALLOW" in result.output

    def test_stats_actions_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats actions subcommand shows action breakdown."""
        _add_audit_entry("UNBLOCK", "site.com", hours_ago=1)
        _add_audit_entry("BLOCK", "site.com", hours_ago=1, minutes_ago=5)
        _add_audit_entry("ALLOW", "site.com", hours_ago=1, minutes_ago=10)

        result = runner.invoke(main, ["stats", "actions"])

        assert result.exit_code == 0
        assert "Action Breakdown" in result.output or "Total entries" in result.output


class TestStatsLargeLog:
    """Tests for stats with large audit logs."""

    def test_stats_handles_large_log(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test that stats handles large audit log efficiently."""
        # Create 100 entries
        base_time = datetime.now() - timedelta(hours=2)
        for i in range(100):
            action = ["BLOCK", "UNBLOCK", "PAUSE", "RESUME"][i % 4]
            ts = (base_time + timedelta(minutes=i)).isoformat()
            db.add_audit_log(event_type=action, domain=f"domain{i}.com", created_at=ts)

        result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Total entries: 100" in result.output


class TestStatsSubcommands:
    """Tests for stats subcommands."""

    def test_stats_domains_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test stats domains subcommand."""
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1, minutes_ago=5)
        _add_audit_entry("BLOCK", "twitter.com", hours_ago=1, minutes_ago=10)

        result = runner.invoke(main, ["stats", "domains"])

        assert result.exit_code == 0
        assert "Top" in result.output and "Blocked" in result.output

    def test_stats_hours_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test stats hours subcommand."""
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)
        _add_audit_entry("BLOCK", "twitter.com", hours_ago=2)

        result = runner.invoke(main, ["stats", "hours"])

        assert result.exit_code == 0
        assert "Hourly Activity" in result.output or "00:00" in result.output

    def test_stats_export_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test stats export subcommand."""
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)

        output_file = tmp_path / "export.csv"

        result = runner.invoke(main, ["stats", "export", "-o", str(output_file)])

        assert result.exit_code == 0
        assert "Exported" in result.output
        assert output_file.exists()

    def test_stats_domain_filter(
        self,
        runner: CliRunner,
        tmp_path: Path,
        use_temp_database: Path,
    ) -> None:
        """Test stats with domain filter."""
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1)
        _add_audit_entry("BLOCK", "youtube.com", hours_ago=1, minutes_ago=5)
        _add_audit_entry("UNBLOCK", "youtube.com", hours_ago=1, minutes_ago=10)
        _add_audit_entry("BLOCK", "twitter.com", hours_ago=1, minutes_ago=15)

        result = runner.invoke(main, ["stats", "--domain", "youtube"])

        assert result.exit_code == 0
        assert "youtube" in result.output.lower()
