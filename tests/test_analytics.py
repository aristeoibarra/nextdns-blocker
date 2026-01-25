"""Unit tests for the analytics module.

Tests cover:
- Audit log parsing from SQLite
- Domain statistics aggregation
- Hourly pattern analysis
- Overall statistics calculation
- CSV export functionality
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker import database as db
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
def use_temp_database(tmp_path: Path):
    """Use a temporary database for each test."""
    test_db_path = tmp_path / "test.db"

    with patch.object(db, "get_db_path", return_value=test_db_path):
        if hasattr(db._local, "connection"):
            db._local.connection = None
        db.init_database()
        yield
        db.close_connection()


@pytest.fixture
def analytics_manager(use_temp_database) -> AnalyticsManager:
    """Create an AnalyticsManager with a temporary database."""
    return AnalyticsManager()


def add_audit_entry(
    event_type: str,
    domain: str = None,
    metadata: dict = None,
    created_at: str = None,
) -> None:
    """Helper to add audit log entries to the database."""
    if created_at is None:
        created_at = datetime.now().isoformat()
    db.add_audit_log(
        event_type=event_type,
        domain=domain,
        metadata=metadata,
        created_at=created_at,
    )


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
    """Tests for audit log parsing from SQLite."""

    def test_parse_empty_log(self, analytics_manager: AnalyticsManager) -> None:
        """Test parsing empty audit log."""
        entries = analytics_manager._parse_audit_log()
        assert entries == []

    def test_parse_missing_log(self, analytics_manager: AnalyticsManager) -> None:
        """Test parsing when database is empty."""
        entries = analytics_manager._parse_audit_log()
        assert entries == []

    def test_parse_basic_entries(self, analytics_manager: AnalyticsManager) -> None:
        """Test parsing basic audit log entries."""
        add_audit_entry("BLOCK", domain="youtube.com", created_at="2024-01-15T10:00:00")
        add_audit_entry("UNBLOCK", domain="youtube.com", created_at="2024-01-15T10:05:00")
        add_audit_entry(
            "PAUSE", metadata={"duration": "30 minutes"}, created_at="2024-01-15T10:10:00"
        )

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 3
        assert entries[0].action == "BLOCK"
        assert entries[0].detail == "youtube.com"
        assert entries[1].action == "UNBLOCK"
        assert entries[2].action == "PAUSE"

    def test_parse_watchdog_entries(self, analytics_manager: AnalyticsManager) -> None:
        """Test parsing WD-prefixed watchdog entries."""
        add_audit_entry(
            "WD_RESTORE",
            metadata={"detail": "cron jobs restored"},
            created_at="2024-01-15T10:00:00",
        )
        add_audit_entry(
            "WD_CHECK", metadata={"detail": "jobs ok"}, created_at="2024-01-15T10:05:00"
        )

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 2
        assert entries[0].action == "RESTORE"
        assert entries[0].prefix == "WD"
        assert entries[1].action == "CHECK"

    def test_parse_pending_entries(self, analytics_manager: AnalyticsManager) -> None:
        """Test parsing PENDING action entries."""
        add_audit_entry(
            "PENDING_CREATE",
            domain="youtube.com",
            metadata={"delay": "4h"},
            created_at="2024-01-15T10:00:00",
        )
        add_audit_entry(
            "PENDING_EXECUTE",
            domain="youtube.com",
            created_at="2024-01-15T14:00:00",
        )

        entries = analytics_manager._parse_audit_log()

        assert len(entries) == 2
        assert entries[0].action == "PENDING_CREATE"
        assert "youtube.com" in entries[0].detail
        assert entries[1].action == "PENDING_EXECUTE"

    def test_parse_filters_by_days(self, analytics_manager: AnalyticsManager) -> None:
        """Test that parsing filters entries by days."""
        now = datetime.now()
        old_date = (now - timedelta(days=10)).isoformat()
        recent_date = (now - timedelta(days=1)).isoformat()

        add_audit_entry("BLOCK", domain="old.com", created_at=old_date)
        add_audit_entry("BLOCK", domain="recent.com", created_at=recent_date)

        entries = analytics_manager._parse_audit_log(days=7)

        assert len(entries) == 1
        assert "recent.com" in entries[0].detail

    def test_parse_filters_by_domain(self, analytics_manager: AnalyticsManager) -> None:
        """Test that parsing filters entries by domain."""
        add_audit_entry("BLOCK", domain="youtube.com", created_at="2024-01-15T10:00:00")
        add_audit_entry("BLOCK", domain="twitter.com", created_at="2024-01-15T10:05:00")
        add_audit_entry("UNBLOCK", domain="youtube.com", created_at="2024-01-15T10:10:00")

        entries = analytics_manager._parse_audit_log(domain_filter="youtube")

        assert len(entries) == 2
        assert all("youtube" in e.detail.lower() for e in entries)


# =============================================================================
# ANALYTICS MANAGER TESTS - STATISTICS
# =============================================================================


class TestTopBlockedDomains:
    """Tests for get_top_blocked_domains method."""

    def test_top_blocked_domains_empty(self, analytics_manager: AnalyticsManager) -> None:
        """Test top blocked with no entries."""
        result = analytics_manager.get_top_blocked_domains()
        assert result == []

    def test_top_blocked_domains_ordering(self, analytics_manager: AnalyticsManager) -> None:
        """Test that domains are ordered by block count."""
        now = datetime.now().isoformat()
        add_audit_entry("BLOCK", domain="low.com", created_at=now)
        add_audit_entry("BLOCK", domain="high.com", created_at=now)
        add_audit_entry("BLOCK", domain="high.com", created_at=now)
        add_audit_entry("BLOCK", domain="high.com", created_at=now)
        add_audit_entry("BLOCK", domain="medium.com", created_at=now)
        add_audit_entry("BLOCK", domain="medium.com", created_at=now)

        result = analytics_manager.get_top_blocked_domains(limit=10)

        assert len(result) == 3
        assert result[0].domain == "high.com"
        assert result[0].block_count == 3
        assert result[1].domain == "medium.com"
        assert result[1].block_count == 2
        assert result[2].domain == "low.com"
        assert result[2].block_count == 1

    def test_top_blocked_domains_limit(self, analytics_manager: AnalyticsManager) -> None:
        """Test that limit parameter works."""
        now = datetime.now().isoformat()
        for i in range(10):
            add_audit_entry("BLOCK", domain=f"domain{i}.com", created_at=now)

        result = analytics_manager.get_top_blocked_domains(limit=5)

        assert len(result) == 5


class TestDomainStats:
    """Tests for get_domain_stats method."""

    def test_domain_stats_found(self, analytics_manager: AnalyticsManager) -> None:
        """Test getting stats for a specific domain."""
        now = datetime.now().isoformat()
        add_audit_entry("BLOCK", domain="youtube.com", created_at=now)
        add_audit_entry("BLOCK", domain="youtube.com", created_at=now)
        add_audit_entry("UNBLOCK", domain="youtube.com", created_at=now)
        add_audit_entry("BLOCK", domain="twitter.com", created_at=now)

        result = analytics_manager.get_domain_stats("youtube.com")

        assert result is not None
        assert result.domain == "youtube.com"
        assert result.block_count == 2
        assert result.unblock_count == 1
        assert result.effectiveness_score == 50.0

    def test_domain_stats_not_found(self, analytics_manager: AnalyticsManager) -> None:
        """Test getting stats for nonexistent domain."""
        add_audit_entry("BLOCK", domain="other.com", created_at="2024-01-15T10:00:00")

        result = analytics_manager.get_domain_stats("youtube.com")

        assert result is None

    def test_domain_stats_case_insensitive(self, analytics_manager: AnalyticsManager) -> None:
        """Test that domain lookup is case-insensitive."""
        now = datetime.now().isoformat()
        add_audit_entry("BLOCK", domain="YouTube.com", created_at=now)

        result = analytics_manager.get_domain_stats("youtube.COM")

        assert result is not None


class TestHourlyPatterns:
    """Tests for get_hourly_patterns method."""

    def test_hourly_patterns_empty(self, analytics_manager: AnalyticsManager) -> None:
        """Test hourly patterns with no entries."""
        result = analytics_manager.get_hourly_patterns()

        assert len(result) == 24
        assert all(p.total_activity == 0 for p in result)

    def test_hourly_patterns_distribution(self, analytics_manager: AnalyticsManager) -> None:
        """Test that activity is correctly distributed by hour."""
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        add_audit_entry("BLOCK", domain="a.com", created_at=base.replace(hour=10).isoformat())
        add_audit_entry("BLOCK", domain="b.com", created_at=base.replace(hour=10).isoformat())
        add_audit_entry("UNBLOCK", domain="a.com", created_at=base.replace(hour=14).isoformat())
        add_audit_entry("BLOCK", domain="c.com", created_at=base.replace(hour=22).isoformat())
        add_audit_entry("BLOCK", domain="d.com", created_at=base.replace(hour=22).isoformat())
        add_audit_entry("BLOCK", domain="e.com", created_at=base.replace(hour=22).isoformat())

        result = analytics_manager.get_hourly_patterns(days=1)

        # Hour 10: 2 blocks
        assert result[10].block_count == 2
        # Hour 14: 1 unblock
        assert result[14].unblock_count == 1
        # Hour 22: 3 blocks
        assert result[22].block_count == 3


class TestGetOverallStatistics:
    """Tests for get_overall_statistics method."""

    def test_overall_stats_empty(self, analytics_manager: AnalyticsManager) -> None:
        """Test overall statistics with no entries."""
        result = analytics_manager.get_overall_statistics()

        assert result.total_entries == 0
        assert result.unique_domains == 0
        assert result.effectiveness_score == 100.0

    def test_overall_stats_counts(self, analytics_manager: AnalyticsManager) -> None:
        """Test overall statistics counting."""
        base_date = datetime.now() - timedelta(days=1)
        add_audit_entry(
            "BLOCK", domain="youtube.com", created_at=base_date.replace(hour=10).isoformat()
        )
        add_audit_entry(
            "BLOCK",
            domain="twitter.com",
            created_at=base_date.replace(hour=10, minute=5).isoformat(),
        )
        add_audit_entry(
            "UNBLOCK",
            domain="youtube.com",
            created_at=base_date.replace(hour=10, minute=10).isoformat(),
        )
        add_audit_entry(
            "BLOCK", domain="youtube.com", created_at=base_date.replace(hour=11).isoformat()
        )
        add_audit_entry("PAUSE", created_at=base_date.replace(hour=12).isoformat())
        add_audit_entry("RESUME", created_at=base_date.replace(hour=12, minute=30).isoformat())
        add_audit_entry(
            "BLOCK", domain="facebook.com", created_at=base_date.replace(hour=14).isoformat()
        )
        add_audit_entry(
            "ALLOW", domain="trusted.com", created_at=base_date.replace(hour=15).isoformat()
        )
        add_audit_entry(
            "DISALLOW", domain="untrusted.com", created_at=base_date.replace(hour=16).isoformat()
        )

        result = analytics_manager.get_overall_statistics()

        assert result.total_entries == 9
        assert result.total_blocks == 4
        assert result.total_unblocks == 1
        assert result.total_pauses == 1
        assert result.total_resumes == 1
        assert result.total_allows == 1
        assert result.total_disallows == 1
        assert result.unique_domains == 5  # youtube, twitter, facebook, trusted, untrusted

    def test_overall_stats_date_range(self, analytics_manager: AnalyticsManager) -> None:
        """Test that date range is correctly calculated."""
        now = datetime.now()
        day1 = (now - timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
        day2 = (now - timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
        day3 = (now - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

        add_audit_entry("BLOCK", domain="a.com", created_at=day1.isoformat())
        add_audit_entry("BLOCK", domain="b.com", created_at=day2.isoformat())
        add_audit_entry("BLOCK", domain="c.com", created_at=day3.isoformat())

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
        tmp_path: Path,
    ) -> None:
        """Test successful CSV export."""
        now = datetime.now().isoformat()
        add_audit_entry("BLOCK", domain="youtube.com", created_at=now)
        add_audit_entry("UNBLOCK", domain="youtube.com", created_at=now)

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
        tmp_path: Path,
    ) -> None:
        """Test CSV export with no entries."""
        output_path = tmp_path / "export.csv"
        result = analytics_manager.export_csv(output_path)

        assert result is True
        content = output_path.read_text()
        assert content.strip() == "timestamp,action,domain,prefix"

    def test_export_csv_invalid_path(self, analytics_manager: AnalyticsManager) -> None:
        """Test CSV export with invalid output path."""
        add_audit_entry("BLOCK", domain="test.com", created_at="2024-01-15T10:00:00")

        # Try to write to a directory that doesn't exist
        output_path = Path("/nonexistent/dir/export.csv")
        result = analytics_manager.export_csv(output_path)

        assert result is False
