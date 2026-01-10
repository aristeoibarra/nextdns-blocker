"""Unit tests for the analytics module.

Tests cover:
- Audit log parsing
- Domain statistics aggregation
- Hourly pattern analysis
- Overall statistics calculation
- CSV export functionality
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from nextdns_blocker.analytics import (
    AnalyticsManager,
    DomainStatistics,
    HourlyPattern,
    OverallStatistics,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def tmp_audit_log(tmp_path: Path) -> Path:
    """Create a temporary audit log file."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    return log_dir / "audit.log"


@pytest.fixture
def analytics_manager(tmp_audit_log: Path) -> AnalyticsManager:
    """Create an AnalyticsManager with a temporary audit log."""
    return AnalyticsManager(audit_log_path=tmp_audit_log)


@pytest.fixture
def sample_audit_entries() -> list[str]:
    """Sample audit log entries for testing."""
    base_date = datetime.now() - timedelta(days=1)
    return [
        f"{base_date.replace(hour=10).isoformat()} | BLOCK | youtube.com",
        f"{base_date.replace(hour=10, minute=5).isoformat()} | BLOCK | twitter.com",
        f"{base_date.replace(hour=10, minute=10).isoformat()} | UNBLOCK | youtube.com",
        f"{base_date.replace(hour=11).isoformat()} | BLOCK | youtube.com",
        f"{base_date.replace(hour=12).isoformat()} | PAUSE | 30 minutes",
        f"{base_date.replace(hour=12, minute=30).isoformat()} | RESUME | Manual resume",
        f"{base_date.replace(hour=14).isoformat()} | BLOCK | facebook.com",
        f"{base_date.replace(hour=15).isoformat()} | ALLOW | trusted.com",
        f"{base_date.replace(hour=16).isoformat()} | DISALLOW | untrusted.com",
    ]


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestDomainStatistics:
    """Tests for DomainStatistics dataclass."""

    def test_effectiveness_score_no_blocks(self) -> None:
        """Test effectiveness score when no blocks."""
        stats = DomainStatistics(domain="test.com", block_count=0, unblock_count=0)
        assert stats.effectiveness_score == 100.0

    def test_effectiveness_score_all_blocks_maintained(self) -> None:
        """Test effectiveness when all blocks are maintained."""
        stats = DomainStatistics(domain="test.com", block_count=10, unblock_count=0)
        assert stats.effectiveness_score == 100.0

    def test_effectiveness_score_half_unblocked(self) -> None:
        """Test effectiveness when half are unblocked."""
        stats = DomainStatistics(domain="test.com", block_count=10, unblock_count=5)
        assert stats.effectiveness_score == 50.0

    def test_effectiveness_score_all_unblocked(self) -> None:
        """Test effectiveness when all are unblocked."""
        stats = DomainStatistics(domain="test.com", block_count=10, unblock_count=10)
        assert stats.effectiveness_score == 0.0

    def test_effectiveness_score_more_unblocks_than_blocks(self) -> None:
        """Test effectiveness doesn't go negative."""
        stats = DomainStatistics(domain="test.com", block_count=5, unblock_count=10)
        assert stats.effectiveness_score == 0.0


class TestHourlyPattern:
    """Tests for HourlyPattern dataclass."""

    def test_total_activity(self) -> None:
        """Test total activity calculation."""
        pattern = HourlyPattern(
            hour=10,
            block_count=5,
            unblock_count=3,
            allow_count=2,
            disallow_count=1,
        )
        assert pattern.total_activity == 11

    def test_total_activity_empty(self) -> None:
        """Test total activity when all counts are zero."""
        pattern = HourlyPattern(hour=10)
        assert pattern.total_activity == 0


class TestOverallStatistics:
    """Tests for OverallStatistics dataclass."""

    def test_effectiveness_score_no_blocks(self) -> None:
        """Test effectiveness when no blocks."""
        stats = OverallStatistics(total_blocks=0, total_unblocks=0)
        assert stats.effectiveness_score == 100.0

    def test_effectiveness_score_high(self) -> None:
        """Test high effectiveness score."""
        stats = OverallStatistics(total_blocks=100, total_unblocks=10)
        assert stats.effectiveness_score == 90.0


# =============================================================================
# ANALYTICS MANAGER TESTS - PARSING
# =============================================================================


class TestAuditLogParsing:
    """Tests for audit log parsing."""

    def test_parse_empty_log(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test parsing empty audit log."""
        tmp_audit_log.write_text("")
        entries = analytics_manager._parse_audit_log()
        assert entries == []

    def test_parse_missing_log(
        self,
        analytics_manager: AnalyticsManager,
    ) -> None:
        """Test parsing when log file doesn't exist."""
        entries = analytics_manager._parse_audit_log()
        assert entries == []

    def test_parse_basic_entries(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test parsing basic audit log entries."""
        entries_text = [
            "2024-01-15T10:00:00 | BLOCK | youtube.com",
            "2024-01-15T10:05:00 | UNBLOCK | youtube.com",
            "2024-01-15T10:10:00 | PAUSE | 30 minutes",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 3
        assert entries[0].action == "BLOCK"
        assert entries[0].detail == "youtube.com"
        assert entries[1].action == "UNBLOCK"
        assert entries[2].action == "PAUSE"

    def test_parse_watchdog_entries(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test parsing WD-prefixed watchdog entries."""
        entries_text = [
            "2024-01-15T10:00:00 | WD | RESTORE | cron jobs restored",
            "2024-01-15T10:05:00 | WD | CHECK | jobs ok",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 2
        assert entries[0].action == "RESTORE"
        assert entries[0].prefix == "WD"
        assert entries[0].detail == "cron jobs restored"
        assert entries[1].action == "CHECK"

    def test_parse_pending_entries(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test parsing PENDING action entries."""
        entries_text = [
            "2024-01-15T10:00:00 | PENDING_CREATE | pnd_20240115_100000_abc123 youtube.com delay=4h",
            "2024-01-15T14:00:00 | PENDING_EXECUTE | pnd_20240115_100000_abc123 youtube.com",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 2
        assert entries[0].action == "PENDING_CREATE"
        assert entries[0].detail == "youtube.com"
        assert entries[1].action == "PENDING_EXECUTE"

    def test_parse_filters_by_days(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that parsing filters entries by days."""
        now = datetime.now()
        old_date = (now - timedelta(days=10)).isoformat()
        recent_date = (now - timedelta(days=1)).isoformat()

        entries_text = [
            f"{old_date} | BLOCK | old.com",
            f"{recent_date} | BLOCK | recent.com",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log(days=7)

        assert len(entries) == 1
        assert entries[0].detail == "recent.com"

    def test_parse_filters_by_domain(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that parsing filters entries by domain."""
        entries_text = [
            "2024-01-15T10:00:00 | BLOCK | youtube.com",
            "2024-01-15T10:05:00 | BLOCK | twitter.com",
            "2024-01-15T10:10:00 | UNBLOCK | youtube.com",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log(domain_filter="youtube")

        assert len(entries) == 2
        assert all("youtube" in e.detail.lower() for e in entries)

    def test_parse_handles_malformed_entries(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that parsing skips malformed entries."""
        entries_text = [
            "2024-01-15T10:00:00 | BLOCK | youtube.com",
            "malformed line without pipes",
            "",
            "another bad line",
            "2024-01-15T10:05:00 | UNBLOCK | youtube.com",
        ]
        tmp_audit_log.write_text("\n".join(entries_text))

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 2


# =============================================================================
# ANALYTICS MANAGER TESTS - STATISTICS
# =============================================================================


class TestTopBlockedDomains:
    """Tests for get_top_blocked_domains method."""

    def test_top_blocked_domains_empty(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test top blocked with no entries."""
        tmp_audit_log.write_text("")
        result = analytics_manager.get_top_blocked_domains()
        assert result == []

    def test_top_blocked_domains_ordering(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that domains are ordered by block count."""
        now = datetime.now()
        entries = [
            f"{now.isoformat()} | BLOCK | low.com",
            f"{now.isoformat()} | BLOCK | high.com",
            f"{now.isoformat()} | BLOCK | high.com",
            f"{now.isoformat()} | BLOCK | high.com",
            f"{now.isoformat()} | BLOCK | medium.com",
            f"{now.isoformat()} | BLOCK | medium.com",
        ]
        tmp_audit_log.write_text("\n".join(entries))

        result = analytics_manager.get_top_blocked_domains(limit=10)

        assert len(result) == 3
        assert result[0].domain == "high.com"
        assert result[0].block_count == 3
        assert result[1].domain == "medium.com"
        assert result[1].block_count == 2
        assert result[2].domain == "low.com"
        assert result[2].block_count == 1

    def test_top_blocked_domains_limit(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that limit parameter works."""
        now = datetime.now()
        entries = [f"{now.isoformat()} | BLOCK | domain{i}.com" for i in range(10)]
        tmp_audit_log.write_text("\n".join(entries))

        result = analytics_manager.get_top_blocked_domains(limit=5)

        assert len(result) == 5


class TestDomainStats:
    """Tests for get_domain_stats method."""

    def test_domain_stats_found(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test getting stats for a specific domain."""
        now = datetime.now()
        entries = [
            f"{now.isoformat()} | BLOCK | youtube.com",
            f"{now.isoformat()} | BLOCK | youtube.com",
            f"{now.isoformat()} | UNBLOCK | youtube.com",
            f"{now.isoformat()} | BLOCK | twitter.com",
        ]
        tmp_audit_log.write_text("\n".join(entries))

        result = analytics_manager.get_domain_stats("youtube.com")

        assert result is not None
        assert result.domain == "youtube.com"
        assert result.block_count == 2
        assert result.unblock_count == 1
        assert result.effectiveness_score == 50.0

    def test_domain_stats_not_found(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test getting stats for nonexistent domain."""
        tmp_audit_log.write_text("2024-01-15T10:00:00 | BLOCK | other.com")

        result = analytics_manager.get_domain_stats("youtube.com")

        assert result is None

    def test_domain_stats_case_insensitive(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that domain lookup is case-insensitive."""
        now = datetime.now()
        tmp_audit_log.write_text(f"{now.isoformat()} | BLOCK | YouTube.com")

        result = analytics_manager.get_domain_stats("youtube.COM")

        assert result is not None


class TestHourlyPatterns:
    """Tests for get_hourly_patterns method."""

    def test_hourly_patterns_empty(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test hourly patterns with no entries."""
        tmp_audit_log.write_text("")

        result = analytics_manager.get_hourly_patterns()

        assert len(result) == 24
        assert all(p.total_activity == 0 for p in result)

    def test_hourly_patterns_distribution(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that activity is correctly distributed by hour."""
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        entries = [
            f"{base.replace(hour=10).isoformat()} | BLOCK | a.com",
            f"{base.replace(hour=10).isoformat()} | BLOCK | b.com",
            f"{base.replace(hour=14).isoformat()} | UNBLOCK | a.com",
            f"{base.replace(hour=22).isoformat()} | BLOCK | c.com",
            f"{base.replace(hour=22).isoformat()} | BLOCK | d.com",
            f"{base.replace(hour=22).isoformat()} | BLOCK | e.com",
        ]
        tmp_audit_log.write_text("\n".join(entries))

        result = analytics_manager.get_hourly_patterns(days=1)

        # Hour 10: 2 blocks
        assert result[10].block_count == 2
        # Hour 14: 1 unblock
        assert result[14].unblock_count == 1
        # Hour 22: 3 blocks
        assert result[22].block_count == 3


class TestGetOverallStatistics:
    """Tests for get_overall_statistics method."""

    def test_overall_stats_empty(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test overall statistics with no entries."""
        tmp_audit_log.write_text("")

        result = analytics_manager.get_overall_statistics()

        assert result.total_entries == 0
        assert result.unique_domains == 0
        assert result.effectiveness_score == 100.0

    def test_overall_stats_counts(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
        sample_audit_entries: list[str],
    ) -> None:
        """Test overall statistics counting."""
        tmp_audit_log.write_text("\n".join(sample_audit_entries))

        result = analytics_manager.get_overall_statistics()

        assert result.total_entries == 9
        assert result.total_blocks == 4
        assert result.total_unblocks == 1
        assert result.total_pauses == 1
        assert result.total_resumes == 1
        assert result.total_allows == 1
        assert result.total_disallows == 1
        assert result.unique_domains == 5  # youtube, twitter, facebook, trusted, untrusted

    def test_overall_stats_date_range(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test that date range is correctly calculated."""
        now = datetime.now()
        day1 = (now - timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
        day2 = (now - timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
        day3 = (now - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

        entries = [
            f"{day1.isoformat()} | BLOCK | a.com",
            f"{day2.isoformat()} | BLOCK | b.com",
            f"{day3.isoformat()} | BLOCK | c.com",
        ]
        tmp_audit_log.write_text("\n".join(entries))

        result = analytics_manager.get_overall_statistics()

        assert result.date_range_start is not None
        assert result.date_range_end is not None
        assert result.date_range_start.day == day1.day
        assert result.date_range_end.day == day3.day


# =============================================================================
# ANALYTICS MANAGER TESTS - EXPORT
# =============================================================================


class TestCSVExport:
    """Tests for CSV export functionality."""

    def test_export_csv_success(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
        tmp_path: Path,
    ) -> None:
        """Test successful CSV export."""
        now = datetime.now()
        entries = [
            f"{now.isoformat()} | BLOCK | youtube.com",
            f"{now.isoformat()} | UNBLOCK | youtube.com",
        ]
        tmp_audit_log.write_text("\n".join(entries))

        output_path = tmp_path / "export.csv"
        result = analytics_manager.export_csv(output_path)

        assert result is True
        assert output_path.exists()

        content = output_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert lines[0] == "timestamp,action,domain,prefix"
        assert "BLOCK" in lines[1]
        assert "youtube.com" in lines[1]

    def test_export_csv_empty(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
        tmp_path: Path,
    ) -> None:
        """Test CSV export with no entries."""
        tmp_audit_log.write_text("")

        output_path = tmp_path / "export.csv"
        result = analytics_manager.export_csv(output_path)

        assert result is True
        content = output_path.read_text()
        assert content.strip() == "timestamp,action,domain,prefix"

    def test_export_csv_invalid_path(
        self,
        analytics_manager: AnalyticsManager,
        tmp_audit_log: Path,
    ) -> None:
        """Test CSV export with invalid output path."""
        tmp_audit_log.write_text("2024-01-15T10:00:00 | BLOCK | test.com")

        # Try to write to a directory that doesn't exist
        output_path = Path("/nonexistent/dir/export.csv")
        result = analytics_manager.export_csv(output_path)

        assert result is False
