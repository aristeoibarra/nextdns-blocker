"""Notification system with batching, async delivery, and multi-channel support."""

import atexit
import logging
import subprocess
import threading
from abc import ABC, abstractmethod
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Notification timeout in seconds
NOTIF_TIMEOUT = 10  # Increased timeout for external APIs


class EventType(Enum):
    """Types of notification events."""

    BLOCK = "block"
    UNBLOCK = "unblock"
    PENDING = "pending"
    CANCEL_PENDING = "cancel_pending"
    PANIC = "panic"
    ALLOW = "allow"
    DISALLOW = "disallow"
    PC_ACTIVATE = "pc_activate"
    PC_DEACTIVATE = "pc_deactivate"
    ERROR = "error"
    TEST = "test"


@dataclass
class NotificationEvent:
    """Represents a single notification event."""

    event_type: EventType
    domain: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchedNotification:
    """Represents a collection of events to be sent as one notification."""

    events: list[NotificationEvent] = field(default_factory=list)
    profile_id: str = ""
    sync_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sync_end: Optional[datetime] = None


class NotificationAdapter(ABC):
    """Base class for notification adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if adapter has required configuration."""
        pass

    @abstractmethod
    def send(self, batch: BatchedNotification) -> bool:
        """
        Send a batched notification.

        Args:
            batch: The notification batch to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def format_batch(self, batch: BatchedNotification) -> Any:
        """Format batch for this adapter's API."""
        pass


class DiscordAdapter(NotificationAdapter):
    """Discord webhook notification adapter."""

    # Discord embed colors
    COLOR_BLOCK = 15158332  # Red
    COLOR_UNBLOCK = 3066993  # Green
    COLOR_PENDING = 16776960  # Yellow
    COLOR_CANCEL = 9807270  # Gray
    COLOR_PANIC = 9109504  # Dark Red
    COLOR_ALLOW = 3066993  # Green
    COLOR_DISALLOW = 15105570  # Orange
    COLOR_ERROR = 15158332  # Red
    COLOR_BATCH = 3447003  # Blue

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self._webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "Discord"

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send(self, batch: BatchedNotification) -> bool:
        if not self.is_configured:
            logger.debug("Discord adapter not configured, skipping")
            return False

        payload = self.format_batch(batch)

        try:
            response = requests.post(
                self._webhook_url,  # type: ignore[arg-type]
                json=payload,
                timeout=NOTIF_TIMEOUT,
            )
            response.raise_for_status()
            logger.debug(f"Discord notification sent with {len(batch.events)} events")
            return True
        except requests.exceptions.Timeout:
            logger.warning(f"Discord notification timeout ({NOTIF_TIMEOUT}s)")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Discord notification connection error: {e}")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Discord notification HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Discord notification failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected Discord error: {type(e).__name__}: {e}")

        return False

    def format_batch(self, batch: BatchedNotification) -> dict[str, Any]:
        """Format batch for Discord embed."""
        # Group events by type
        blocked = [e.domain for e in batch.events if e.event_type == EventType.BLOCK]
        unblocked = [e.domain for e in batch.events if e.event_type == EventType.UNBLOCK]
        allowed = [e.domain for e in batch.events if e.event_type == EventType.ALLOW]
        disallowed = [e.domain for e in batch.events if e.event_type == EventType.DISALLOW]
        pc_activated = [e.domain for e in batch.events if e.event_type == EventType.PC_ACTIVATE]
        pc_deactivated = [e.domain for e in batch.events if e.event_type == EventType.PC_DEACTIVATE]
        pending = [e.domain for e in batch.events if e.event_type == EventType.PENDING]
        errors = [e.domain for e in batch.events if e.event_type == EventType.ERROR]
        panic = [e.domain for e in batch.events if e.event_type == EventType.PANIC]

        # Build description
        lines: list[str] = []

        if blocked:
            domains_str = self._format_domain_list(blocked)
            lines.append(f":red_circle: **Blocked ({len(blocked)}):** {domains_str}")

        if unblocked:
            domains_str = self._format_domain_list(unblocked)
            lines.append(f":green_circle: **Unblocked ({len(unblocked)}):** {domains_str}")

        if allowed:
            domains_str = self._format_domain_list(allowed)
            lines.append(f":white_check_mark: **Allowed ({len(allowed)}):** {domains_str}")

        if disallowed:
            domains_str = self._format_domain_list(disallowed)
            lines.append(f":x: **Disallowed ({len(disallowed)}):** {domains_str}")

        if pc_activated:
            domains_str = self._format_domain_list(pc_activated)
            lines.append(f":shield: **PC Activated ({len(pc_activated)}):** {domains_str}")

        if pc_deactivated:
            domains_str = self._format_domain_list(pc_deactivated)
            lines.append(f":unlock: **PC Deactivated ({len(pc_deactivated)}):** {domains_str}")

        if pending:
            domains_str = self._format_domain_list(pending)
            lines.append(f":clock3: **Scheduled ({len(pending)}):** {domains_str}")

        if panic:
            domains_str = self._format_domain_list(panic)
            lines.append(f":rotating_light: **PANIC MODE:** {domains_str}")

        if errors:
            domains_str = self._format_domain_list(errors)
            lines.append(f":warning: **Errors ({len(errors)}):** {domains_str}")

        sync_time = batch.sync_end.strftime("%H:%M") if batch.sync_end else "N/A"
        description = "\n".join(lines) if lines else "No changes"

        return {
            "embeds": [
                {
                    "title": ":bar_chart: NextDNS Blocker Sync Complete",
                    "description": description,
                    "color": self.COLOR_BATCH,
                    "footer": {"text": f"Profile: {batch.profile_id} | Synced at {sync_time}"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    def _format_domain_list(self, domains: list[str], max_show: int = 5) -> str:
        """Format domain list with truncation."""
        if len(domains) <= max_show:
            return ", ".join(domains)
        shown = ", ".join(domains[:max_show])
        return f"{shown}... (+{len(domains) - max_show} more)"


class TelegramAdapter(NotificationAdapter):
    """Telegram notification adapter."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "Telegram"

    @property
    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    def send(self, batch: BatchedNotification) -> bool:
        if not self.is_configured:
            return False

        message = self.format_batch(batch)
        if not message:
            return True

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=NOTIF_TIMEOUT)
            response.raise_for_status()
            logger.debug(f"Telegram notification sent with {len(batch.events)} events")
            return True
        except Exception as e:
            logger.warning(f"Telegram notification failed: {e}")
            return False

    def format_batch(self, batch: BatchedNotification) -> str:
        """Format batch for Telegram markdown."""
        # Simple text summary
        blocked = [e.domain for e in batch.events if e.event_type == EventType.BLOCK]
        unblocked = [e.domain for e in batch.events if e.event_type == EventType.UNBLOCK]
        errors = [e.domain for e in batch.events if e.event_type == EventType.ERROR]

        lines: list[str] = []
        if blocked:
            lines.append(f"🛑 *Blocked ({len(blocked)}):*\n" + ", ".join(blocked[:5]))
        if unblocked:
            lines.append(f"✅ *Unblocked ({len(unblocked)}):*\n" + ", ".join(unblocked[:5]))
        if errors:
            lines.append(f"⚠️ *Errors ({len(errors)}):*\n" + ", ".join(errors[:5]))

        return "\n\n".join(lines)


class SlackAdapter(NotificationAdapter):
    """Slack notification adapter."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "Slack"

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send(self, batch: BatchedNotification) -> bool:
        if not self.is_configured:
            return False

        payload = self.format_batch(batch)
        if not payload:
            return True

        try:
            response = requests.post(self._webhook_url, json=payload, timeout=NOTIF_TIMEOUT)
            response.raise_for_status()
            logger.debug(f"Slack notification sent with {len(batch.events)} events")
            return True
        except Exception as e:
            logger.warning(f"Slack notification failed: {e}")
            return False

    def format_batch(self, batch: BatchedNotification) -> dict[str, Any]:
        """Format batch for Slack Block Kit."""
        blocks: list[dict[str, Any]] = []

        # Title block
        blocks.append(
            {"type": "header", "text": {"type": "plain_text", "text": "NextDNS Blocker Sync"}}
        )

        blocked = [e.domain for e in batch.events if e.event_type == EventType.BLOCK]
        if blocked:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Blocked ({len(blocked)})*:\n" + ", ".join(blocked[:5]),
                    },
                }
            )

        return {"blocks": blocks}


class NtfyAdapter(NotificationAdapter):
    """Ntfy notification adapter."""

    def __init__(self, topic: str, server: str = "https://ntfy.sh") -> None:
        self._topic = topic
        self._server = server.rstrip("/")

    @property
    def name(self) -> str:
        return "Ntfy"

    @property
    def is_configured(self) -> bool:
        return bool(self._topic)

    def send(self, batch: BatchedNotification) -> bool:
        if not self.is_configured:
            return False

        message = self.format_batch(batch)
        if not message:
            return True

        url = f"{self._server}/{self._topic}"
        headers = {"Title": "NextDNS Blocker Sync", "Priority": "3"}

        try:
            response = requests.post(
                url, data=message.encode("utf-8"), headers=headers, timeout=NOTIF_TIMEOUT
            )
            response.raise_for_status()
            logger.debug(f"Ntfy notification sent with {len(batch.events)} events")
            return True
        except Exception as e:
            logger.warning(f"Ntfy notification failed: {e}")
            return False

    def format_batch(self, batch: BatchedNotification) -> str:
        """Format batch for Ntfy simple text."""
        # Simple text summary
        blocked = len([e for e in batch.events if e.event_type == EventType.BLOCK])
        unblocked = len([e for e in batch.events if e.event_type == EventType.UNBLOCK])

        parts = []
        if blocked:
            parts.append(f"Blocked: {blocked}")
        if unblocked:
            parts.append(f"Unblocked: {unblocked}")

        return " | ".join(parts) if parts else ""


class MacOSAdapter(NotificationAdapter):
    """macOS native notification adapter using osascript."""

    def __init__(self, sound: bool = True) -> None:
        self._sound = sound
        self._is_macos = self._check_macos()

    def _check_macos(self) -> bool:
        """Check if running on macOS."""
        import platform

        return platform.system() == "Darwin"

    @property
    def name(self) -> str:
        return "macOS"

    @property
    def is_configured(self) -> bool:
        return self._is_macos

    def send(self, batch: BatchedNotification) -> bool:
        if not self.is_configured:
            logger.debug("macOS adapter not available (not on macOS)")
            return False

        title, message = self.format_batch(batch)

        # Don't send notification if there's nothing to report
        if not message:
            logger.debug("No changes to notify, skipping macOS notification")
            return True

        try:
            sound_part = 'sound name "Glass"' if self._sound else ""
            script = f'display notification "{message}" with title "{title}" {sound_part}'

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                logger.debug(f"macOS notification sent with {len(batch.events)} events")
                return True
            else:
                logger.warning(f"macOS notification failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.warning("macOS notification timeout")
        except FileNotFoundError:
            logger.warning("osascript not found")
        except Exception as e:
            logger.error(f"Unexpected macOS notification error: {type(e).__name__}: {e}")

        return False

    def format_batch(self, batch: BatchedNotification) -> tuple[str, str]:
        """Format batch for macOS notification."""
        # Count events by type
        blocked = sum(1 for e in batch.events if e.event_type == EventType.BLOCK)
        unblocked = sum(1 for e in batch.events if e.event_type == EventType.UNBLOCK)
        allowed = sum(1 for e in batch.events if e.event_type == EventType.ALLOW)
        disallowed = sum(1 for e in batch.events if e.event_type == EventType.DISALLOW)
        pc_activated = sum(1 for e in batch.events if e.event_type == EventType.PC_ACTIVATE)
        pc_deactivated = sum(1 for e in batch.events if e.event_type == EventType.PC_DEACTIVATE)
        panic = any(e.event_type == EventType.PANIC for e in batch.events)

        title = "NextDNS Blocker Sync"
        parts: list[str] = []

        if panic:
            title = "PANIC MODE"
            parts.append("Emergency block activated")

        if blocked:
            parts.append(f"Blocked: {blocked}")
        if unblocked:
            parts.append(f"Unblocked: {unblocked}")
        if allowed:
            parts.append(f"Allowed: {allowed}")
        if disallowed:
            parts.append(f"Disallowed: {disallowed}")
        if pc_activated:
            parts.append(f"PC activated: {pc_activated}")
        if pc_deactivated:
            parts.append(f"PC deactivated: {pc_deactivated}")

        message = " | ".join(parts) if parts else ""

        # Escape quotes for osascript
        message = message.replace('"', '\\"')
        title = title.replace('"', '\\"')

        return title, message


class NotificationManager:
    """
    Manages notification collection and batched async delivery.

    Usage as context manager:
        with NotificationManager.get_instance().sync_context(profile_id, config) as nm:
            nm.queue(EventType.BLOCK, "reddit.com")
            nm.queue(EventType.UNBLOCK, "github.com")
        # Automatically flushes on exit

    Usage explicit:
        nm = NotificationManager.get_instance()
        nm.start_batch(profile_id, config)
        nm.queue(EventType.BLOCK, "reddit.com")
        nm.flush()
    """

    _instance: Optional["NotificationManager"] = None
    _lock = threading.Lock()
    _executor: Optional[ThreadPoolExecutor] = None
    _pending_futures: list[Future[bool]] = []

    def __init__(self) -> None:
        self._events: list[NotificationEvent] = []
        self._batch_active = False
        self._profile_id = ""
        self._adapters: list[NotificationAdapter] = []
        self._sync_start: Optional[datetime] = None
        self._enabled = True

    @classmethod
    def get_instance(cls) -> "NotificationManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Used for testing."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._events = []
                cls._instance._batch_active = False
                cls._instance._adapters = []
            cls._instance = None

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        """Get or create the thread pool executor."""
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="notification-",
            )
            atexit.register(cls._shutdown_executor)
        return cls._executor

    @classmethod
    def _shutdown_executor(cls) -> None:
        """Gracefully shutdown the executor on program exit."""
        if cls._executor:
            # Wait for pending notifications with timeout
            for future in cls._pending_futures:
                try:
                    future.result(timeout=5.0)
                except Exception as e:
                    logger.debug(f"Notification future error during shutdown: {e}")
            cls._executor.shutdown(wait=True, cancel_futures=True)
            cls._executor = None
            cls._pending_futures = []

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure adapters from notification config.

        Args:
            config: Notification configuration dictionary with channels
        """
        self._adapters = []

        notifications = config.get("notifications", {})
        if not notifications:
            logger.debug("No notifications section in config")
            return

        self._enabled = notifications.get("enabled", True)
        if not self._enabled:
            logger.debug("Notifications disabled in config")
            return

        channels = notifications.get("channels", {})

        # Configure Discord adapter
        discord_config = channels.get("discord", {})
        if discord_config.get("enabled", False):
            webhook_url = discord_config.get("webhook_url")
            if webhook_url:
                self._adapters.append(DiscordAdapter(webhook_url))
                logger.debug("Discord adapter configured")

        # Configure macOS adapter
        macos_config = channels.get("macos", {})
        if macos_config.get("enabled", False):
            sound = macos_config.get("sound", True)
            adapter = MacOSAdapter(sound=sound)
            if adapter.is_configured:
                self._adapters.append(adapter)
                logger.debug("macOS adapter configured")

        # Configure Telegram adapter
        telegram_config = channels.get("telegram", {})
        if telegram_config.get("enabled", False):
            bot_token = telegram_config.get("bot_token")
            chat_id = telegram_config.get("chat_id")
            if bot_token and chat_id:
                self._adapters.append(TelegramAdapter(bot_token, chat_id))
                logger.debug("Telegram adapter configured")

        # Configure Slack adapter
        slack_config = channels.get("slack", {})
        if slack_config.get("enabled", False):
            webhook_url = slack_config.get("webhook_url")
            if webhook_url:
                self._adapters.append(SlackAdapter(webhook_url))
                logger.debug("Slack adapter configured")

        # Configure Ntfy adapter
        ntfy_config = channels.get("ntfy", {})
        if ntfy_config.get("enabled", False):
            topic = ntfy_config.get("topic")
            server = ntfy_config.get("server", "https://ntfy.sh")
            if topic:
                self._adapters.append(NtfyAdapter(topic, server))
                logger.debug("Ntfy adapter configured")

    def start_batch(self, profile_id: str) -> None:
        """Start collecting events for a batch."""
        self._events = []
        self._batch_active = True
        self._profile_id = profile_id
        self._sync_start = datetime.now(timezone.utc)

    def queue(self, event_type: EventType, domain: str, **metadata: Any) -> None:
        """Queue an event for batched delivery."""
        if not self._enabled:
            return

        if not self._batch_active:
            logger.debug(f"No batch active, dropping event: {event_type.value} {domain}")
            return

        self._events.append(
            NotificationEvent(
                event_type=event_type,
                domain=domain,
                metadata=metadata,
            )
        )
        logger.debug(f"Queued notification: {event_type.value} {domain}")

    def flush(self, async_send: bool = True) -> None:
        """Send all queued events as a batch and clear the queue."""
        if not self._enabled:
            self._batch_active = False
            self._events = []
            return

        if not self._events:
            logger.debug("No events to flush")
            self._batch_active = False
            return

        if not self._adapters:
            logger.debug("No adapters configured, skipping flush")
            self._batch_active = False
            self._events = []
            return

        batch = BatchedNotification(
            events=self._events.copy(),
            profile_id=self._profile_id,
            sync_start=self._sync_start or datetime.now(timezone.utc),
            sync_end=datetime.now(timezone.utc),
        )

        if async_send:
            future = self._get_executor().submit(self._send_batch, batch)
            self._pending_futures.append(future)
            # Clean up completed futures
            self._pending_futures = [f for f in self._pending_futures if not f.done()]
        else:
            self._send_batch(batch)

        self._events = []
        self._batch_active = False

    def _send_batch(self, batch: BatchedNotification) -> bool:
        """Send batch to all configured adapters."""
        success = False
        for adapter in self._adapters:
            try:
                if adapter.send(batch):
                    success = True
            except Exception as e:
                logger.warning(f"Notification adapter {adapter.name} failed: {e}")
        return success

    @contextmanager
    def sync_context(
        self, profile_id: str, config: dict[str, Any]
    ) -> Generator["NotificationManager", None, None]:
        """Context manager for sync operations."""
        self.configure(config)
        self.start_batch(profile_id)
        try:
            yield self
        finally:
            self.flush()


def get_notification_manager() -> NotificationManager:
    """Get the global NotificationManager instance."""
    return NotificationManager.get_instance()


def send_notification(
    event_type: EventType, domain: str, config: dict[str, Any], **metadata: Any
) -> None:
    """
    Send an immediate notification (not batched).

    Use this for individual commands like unblock, allow, disallow.
    For sync operations, use NotificationManager.sync_context() instead.

    Args:
        event_type: Type of event
        domain: Domain name
        config: Configuration dict with 'notifications' section
        **metadata: Additional metadata
    """
    nm = get_notification_manager()
    nm.configure(config)

    if not nm._enabled or not nm._adapters:
        return

    event = NotificationEvent(event_type=event_type, domain=domain, metadata=metadata)
    batch = BatchedNotification(
        events=[event],
        profile_id=config.get("profile_id", ""),
    )
    batch.sync_end = batch.sync_start

    # Send synchronously for immediate feedback
    nm._send_batch(batch)
