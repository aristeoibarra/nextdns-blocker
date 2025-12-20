"""Discord webhook notifications for block/unblock events."""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Discord embed colors
COLOR_BLOCK = 15158332  # Red
COLOR_UNBLOCK = 3066993  # Green
COLOR_PENDING = 16776960  # Yellow
COLOR_CANCEL = 9807270  # Gray
COLOR_PANIC = 9109504  # Dark Red
COLOR_ALLOW = 3066993  # Green (same as unblock - adding to allowlist is permissive)
COLOR_DISALLOW = 15105570  # Orange (removing from allowlist is restrictive)

# Notification timeout in seconds
NOTIFICATION_TIMEOUT = 5

# Rate limiting: minimum seconds between notifications
# Discord allows ~30/min, so 3 second interval provides safety margin for bulk operations
MIN_NOTIFICATION_INTERVAL = 3.0


class _NotificationRateLimiter:
    """Thread-safe rate limiter for Discord notifications."""

    def __init__(self, min_interval: float = MIN_NOTIFICATION_INTERVAL) -> None:
        self._min_interval = min_interval
        self._last_notification_time: float = 0.0
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset rate limit state. Used for testing."""
        with self._lock:
            self._last_notification_time = 0.0

    def check(self) -> bool:
        """
        Check if we can send a notification based on rate limiting.

        Uses time.monotonic() for accurate interval measurement that is not
        affected by system clock changes.

        Returns:
            True if notification can be sent, False if rate limited
        """
        with self._lock:
            now = time.monotonic()
            if now - self._last_notification_time < self._min_interval:
                return False
            self._last_notification_time = now
            return True


# Singleton instance for module-level rate limiting
_rate_limiter = _NotificationRateLimiter()


def _reset_rate_limit() -> None:
    """Reset rate limit state. Used for testing."""
    _rate_limiter.reset()


def is_notifications_enabled() -> bool:
    """
    Check if Discord notifications are enabled.

    Returns:
        True if DISCORD_NOTIFICATIONS_ENABLED is set to 'true', False otherwise
    """
    enabled = os.getenv("DISCORD_NOTIFICATIONS_ENABLED", "").lower()
    return enabled == "true"


def get_webhook_url() -> Optional[str]:
    """
    Get Discord webhook URL from environment.

    Returns:
        Webhook URL if set, None otherwise
    """
    return os.getenv("DISCORD_WEBHOOK_URL")


def send_discord_notification(
    domain: str, event_type: str, webhook_url: Optional[str] = None
) -> None:
    """
    Send a Discord webhook notification for a block/unblock event.

    This function is designed to silently fail - it will never raise exceptions
    to the caller. All errors are logged and swallowed to prevent notification
    failures from interrupting the main application flow.

    Silent failures occur when:
    - Notifications are disabled AND webhook_url is not explicitly provided
    - Webhook URL is not configured
    - Network request fails or times out
    - Rate limit exceeded (3 seconds between notifications)
    - Unknown event type provided

    Args:
        domain: Domain name that was blocked/unblocked
        event_type: Event type - one of "block", "unblock", "pending",
                    "cancel_pending", or "panic"
        webhook_url: Optional explicit webhook URL. If provided, notifications
                     are sent even if DISCORD_NOTIFICATIONS_ENABLED is not set.

    Note:
        This function does not raise exceptions. All errors are caught internally
        and logged at appropriate levels (debug, warning, or error).
    """
    # If webhook_url is explicitly passed, use it regardless of env setting
    # Otherwise, check if notifications are enabled via environment
    if webhook_url is None:
        if not is_notifications_enabled():
            return
        webhook_url = get_webhook_url()

    if not webhook_url:
        logger.debug("Discord webhook URL not configured, skipping notification")
        return

    # Apply rate limiting to avoid Discord rate limits
    if not _rate_limiter.check():
        logger.debug(f"Rate limited, skipping notification for {event_type}: {domain}")
        return

    # Determine title and color based on event type
    if event_type == "block":
        title = "Domain Blocked"
        color = COLOR_BLOCK
    elif event_type == "unblock":
        title = "Domain Unblocked"
        color = COLOR_UNBLOCK
    elif event_type == "pending":
        title = "Unblock Scheduled"
        color = COLOR_PENDING
    elif event_type == "cancel_pending":
        title = "Scheduled Unblock Cancelled"
        color = COLOR_CANCEL
    elif event_type == "panic":
        title = "Panic Mode Activated"
        color = COLOR_PANIC
    elif event_type == "allow":
        title = "Domain Added to Allowlist"
        color = COLOR_ALLOW
    elif event_type == "disallow":
        title = "Domain Removed from Allowlist"
        color = COLOR_DISALLOW
    else:
        logger.warning(f"Unknown event type: {event_type}, skipping notification")
        return

    # Create Discord embed payload
    payload = {
        "embeds": [
            {
                "title": title,
                "description": domain,
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "NextDNS Blocker"},
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=NOTIFICATION_TIMEOUT)
        response.raise_for_status()
        logger.debug(f"Discord notification sent for {event_type}: {domain}")
    except requests.exceptions.Timeout:
        logger.warning(
            f"Discord notification timeout for {event_type}: {domain} "
            f"(timeout: {NOTIFICATION_TIMEOUT}s)"
        )
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Discord notification connection error for {event_type}: {domain} - {e}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Discord notification HTTP error for {event_type}: {domain} - {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Discord notification failed for {event_type}: {domain} - {e}")
    except (ValueError, TypeError) as e:
        # JSON serialization or payload construction errors
        logger.warning(f"Discord notification payload error for {event_type}: {domain} - {e}")
    except Exception as e:
        # Catch any other Exception subclass (but not BaseException like KeyboardInterrupt/SystemExit)
        # to ensure silent failure for notification errors
        logger.error(
            f"Unexpected error sending Discord notification for {event_type}: {domain} - "
            f"{type(e).__name__}: {e}"
        )
