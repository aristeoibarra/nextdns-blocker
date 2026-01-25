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
from typing import Any, Optional

from . import database as db
from .common import ensure_naive_datetime
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
            audit_log_path: Deprecated, kept for API compatibility. Ignored.
        """
        # audit_log_path is ignored - we now read from SQLite
        pass

    def _parse_audit_log(
        self,
        days: Optional[int] = None,
        domain_filter: Optional[str] = None,
    ) -> list[AuditLogEntry]:
        """
        Parse audit log entries from SQLite database.

        Args:
            days: Only include entries from last N days. None = all entries.
            domain_filter: Only include entries for this domain (case-insensitive).

        Returns:
            List of parsed audit log entries.
        """
        entries: list[AuditLogEntry] = []

        # Calculate date range
        start_date: Optional[str] = None
        if days is not None:
            cutoff = datetime.now() - timedelta(days=days)
            start_date = cutoff.isoformat()

        try:
            # Query from SQLite - get a large batch
            raw_entries = db.get_audit_logs(
                start_date=start_date,
                limit=100000,  # Large limit to get all entries
            )

            for row in raw_entries:
                entry = self._row_to_entry(row)
                if entry is None:
                    continue

                # Filter by domain if specified
                if domain_filter:
                    # Check domain field first
                    domain_match = False
                    if row.get("domain"):
                        if domain_filter.lower() in row["domain"].lower():
                            domain_match = True

                    # Also check metadata for domain references
                    if not domain_match and row.get("metadata"):
                        metadata = row["metadata"]
                        if isinstance(metadata, dict):
                            for value in metadata.values():
                                if (
                                    isinstance(value, str)
                                    and domain_filter.lower() in value.lower()
                                ):
                                    domain_match = True
                                    break

                    if not domain_match:
                        continue

                entries.append(entry)

        except Exception as e:
            logger.warning(f"Failed to read audit log from database: {e}")

        # Reverse to get chronological order (DB returns newest first)
        return list(reversed(entries))

    def _row_to_entry(self, row: dict[str, Any]) -> Optional[AuditLogEntry]:
        """
        Convert a database row to AuditLogEntry.

        Args:
            row: Database row dict

        Returns:
            AuditLogEntry or None if invalid
        """
        try:
            timestamp = ensure_naive_datetime(datetime.fromisoformat(row["created_at"]))
        except (ValueError, KeyError):
            return None

        event_type = row.get("event_type", "")

        # Parse prefix from event_type (e.g., "WD_RESTORE" -> prefix="WD", action="RESTORE")
        prefix = ""
        action = event_type
        if "_" in event_type:
            parts = event_type.split("_", 1)
            if parts[0] in ("WD",):  # Known prefixes
                prefix = parts[0]
                action = parts[1]

        # Build detail from domain and metadata
        detail_parts = []
        if row.get("domain"):
            detail_parts.append(row["domain"])

        metadata = row.get("metadata")
        if metadata and isinstance(metadata, dict):
            for key, value in metadata.items():
                if key != "id":  # Skip internal id
                    detail_parts.append(f"{key}={value}")

        detail = " ".join(detail_parts)

        return AuditLogEntry(
            timestamp=timestamp,
            action=action,
            detail=detail,
            prefix=prefix,
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
                parts = entry.detail.split()
                if parts:
                    return parts[0]
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
                        f"{entry.timestamp.isoformat()},{entry.action},{domain},{entry.prefix}\n"
                    )

            logger.info(f"Exported {len(entries)} entries to {output_path}")
            return True

        except OSError as e:
            logger.error(f"Failed to export CSV: {e}")
            return False
