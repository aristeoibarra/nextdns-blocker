"""E2E tests for the stats command.

Tests the statistics display including:
- Reading audit log file
- Counting different action types
- Handling missing audit log
- Handling corrupted audit log
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from nextdns_blocker.cli import main


def _recent_timestamp(hours_ago: int = 0, minutes_ago: int = 0) -> str:
    """Generate a recent ISO timestamp within the default 7-day window."""
    dt = datetime.now() - timedelta(hours=hours_ago, minutes=minutes_ago)
    return dt.isoformat()


class TestStatsBasic:
    """Tests for basic stats command functionality."""

    def test_stats_shows_action_counts(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats command shows action counts from audit log."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Create audit log with various actions (using recent timestamps)
        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | BLOCK | twitter.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | UNBLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=15)} | PAUSE | 30 minutes",
            f"{_recent_timestamp(hours_ago=0, minutes_ago=45)} | RESUME | Manual resume",
            f"{_recent_timestamp(hours_ago=0)} | BLOCK | facebook.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # New format shows "Blocks:" instead of just "BLOCK"
        assert "Blocks:" in result.output or "BLOCK" in result.output
        assert "Unblocks:" in result.output or "UNBLOCK" in result.output
        assert "Total entries:" in result.output

    def test_stats_handles_empty_log(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats handles empty audit log gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_file.write_text("")

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # New format shows "No activity recorded" for empty logs
        assert "No activity" in result.output or "Total entries: 0" in result.output

    def test_stats_handles_missing_log(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats handles missing audit log gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        # Don't create the file

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # New format shows "No activity" when no log file exists
        assert "No activity" in result.output or "Statistics" in result.output


class TestStatsWatchdogEntries:
    """Tests for stats handling watchdog entries."""

    def test_stats_parses_watchdog_entries(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats correctly parses WD-prefixed entries."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | WD | RESTORE | cron jobs restored",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | WD | CHECK | jobs ok",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=15)} | UNBLOCK | youtube.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # Should parse entries without errors
        assert "Blocks:" in result.output or "Total entries:" in result.output


class TestStatsActionTypes:
    """Tests for stats with various action types."""

    def test_stats_shows_allow_disallow_actions(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats shows ALLOW and DISALLOW actions."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | ALLOW | trusted-site.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | ALLOW | another-trusted.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | DISALLOW | untrusted.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # New format shows "Allows:" and "Disallows:"
        assert "Allows:" in result.output or "ALLOW" in result.output
        assert "Disallows:" in result.output or "DISALLOW" in result.output

    def test_stats_actions_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats actions subcommand shows action breakdown."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | UNBLOCK | site.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | BLOCK | site.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | ALLOW | site.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats", "actions"])

        assert result.exit_code == 0
        # Actions subcommand shows action breakdown table
        assert "Action Breakdown" in result.output or "Total entries" in result.output


class TestStatsMalformedEntries:
    """Tests for stats handling malformed log entries."""

    def test_stats_handles_malformed_entries(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats handles malformed log entries gracefully."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            "malformed line without proper format",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | UNBLOCK | youtube.com",
            "",  # Empty line
            "another bad line",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        # Should still show valid entries
        assert "Blocks:" in result.output or "Total entries:" in result.output


class TestStatsLargeLog:
    """Tests for stats with large audit logs."""

    def test_stats_handles_large_log(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that stats handles large audit log efficiently."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"

        # Create a log file with 100 entries using recent timestamps
        entries = []
        base_time = datetime.now() - timedelta(hours=2)
        for i in range(100):
            action = ["BLOCK", "UNBLOCK", "PAUSE", "RESUME"][i % 4]
            ts = (base_time + timedelta(minutes=i)).isoformat()
            entries.append(f"{ts} | {action} | domain{i}.com")

        audit_file.write_text("\n".join(entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Total entries: 100" in result.output


class TestStatsSubcommands:
    """Tests for stats subcommands."""

    def test_stats_domains_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test stats domains subcommand."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | BLOCK | twitter.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats", "domains"])

        assert result.exit_code == 0
        assert "Top" in result.output and "Blocked" in result.output

    def test_stats_hours_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test stats hours subcommand."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=2)} | BLOCK | twitter.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats", "hours"])

        assert result.exit_code == 0
        assert "Hourly Activity" in result.output or "00:00" in result.output

    def test_stats_export_subcommand(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test stats export subcommand."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        output_file = tmp_path / "export.csv"

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats", "export", "-o", str(output_file)])

        assert result.exit_code == 0
        assert "Exported" in result.output
        assert output_file.exists()

    def test_stats_domain_filter(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test stats with domain filter."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        audit_file = log_dir / "audit.log"
        audit_entries = [
            f"{_recent_timestamp(hours_ago=1)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=5)} | BLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=10)} | UNBLOCK | youtube.com",
            f"{_recent_timestamp(hours_ago=1, minutes_ago=15)} | BLOCK | twitter.com",
        ]
        audit_file.write_text("\n".join(audit_entries))

        with patch("nextdns_blocker.analytics.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats", "--domain", "youtube"])

        assert result.exit_code == 0
        assert "youtube" in result.output.lower()
