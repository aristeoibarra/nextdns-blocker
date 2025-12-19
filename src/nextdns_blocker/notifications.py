"""Discord webhook notifications for block/unblock events."""

import logging
import os
import threading
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

# Notification timeout in seconds
NOTIFICATION_TIMEOUT = 5

# Rate limiting: minimum seconds between notifications (Discord allows ~30/min)
MIN_NOTIFICATION_INTERVAL = 2.0

# Thread-safe rate limiting state
_last_notification_time: float = 0.0
_rate_limit_lock = threading.Lock()


def _reset_rate_limit() -> None:
    """Reset rate limit state. Used for testing."""
    global _last_notification_time
    with _rate_limit_lock:
        _last_notification_time = 0.0


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


def _check_rate_limit() -> bool:
    """
    Check if we can send a notification based on rate limiting.

    Returns:
        True if notification can be sent, False if rate limited
    """
    global _last_notification_time
    with _rate_limit_lock:
        now = datetime.now().timestamp()
        if now - _last_notification_time < MIN_NOTIFICATION_INTERVAL:
            return False
        _last_notification_time = now
        return True


def send_discord_notification(
    domain: str, event_type: str, webhook_url: Optional[str] = None
) -> None:
    """
    Send a Discord webhook notification for a block/unblock event.

    This function silently fails if:
    - Notifications are disabled
    - Webhook URL is not configured
    - Network request fails or times out
    - Rate limit exceeded (2 seconds between notifications)

    Args:
        domain: Domain name that was blocked/unblocked
        event_type: Either "block" or "unblock"
    """
    if not is_notifications_enabled():
        return

    if webhook_url is None:
        webhook_url = get_webhook_url()
    if not webhook_url:
        logger.debug("Discord webhook URL not configured, skipping notification")
        return

    # Apply rate limiting to avoid Discord rate limits
    if not _check_rate_limit():
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
    except requests.exceptions.RequestException as e:
        logger.warning(f"Discord notification failed for {event_type}: {domain} - {e}")
    except Exception as e:
        # Catch any other unexpected errors to ensure silent failure
        logger.warning(f"Unexpected error sending Discord notification: {e}")
