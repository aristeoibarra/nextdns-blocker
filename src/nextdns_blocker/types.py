"""Type definitions for NextDNS Blocker using TypedDict.

This module provides structured type definitions for configuration,
protection settings, schedules, and other data structures used throughout
the application.
"""

from typing import Literal, Optional

from typing_extensions import NotRequired, TypedDict

# =============================================================================
# TIME AND SCHEDULE TYPES
# =============================================================================

DayName = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class TimeRange(TypedDict):
    """A time range with start and end times in HH:MM format."""

    start: str  # HH:MM format
    end: str  # HH:MM format


class HoursBlock(TypedDict):
    """A block of hours for specific days."""

    days: list[DayName]
    time_ranges: list[TimeRange]


class Schedule(TypedDict, total=False):
    """Schedule configuration for when a domain is available or blocked."""

    available_hours: list[HoursBlock]
    blocked_hours: list[HoursBlock]


# =============================================================================
# DOMAIN CONFIGURATION TYPES
# =============================================================================


class DomainConfig(TypedDict, total=False):
    """Configuration for a single domain in blocklist."""

    domain: str
    description: str
    unblock_delay: str  # "never", "0", "30m", "1h", "24h", etc.
    schedule: Optional[Schedule]
    locked: bool


class AllowlistEntry(TypedDict, total=False):
    """Configuration for a single domain in allowlist."""

    domain: str
    description: str
    schedule: Optional[Schedule]


# =============================================================================
# CATEGORY CONFIGURATION TYPES
# =============================================================================


class CategoryConfig(TypedDict, total=False):
    """Configuration for a domain category (user-defined grouping)."""

    id: str
    description: str
    unblock_delay: str
    schedule: Optional[Schedule]
    domains: list[str]
    locked: bool


class NextDNSCategoryConfig(TypedDict, total=False):
    """Configuration for a NextDNS native category."""

    id: str  # Must be one of NEXTDNS_CATEGORIES
    description: str
    unblock_delay: str
    schedule: Optional[Schedule]
    locked: bool


class NextDNSServiceConfig(TypedDict, total=False):
    """Configuration for a NextDNS native service."""

    id: str  # Must be one of NEXTDNS_SERVICES
    description: str
    unblock_delay: str
    schedule: Optional[Schedule]
    locked: bool


# =============================================================================
# NEXTDNS PARENTAL CONTROL TYPES
# =============================================================================


class ParentalControlConfig(TypedDict, total=False):
    """NextDNS Parental Control settings."""

    safe_search: bool
    youtube_restricted_mode: bool
    block_bypass: bool


class NextDNSConfig(TypedDict, total=False):
    """NextDNS-specific configuration section."""

    parental_control: ParentalControlConfig
    categories: list[NextDNSCategoryConfig]
    services: list[NextDNSServiceConfig]


# =============================================================================
# PROTECTION TYPES
# =============================================================================


class AutoPanicSchedule(TypedDict):
    """Schedule for auto-panic mode."""

    start: str  # HH:MM format
    end: str  # HH:MM format


class AutoPanicConfig(TypedDict, total=False):
    """Auto-panic mode configuration."""

    enabled: bool
    schedule: AutoPanicSchedule
    days: list[DayName]
    cannot_disable: bool


class ProtectionConfig(TypedDict, total=False):
    """Protection settings for addiction safety features."""

    auto_panic: AutoPanicConfig


# =============================================================================
# SETTINGS TYPES
# =============================================================================


class SettingsConfig(TypedDict, total=False):
    """Application settings."""

    editor: Optional[str]
    timezone: Optional[str]


# =============================================================================
# NOTIFICATION TYPES
# =============================================================================


class DiscordNotificationConfig(TypedDict, total=False):
    """Discord notification settings."""

    webhook_url: str
    enabled: bool


class TelegramNotificationConfig(TypedDict, total=False):
    """Telegram notification settings."""

    bot_token: str
    chat_id: str
    enabled: bool


class SlackNotificationConfig(TypedDict, total=False):
    """Slack notification settings."""

    webhook_url: str
    enabled: bool


class NtfyNotificationConfig(TypedDict, total=False):
    """Ntfy notification settings."""

    server: str
    topic: str
    enabled: bool


class MacOSNotificationConfig(TypedDict, total=False):
    """macOS notification settings."""

    enabled: bool


class NotificationsConfig(TypedDict, total=False):
    """Notification configuration section."""

    enabled: bool
    discord: DiscordNotificationConfig
    telegram: TelegramNotificationConfig
    slack: SlackNotificationConfig
    ntfy: NtfyNotificationConfig
    macos: MacOSNotificationConfig


# =============================================================================
# MAIN CONFIG TYPE
# =============================================================================


class Config(TypedDict, total=False):
    """Main configuration structure for config.json."""

    version: str
    settings: SettingsConfig
    nextdns: NextDNSConfig
    categories: list[CategoryConfig]
    blocklist: list[DomainConfig]
    allowlist: list[AllowlistEntry]
    schedules: dict[str, Schedule]
    protection: ProtectionConfig
    notifications: NotificationsConfig


# =============================================================================
# LOADED CONFIG TYPE (with environment variables merged)
# =============================================================================


class LoadedConfig(TypedDict):
    """Configuration after loading with environment variables merged."""

    api_key: str
    profile_id: str
    timeout: int
    retries: int
    timezone: str
    blocklist: list[DomainConfig]
    allowlist: list[AllowlistEntry]
    categories: list[CategoryConfig]
    nextdns: NotRequired[NextDNSConfig]
    protection: NotRequired[ProtectionConfig]
    notifications: NotRequired[NotificationsConfig]
    schedules: NotRequired[dict[str, Schedule]]


# =============================================================================
# UNLOCK REQUEST TYPES
# =============================================================================

UnlockRequestStatus = Literal["pending", "executed", "cancelled", "expired"]
ItemType = Literal["category", "service", "domain", "auto_panic", "pin"]


class UnlockRequest(TypedDict, total=False):
    """An unlock request for a locked item."""

    id: str
    item_type: ItemType
    item_id: str
    created_at: str  # ISO format datetime
    execute_at: str  # ISO format datetime
    delay_hours: int
    reason: Optional[str]
    status: UnlockRequestStatus
    executed_at: str  # ISO format datetime (when executed)
    cancelled_at: str  # ISO format datetime (when cancelled)


# =============================================================================
# PENDING ACTION TYPES
# =============================================================================

PendingActionType = Literal["unblock", "block", "allow", "disallow"]
PendingActionStatus = Literal["pending", "executed", "cancelled", "expired"]


class PendingAction(TypedDict, total=False):
    """A pending action waiting to be executed."""

    id: str
    action: PendingActionType
    domain: str
    created_at: str  # ISO format datetime
    execute_at: str  # ISO format datetime
    delay_seconds: int
    reason: Optional[str]
    status: PendingActionStatus
    executed_at: str  # ISO format datetime


class PendingActionsData(TypedDict):
    """Container for pending actions stored in file."""

    version: str
    pending_actions: list[PendingAction]


# =============================================================================
# RETRY QUEUE TYPES
# =============================================================================

RetryActionType = Literal["block", "unblock", "allow", "disallow"]


class RetryQueueItem(TypedDict):
    """An item in the retry queue."""

    id: str
    domain: str
    action: RetryActionType
    error_type: str
    error_msg: str
    attempt_count: int
    created_at: str  # ISO format datetime
    next_retry_at: str  # ISO format datetime


# =============================================================================
# API TYPES
# =============================================================================


class APIRequestResultData(TypedDict, total=False):
    """Data returned from API requests."""

    data: list[dict[str, str]]  # For denylist/allowlist responses
    # Other fields may be present depending on endpoint


# =============================================================================
# AUDIT LOG TYPES
# =============================================================================

AuditAction = Literal[
    "BLOCK",
    "UNBLOCK",
    "ALLOW",
    "DISALLOW",
    "PANIC_ON",
    "PANIC_OFF",
    "SYNC",
    "PENDING_CREATE",
    "PENDING_CANCEL",
    "PENDING_EXECUTE",
    "UNLOCK_REQUEST",
    "UNLOCK_CANCEL",
    "UNLOCK_EXECUTE",
    "PIN_SET",
    "PIN_REMOVE",
    "PIN_LOCKOUT",
]
