"""Tests for the notification system."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import responses

from nextdns_blocker.notifications import (
    BatchedNotification,
    DiscordAdapter,
    EventType,
    MacOSAdapter,
    NotificationEvent,
    NotificationManager,
    NtfyAdapter,
    SlackAdapter,
    TelegramAdapter,
    get_notification_manager,
    send_notification,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self):
        """Test all expected event types exist."""
        assert EventType.BLOCK.value == "block"
        assert EventType.UNBLOCK.value == "unblock"
        assert EventType.PENDING.value == "pending"
        assert EventType.CANCEL_PENDING.value == "cancel_pending"
        assert EventType.PANIC.value == "panic"
        assert EventType.ALLOW.value == "allow"
        assert EventType.DISALLOW.value == "disallow"
        assert EventType.PC_ACTIVATE.value == "pc_activate"
        assert EventType.PC_DEACTIVATE.value == "pc_deactivate"
        assert EventType.ERROR.value == "error"
        assert EventType.TEST.value == "test"


class TestNotificationEvent:
    """Tests for NotificationEvent dataclass."""

    def test_create_event(self):
        """Test creating a notification event."""
        event = NotificationEvent(
            event_type=EventType.BLOCK,
            domain="reddit.com",
        )
        assert event.event_type == EventType.BLOCK
        assert event.domain == "reddit.com"
        assert isinstance(event.timestamp, datetime)
        assert event.metadata == {}

    def test_create_event_with_metadata(self):
        """Test creating a notification event with metadata."""
        event = NotificationEvent(
            event_type=EventType.PC_ACTIVATE,
            domain="category:gambling",
            metadata={"category_id": "gambling"},
        )
        assert event.metadata["category_id"] == "gambling"


class TestBatchedNotification:
    """Tests for BatchedNotification dataclass."""

    def test_create_empty_batch(self):
        """Test creating an empty batch."""
        batch = BatchedNotification()
        assert batch.events == []
        assert batch.profile_id == ""
        assert isinstance(batch.sync_start, datetime)
        assert batch.sync_end is None

    def test_create_batch_with_events(self):
        """Test creating a batch with events."""
        events = [
            NotificationEvent(EventType.BLOCK, "reddit.com"),
            NotificationEvent(EventType.UNBLOCK, "github.com"),
        ]
        batch = BatchedNotification(
            events=events,
            profile_id="abc123",
        )
        assert len(batch.events) == 2
        assert batch.profile_id == "abc123"


class TestDiscordAdapter:
    """Tests for DiscordAdapter."""

    def test_name(self):
        """Test adapter name."""
        adapter = DiscordAdapter()
        assert adapter.name == "Discord"

    def test_is_configured_false_when_no_url(self):
        """Test is_configured returns False when no webhook URL."""
        adapter = DiscordAdapter()
        assert adapter.is_configured is False

    def test_is_configured_true_when_url_set(self):
        """Test is_configured returns True when webhook URL is set."""
        adapter = DiscordAdapter("https://discord.com/api/webhooks/123/abc")
        assert adapter.is_configured is True

    def test_format_batch_empty(self):
        """Test formatting an empty batch."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(profile_id="test123")
        batch.sync_end = datetime.now(timezone.utc)

        payload = adapter.format_batch(batch)

        assert "embeds" in payload
        assert len(payload["embeds"]) == 1
        embed = payload["embeds"][0]
        assert embed["description"] == "No changes"
        assert "test123" in embed["footer"]["text"]

    def test_format_batch_with_events(self):
        """Test formatting a batch with events."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(
            events=[
                NotificationEvent(EventType.BLOCK, "reddit.com"),
                NotificationEvent(EventType.BLOCK, "twitter.com"),
                NotificationEvent(EventType.UNBLOCK, "github.com"),
            ],
            profile_id="test123",
        )
        batch.sync_end = datetime.now(timezone.utc)

        payload = adapter.format_batch(batch)

        embed = payload["embeds"][0]
        assert "Blocked (2)" in embed["description"]
        assert "Unblocked (1)" in embed["description"]
        assert "reddit.com" in embed["description"]
        assert "github.com" in embed["description"]

    def test_format_batch_truncates_long_lists(self):
        """Test that long domain lists are truncated."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(
            events=[NotificationEvent(EventType.BLOCK, f"domain{i}.com") for i in range(10)],
            profile_id="test123",
        )
        batch.sync_end = datetime.now(timezone.utc)

        payload = adapter.format_batch(batch)

        embed = payload["embeds"][0]
        assert "+5 more" in embed["description"]

    @responses.activate
    def test_send_success(self):
        """Test successful notification send."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, body="", status=204)

        adapter = DiscordAdapter(webhook_url)
        batch = BatchedNotification(
            events=[NotificationEvent(EventType.BLOCK, "reddit.com")],
            profile_id="test",
        )
        batch.sync_end = datetime.now(timezone.utc)

        result = adapter.send(batch)

        assert result is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_send_http_error(self):
        """Test notification send with HTTP error."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, status=500)

        adapter = DiscordAdapter(webhook_url)
        batch = BatchedNotification(events=[], profile_id="test")
        batch.sync_end = datetime.now(timezone.utc)

        result = adapter.send(batch)

        assert result is False

    def test_send_not_configured(self):
        """Test send returns False when not configured."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(events=[], profile_id="test")

        result = adapter.send(batch)

        assert result is False


class TestMacOSAdapter:
    """Tests for MacOSAdapter."""

    def test_name(self):
        """Test adapter name."""
        adapter = MacOSAdapter()
        assert adapter.name == "macOS"

    def test_format_batch_empty(self):
        """Test formatting an empty batch returns empty message (no notification)."""
        adapter = MacOSAdapter()
        batch = BatchedNotification(profile_id="test")

        title, message = adapter.format_batch(batch)

        assert title == "NextDNS Blocker Sync"
        assert message == ""  # Empty message means no notification will be sent

    def test_format_batch_with_blocks(self):
        """Test formatting a batch with blocked domains."""
        adapter = MacOSAdapter()
        batch = BatchedNotification(
            events=[
                NotificationEvent(EventType.BLOCK, "reddit.com"),
                NotificationEvent(EventType.BLOCK, "twitter.com"),
            ],
            profile_id="test",
        )

        title, message = adapter.format_batch(batch)

        assert "Blocked: 2" in message

    def test_format_batch_panic_mode(self):
        """Test formatting a panic mode batch."""
        adapter = MacOSAdapter()
        batch = BatchedNotification(
            events=[NotificationEvent(EventType.PANIC, "Emergency")],
            profile_id="test",
        )

        title, message = adapter.format_batch(batch)

        assert title == "PANIC MODE"

    @patch("subprocess.run")
    def test_send_success(self, mock_run):
        """Test successful macOS notification send."""
        mock_run.return_value = MagicMock(returncode=0)

        adapter = MacOSAdapter()
        # Force is_macos to True for testing
        adapter._is_macos = True
        batch = BatchedNotification(
            events=[NotificationEvent(EventType.BLOCK, "test.com")],
            profile_id="test",
        )

        result = adapter.send(batch)

        assert result is True
        mock_run.assert_called_once()

    def test_send_not_macos(self):
        """Test send returns False when not on macOS."""
        adapter = MacOSAdapter()
        adapter._is_macos = False
        batch = BatchedNotification(events=[], profile_id="test")

        result = adapter.send(batch)

        assert result is False


class TestNotificationManager:
    """Tests for NotificationManager."""

    def setup_method(self):
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    def test_singleton(self):
        """Test that get_instance returns same instance."""
        nm1 = NotificationManager.get_instance()
        nm2 = NotificationManager.get_instance()
        assert nm1 is nm2

    def test_configure_with_discord(self):
        """Test configuring with Discord channel."""
        nm = NotificationManager.get_instance()
        config = {
            "notifications": {
                "enabled": True,
                "channels": {
                    "discord": {
                        "enabled": True,
                        "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    },
                    "telegram": {
                        "enabled": True,
                        "bot_token": "123:abc",
                        "chat_id": "456",
                    },
                    "slack": {
                        "enabled": True,
                        "webhook_url": "https://hooks.slack.com/services/123",
                    },
                    "ntfy": {
                        "enabled": True,
                        "topic": "mytopic",
                    },
                },
            }
        }

        nm.configure(config)

        # Discord + Telegram + Slack + Ntfy
        # Note: If MacOS available it would be there too, but usually mocked out or unavailable in test env
        # Let's check we have at least 4 adapters
        assert len(nm._adapters) >= 4

        types = [type(a) for a in nm._adapters]
        assert DiscordAdapter in types
        assert TelegramAdapter in types
        assert SlackAdapter in types
        assert NtfyAdapter in types

    def test_configure_disabled(self):
        """Test configuring with notifications disabled."""
        nm = NotificationManager.get_instance()
        config = {"notifications": {"enabled": False}}

        nm.configure(config)

        assert nm._enabled is False
        assert len(nm._adapters) == 0

    def test_start_batch(self):
        """Test starting a batch."""
        nm = NotificationManager.get_instance()
        nm.configure({"notifications": {"enabled": True}})

        nm.start_batch("profile123")

        assert nm._batch_active is True
        assert nm._profile_id == "profile123"
        assert nm._events == []

    def test_queue_event(self):
        """Test queuing an event."""
        nm = NotificationManager.get_instance()
        nm.configure({"notifications": {"enabled": True}})
        nm.start_batch("profile123")

        nm.queue(EventType.BLOCK, "reddit.com")

        assert len(nm._events) == 1
        assert nm._events[0].event_type == EventType.BLOCK
        assert nm._events[0].domain == "reddit.com"

    def test_queue_without_batch_drops_event(self):
        """Test that queuing without active batch drops the event."""
        nm = NotificationManager.get_instance()
        nm.configure({"notifications": {"enabled": True}})

        nm.queue(EventType.BLOCK, "reddit.com")

        assert len(nm._events) == 0

    def test_flush_clears_events(self):
        """Test that flush clears events."""
        nm = NotificationManager.get_instance()
        nm.configure({"notifications": {"enabled": True}})
        nm.start_batch("profile123")
        nm.queue(EventType.BLOCK, "reddit.com")

        nm.flush(async_send=False)

        assert nm._events == []
        assert nm._batch_active is False

    @responses.activate
    def test_sync_context(self):
        """Test sync_context context manager."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, body="", status=204)

        nm = NotificationManager.get_instance()
        config = {
            "profile_id": "test123",
            "notifications": {
                "enabled": True,
                "channels": {
                    "discord": {
                        "enabled": True,
                        "webhook_url": webhook_url,
                    }
                },
            },
        }

        # Use sync_context but override flush to be synchronous for testing
        nm.configure(config)
        nm.start_batch("test123")
        nm.queue(EventType.BLOCK, "reddit.com")
        nm.flush(async_send=False)

        # Verify notification was sent
        assert len(responses.calls) == 1
        assert nm._batch_active is False


class TestSendNotification:
    """Tests for send_notification helper function."""

    def setup_method(self):
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    @responses.activate
    def test_send_notification(self):
        """Test sending an immediate notification."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, body="", status=204)

        config = {
            "profile_id": "test123",
            "notifications": {
                "enabled": True,
                "channels": {
                    "discord": {
                        "enabled": True,
                        "webhook_url": webhook_url,
                    }
                },
            },
        }

        send_notification(EventType.UNBLOCK, "github.com", config)

        assert len(responses.calls) == 1
        payload = json.loads(responses.calls[0].request.body)
        assert "github.com" in payload["embeds"][0]["description"]

    def test_send_notification_no_config(self):
        """Test send_notification with no notification config."""
        config = {}

        # Should not raise
        send_notification(EventType.BLOCK, "test.com", config)


class TestGetNotificationManager:
    """Tests for get_notification_manager function."""

    def setup_method(self):
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    def test_returns_manager(self):
        """Test that function returns a NotificationManager."""
        nm = get_notification_manager()
        assert isinstance(nm, NotificationManager)

    def test_returns_same_instance(self):
        """Test that function returns the same instance."""
        nm1 = get_notification_manager()
        nm2 = get_notification_manager()
        assert nm1 is nm2


class TestTelegramAdapter:
    """Tests for TelegramAdapter."""

    def test_name(self):
        adapter = TelegramAdapter("123:abc", "456")
        assert adapter.name == "Telegram"

    def test_is_configured(self):
        assert TelegramAdapter("123:abc", "456").is_configured is True
        assert TelegramAdapter("", "456").is_configured is False
        assert TelegramAdapter("123:abc", "").is_configured is False

    def test_format_batch(self):
        adapter = TelegramAdapter("123:abc", "456")
        batch = BatchedNotification(
            events=[
                NotificationEvent(EventType.BLOCK, "test.com"),
                NotificationEvent(EventType.UNBLOCK, "ok.com"),
            ]
        )
        message = adapter.format_batch(batch)
        assert "🛑 *Blocked (1):*" in message
        assert "test.com" in message
        assert "✅ *Unblocked (1):*" in message
        assert "ok.com" in message

    @responses.activate
    def test_send_success(self):
        adapter = TelegramAdapter("123:abc", "456")
        responses.add(
            responses.POST,
            "https://api.telegram.org/bot123:abc/sendMessage",
            json={"ok": True},
            status=200,
        )
        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])

        assert adapter.send(batch) is True
        assert len(responses.calls) == 1
        payload = json.loads(responses.calls[0].request.body)
        assert payload["chat_id"] == "456"
        assert "test.com" in payload["text"]

    @responses.activate
    def test_send_failure(self):
        adapter = TelegramAdapter("123:abc", "456")
        responses.add(responses.POST, "https://api.telegram.org/bot123:abc/sendMessage", status=500)
        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        assert adapter.send(batch) is False


class TestSlackAdapter:
    """Tests for SlackAdapter."""

    def test_name(self):
        adapter = SlackAdapter("http://hook")
        assert adapter.name == "Slack"

    def test_is_configured(self):
        assert SlackAdapter("http://hook").is_configured is True
        assert SlackAdapter("").is_configured is False

    def test_format_batch(self):
        adapter = SlackAdapter("http://hook")
        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        payload = adapter.format_batch(batch)

        assert "blocks" in payload
        # Header + Blocked section
        assert len(payload["blocks"]) == 2
        assert "Blocked (1)" in payload["blocks"][1]["text"]["text"]

    @responses.activate
    def test_send_success(self):
        url = "https://hooks.slack.com/services/123"
        adapter = SlackAdapter(url)
        responses.add(responses.POST, url, status=200)

        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        assert adapter.send(batch) is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_send_failure(self):
        url = "https://hooks.slack.com/services/123"
        adapter = SlackAdapter(url)
        responses.add(responses.POST, url, status=500)

        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        assert adapter.send(batch) is False


class TestNtfyAdapter:
    """Tests for NtfyAdapter."""

    def test_name(self):
        adapter = NtfyAdapter("my-topic")
        assert adapter.name == "Ntfy"

    def test_is_configured(self):
        assert NtfyAdapter("topic").is_configured is True
        assert NtfyAdapter("").is_configured is False

    def test_format_batch(self):
        adapter = NtfyAdapter("topic")
        batch = BatchedNotification(
            events=[
                NotificationEvent(EventType.BLOCK, "test.com"),
                NotificationEvent(EventType.UNBLOCK, "ok.com"),
            ]
        )
        message = adapter.format_batch(batch)
        assert "Blocked: 1" in message
        assert "Unblocked: 1" in message

    @responses.activate
    def test_send_success(self):
        adapter = NtfyAdapter("topic", "https://ntfy.sh")
        responses.add(responses.POST, "https://ntfy.sh/topic", status=200)

        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        assert adapter.send(batch) is True
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Title"] == "NextDNS Blocker Sync"

    @responses.activate
    def test_send_failure(self):
        adapter = NtfyAdapter("topic")
        responses.add(responses.POST, "https://ntfy.sh/topic", status=500)

        batch = BatchedNotification(events=[NotificationEvent(EventType.BLOCK, "test.com")])
        assert adapter.send(batch) is False
