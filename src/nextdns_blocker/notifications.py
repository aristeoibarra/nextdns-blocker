"""Discord webhook notifications for block/unblock events."""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Discord embed colors
COLOR_BLOCK = 15158332  # Red
COLOR_UNBLOCK = 3066993  # Green

# Notification timeout in seconds
NOTIFICATION_TIMEOUT = 5


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

    This function silently fails if:
    - Notifications are disabled
    - Webhook URL is not configured
    - Network request fails or times out

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

    # Determine title and color based on event type
    if event_type == "block":
        title = "🔒 Domain Blocked"
        color = COLOR_BLOCK
    elif event_type == "unblock":
        title = "🔓 Domain Unblocked"
        color = COLOR_UNBLOCK
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
