"""Analytics module for NextDNS Blocker usage statistics.

Provides parsing and analysis of audit logs, pending actions,
and other data sources to generate usage statistics and patterns.

Note on datetime handling:
    All datetime operations use naive (timezone-unaware) datetimes
    for consistency with the rest of the codebase.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .common import (
    _lock_file,
    _unlock_file,
    ensure_naive_datetime,
    get_audit_log_file,
)
from .pending import get_pending_actions

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class DomainStatistics:
    """Statistics for a single domain."""

    domain: str
    block_count: int = 0
    unblock_count: int = 0
    allow_count: int = 0
    disallow_count: int = 0
    pending_created: int = 0
    pending_cancelled: int = 0
    pending_executed: int = 0
    last_blocked: Optional[datetime] = None
    last_unblocked: Optional[datetime] = None

    @property
    def effectiveness_score(self) -> float:
        """
        Calculate effectiveness score (0-100).

        Formula: (blocks - unblocks) / blocks * 100
        Higher score = fewer manual unblocks = more effective blocking.
        """
        if self.block_count == 0:
            return 100.0  # No blocks = perfectly effective (nothing to bypass)
        score = (self.block_count - self.unblock_count) / self.block_count * 100
        return max(0.0, min(100.0, score))


@dataclass
class HourlyPattern:
    """Blocking pattern for a specific hour."""

    hour: int  # 0-23
    block_count: int = 0
    unblock_count: int = 0
    allow_count: int = 0
    disallow_count: int = 0

    @property
    def total_activity(self) -> int:
        """Total activity count for this hour."""
        return self.block_count + self.unblock_count + self.allow_count + self.disallow_count


@dataclass
class AuditLogEntry:
    """Parsed audit log entry."""

    timestamp: datetime
    action: str
    detail: str = ""
    prefix: str = ""  # e.g., "WD" for watchdog


@dataclass
class OverallStatistics:
    """Overall usage statistics summary."""

    total_entries: int = 0
    total_blocks: int = 0
    total_unblocks: int = 0
    total_allows: int = 0
    total_disallows: int = 0
    total_pauses: int = 0
    total_resumes: int = 0
    total_panic_activations: int = 0
    total_pending_created: int = 0
    total_pending_cancelled: int = 0
    total_pending_executed: int = 0
    unique_domains: int = 0
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    action_counts: dict[str, int] = field(default_factory=dict)

    @property
    def effectiveness_score(self) -> float:
        """
        Calculate overall effectiveness score (0-100).

        Formula: (blocks - unblocks) / blocks * 100
        """
        if self.total_blocks == 0:
            return 100.0
        score = (self.total_blocks - self.total_unblocks) / self.total_blocks * 100
        return max(0.0, min(100.0, score))


# =============================================================================
# ANALYTICS MANAGER
# =============================================================================


class AnalyticsManager:
    """Centralized analytics for NextDNS Blocker."""

    # Actions that involve domains
    DOMAIN_ACTIONS = frozenset({"BLOCK", "UNBLOCK", "ALLOW", "DISALLOW"})

    # Pending action types
    PENDING_ACTIONS = frozenset({"PENDING_CREATE", "PENDING_CANCEL", "PENDING_EXECUTE"})

    def __init__(self, audit_log_path: Optional[Path] = None):
        """
        Initialize analytics manager.

        Args:
            audit_log_path: Path to audit log file. If None, uses default location.
        """
        self.audit_log_path = audit_log_path or get_audit_log_file()

    def _parse_audit_log(
        self,
        days: Optional[int] = None,
        domain_filter: Optional[str] = None,
    ) -> list[AuditLogEntry]:
        """
        Parse audit log entries.

        Args:
            days: Only include entries from last N days. None = all entries.
            domain_filter: Only include entries for this domain (case-insensitive).

        Returns:
            List of parsed audit log entries.
        """
        entries: list[AuditLogEntry] = []

        if not self.audit_log_path.exists():
            return entries

        # Calculate cutoff date if days specified
        cutoff: Optional[datetime] = None
        if days is not None:
            cutoff = datetime.now() - timedelta(days=days)

        try:
            with open(self.audit_log_path, encoding="utf-8") as f:
                _lock_file(f, exclusive=False)
                try:
                    for line in f:
                        entry = self._parse_log_line(line.strip())
                        if entry is None:
                            continue

                        # Filter by date
                        if cutoff and entry.timestamp < cutoff:
                            continue

                        # Filter by domain
                        if domain_filter:
                            detail_lower = entry.detail.lower()
                            filter_lower = domain_filter.lower()
                            if filter_lower not in detail_lower:
                                continue

                        entries.append(entry)
                finally:
                    _unlock_file(f)
        except OSError as e:
            logger.warning(f"Failed to read audit log: {e}")

        return entries

    def _parse_log_line(self, line: str) -> Optional[AuditLogEntry]:
        """
        Parse a single audit log line.

        Format: ISO_TIMESTAMP | [PREFIX] | ACTION | DETAIL
        Examples:
            2024-01-15T10:00:00.123456 | BLOCK | youtube.com
            2024-01-15T10:05:00.123456 | WD | RESTORE | cron jobs restored

        Args:
            line: Raw log line

        Returns:
            Parsed entry or None if invalid
        """
        if not line:
            return None

        parts = line.split(" | ")
        if len(parts) < 2:
            return None

        try:
            timestamp = ensure_naive_datetime(datetime.fromisoformat(parts[0].strip()))
        except ValueError:
            logger.debug(f"Invalid timestamp in log line: {line[:50]}")
            return None

        # Handle WD prefix entries: [timestamp, WD, action, detail]
        if len(parts) >= 3 and parts[1].strip() == "WD":
            return AuditLogEntry(
                timestamp=timestamp,
                action=parts[2].strip(),
                detail=parts[3].strip() if len(parts) > 3 else "",
                prefix="WD",
            )

        # Standard entries: [timestamp, action, detail]
        action = parts[1].strip()
        detail = parts[2].strip() if len(parts) > 2 else ""

        # Handle PENDING entries which have format: PENDING_X | action_id domain detail
        if action.startswith("PENDING_"):
            # Extract domain from detail like "pnd_20240115_143022_a1b2c3 youtube.com delay=4h"
            detail_parts = detail.split()
            if len(detail_parts) >= 2:
                detail = detail_parts[1]  # domain is second part

        return AuditLogEntry(
            timestamp=timestamp,
            action=action,
            detail=detail,
        )

    def get_top_blocked_domains(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[DomainStatistics]:
        """
        Get most frequently blocked domains.

        Args:
            limit: Maximum number of domains to return
            days: Only include data from last N days

        Returns:
            List of DomainStatistics sorted by block count (descending)
        """
        entries = self._parse_audit_log(days=days)
        domain_stats = self._aggregate_domain_stats(entries)

        # Sort by block count descending
        sorted_domains = sorted(
            domain_stats.values(),
            key=lambda d: d.block_count,
            reverse=True,
        )

        return sorted_domains[:limit]

    def get_domain_stats(
        self,
        domain: str,
        days: int = 7,
    ) -> Optional[DomainStatistics]:
        """
        Get statistics for a specific domain.

        Args:
            domain: Domain to get stats for
            days: Only include data from last N days

        Returns:
            DomainStatistics or None if domain not found
        """
        entries = self._parse_audit_log(days=days, domain_filter=domain)
        domain_stats = self._aggregate_domain_stats(entries)

        # Find exact match (case-insensitive)
        domain_lower = domain.lower()
        for d, stats in domain_stats.items():
            if d.lower() == domain_lower:
                return stats

        return None

    def _aggregate_domain_stats(
        self,
        entries: list[AuditLogEntry],
    ) -> dict[str, DomainStatistics]:
        """
        Aggregate entries into per-domain statistics.

        Args:
            entries: List of audit log entries

        Returns:
            Dict mapping domain to DomainStatistics
        """
        domain_stats: dict[str, DomainStatistics] = {}

        for entry in entries:
            # Extract domain from detail for domain-related actions
            domain = self._extract_domain(entry)
            if not domain:
                continue

            if domain not in domain_stats:
                domain_stats[domain] = DomainStatistics(domain=domain)

            stats = domain_stats[domain]

            if entry.action == "BLOCK":
                stats.block_count += 1
                stats.last_blocked = entry.timestamp
            elif entry.action == "UNBLOCK":
                stats.unblock_count += 1
                stats.last_unblocked = entry.timestamp
            elif entry.action == "ALLOW":
                stats.allow_count += 1
            elif entry.action == "DISALLOW":
                stats.disallow_count += 1
            elif entry.action == "PENDING_CREATE":
                stats.pending_created += 1
            elif entry.action == "PENDING_CANCEL":
                stats.pending_cancelled += 1
            elif entry.action == "PENDING_EXECUTE":
                stats.pending_executed += 1

        return domain_stats

    def _extract_domain(self, entry: AuditLogEntry) -> Optional[str]:
        """Extract domain from audit log entry if applicable."""
        if entry.action in self.DOMAIN_ACTIONS or entry.action in self.PENDING_ACTIONS:
            # Domain is typically the first word in detail
            if entry.detail:
                return entry.detail.split()[0]
        return None

    def get_hourly_patterns(
        self,
        days: int = 7,
    ) -> list[HourlyPattern]:
        """
        Get blocking patterns by hour of day.

        Args:
            days: Only include data from last N days

        Returns:
            List of 24 HourlyPattern objects (one per hour)
        """
        entries = self._parse_audit_log(days=days)

        # Initialize all hours
        patterns: dict[int, HourlyPattern] = {hour: HourlyPattern(hour=hour) for hour in range(24)}

        for entry in entries:
            hour = entry.timestamp.hour
            pattern = patterns[hour]

            if entry.action == "BLOCK":
                pattern.block_count += 1
            elif entry.action == "UNBLOCK":
                pattern.unblock_count += 1
            elif entry.action == "ALLOW":
                pattern.allow_count += 1
            elif entry.action == "DISALLOW":
                pattern.disallow_count += 1

        return [patterns[hour] for hour in range(24)]

    def get_overall_statistics(
        self,
        days: int = 7,
    ) -> OverallStatistics:
        """
        Get overall usage statistics.

        Args:
            days: Only include data from last N days

        Returns:
            OverallStatistics object
        """
        entries = self._parse_audit_log(days=days)
        domain_stats = self._aggregate_domain_stats(entries)

        stats = OverallStatistics()
        stats.total_entries = len(entries)
        stats.unique_domains = len(domain_stats)

        if entries:
            stats.date_range_start = min(e.timestamp for e in entries)
            stats.date_range_end = max(e.timestamp for e in entries)

        # Count actions
        action_counts: Counter[str] = Counter()
        for entry in entries:
            action_counts[entry.action] += 1

            if entry.action == "BLOCK":
                stats.total_blocks += 1
            elif entry.action == "UNBLOCK":
                stats.total_unblocks += 1
            elif entry.action == "ALLOW":
                stats.total_allows += 1
            elif entry.action == "DISALLOW":
                stats.total_disallows += 1
            elif entry.action == "PAUSE":
                stats.total_pauses += 1
            elif entry.action == "RESUME":
                stats.total_resumes += 1
            elif entry.action in ("PC_ACTIVATE", "PANIC_ACTIVATE"):
                stats.total_panic_activations += 1
            elif entry.action == "PENDING_CREATE":
                stats.total_pending_created += 1
            elif entry.action == "PENDING_CANCEL":
                stats.total_pending_cancelled += 1
            elif entry.action == "PENDING_EXECUTE":
                stats.total_pending_executed += 1

        stats.action_counts = dict(action_counts)

        return stats

    def get_pending_statistics(self) -> dict[str, int]:
        """
        Get statistics from pending actions.

        Returns:
            Dict with counts by status
        """
        all_actions = get_pending_actions()

        status_counts: Counter[str] = Counter()
        for action in all_actions:
            status = action.get("status", "unknown")
            status_counts[status] += 1

        return dict(status_counts)

    def export_csv(
        self,
        output_path: Path,
        days: int = 7,
    ) -> bool:
        """
        Export statistics to CSV format.

        Args:
            output_path: Path to write CSV file
            days: Only include data from last N days

        Returns:
            True if export successful, False otherwise
        """
        try:
            entries = self._parse_audit_log(days=days)

            with open(output_path, "w", encoding="utf-8") as f:
                # Header
                f.write("timestamp,action,domain,prefix\n")

                # Data rows
                for entry in entries:
                    domain = self._extract_domain(entry) or ""
                    # Escape commas in domain (rare but possible)
                    if "," in domain:
                        domain = f'"{domain}"'

                    f.write(
                        f"{entry.timestamp.isoformat()},"
                        f"{entry.action},"
                        f"{domain},"
                        f"{entry.prefix}\n"
                    )

            logger.info(f"Exported {len(entries)} entries to {output_path}")
            return True

        except OSError as e:
            logger.error(f"Failed to export CSV: {e}")
            return False
