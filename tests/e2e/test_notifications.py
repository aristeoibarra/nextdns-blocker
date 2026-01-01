"""E2E tests for notification system."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import responses

from nextdns_blocker.notifications import (
    BatchedNotification,
    DiscordAdapter,
    EventType,
    MacOSAdapter,
    NotificationEvent,
    NotificationManager,
    get_notification_manager,
    send_notification,
)


class TestDiscordAdapterConfiguration:
    """Tests for DiscordAdapter configuration."""

    def test_not_configured_without_webhook_url(self) -> None:
        """Test adapter is not configured without webhook URL."""
        adapter = DiscordAdapter()
        assert adapter.is_configured is False

    def test_not_configured_with_none(self) -> None:
        """Test adapter is not configured with None URL."""
        adapter = DiscordAdapter(webhook_url=None)
        assert adapter.is_configured is False

    def test_configured_with_url(self) -> None:
        """Test adapter is configured with URL."""
        adapter = DiscordAdapter(webhook_url="https://discord.com/api/webhooks/123/abc")
        assert adapter.is_configured is True

    def test_name_property(self) -> None:
        """Test adapter name."""
        adapter = DiscordAdapter()
        assert adapter.name == "Discord"


class TestDiscordAdapterSend:
    """Tests for DiscordAdapter send functionality."""

    def test_skips_when_not_configured(self) -> None:
        """Test send returns False when not configured."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(events=[], profile_id="test")
        assert adapter.send(batch) is False

    @responses.activate
    def test_sends_block_notification(self) -> None:
        """Test sending block notification."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        adapter = DiscordAdapter(webhook_url=webhook_url)

        responses.add(
            responses.POST,
            webhook_url,
            json={"success": True},
            status=200,
        )

        event = NotificationEvent(
            event_type=EventType.BLOCK,
            domain="example.com",
        )
        batch = BatchedNotification(
            events=[event],
            profile_id="test-profile",
            sync_end=datetime.now(timezone.utc),
        )

        result = adapter.send(batch)

        assert result is True
        assert len(responses.calls) == 1
        request_body = responses.calls[0].request.body
        assert b"example.com" in request_body
        assert b"Blocked" in request_body

    @responses.activate
    def test_sends_unblock_notification(self) -> None:
        """Test sending unblock notification."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        adapter = DiscordAdapter(webhook_url=webhook_url)

        responses.add(
            responses.POST,
            webhook_url,
            json={"success": True},
            status=200,
        )

        event = NotificationEvent(
            event_type=EventType.UNBLOCK,
            domain="example.com",
        )
        batch = BatchedNotification(
            events=[event],
            profile_id="test-profile",
            sync_end=datetime.now(timezone.utc),
        )

        result = adapter.send(batch)

        assert result is True
        assert len(responses.calls) == 1
        request_body = responses.calls[0].request.body
        assert b"example.com" in request_body
        assert b"Unblocked" in request_body

    @responses.activate
    def test_handles_timeout(self) -> None:
        """Test notification handles timeout gracefully."""
        import requests as req

        webhook_url = "https://discord.com/api/webhooks/123/abc"
        adapter = DiscordAdapter(webhook_url=webhook_url)

        responses.add(
            responses.POST,
            webhook_url,
            body=req.exceptions.Timeout(),
        )

        event = NotificationEvent(event_type=EventType.BLOCK, domain="example.com")
        batch = BatchedNotification(events=[event], profile_id="test")

        result = adapter.send(batch)
        assert result is False

    @responses.activate
    def test_handles_connection_error(self) -> None:
        """Test notification handles connection error gracefully."""
        import requests as req

        webhook_url = "https://discord.com/api/webhooks/123/abc"
        adapter = DiscordAdapter(webhook_url=webhook_url)

        responses.add(
            responses.POST,
            webhook_url,
            body=req.exceptions.ConnectionError(),
        )

        event = NotificationEvent(event_type=EventType.BLOCK, domain="example.com")
        batch = BatchedNotification(events=[event], profile_id="test")

        result = adapter.send(batch)
        assert result is False

    @responses.activate
    def test_handles_http_error(self) -> None:
        """Test notification handles HTTP error gracefully."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        adapter = DiscordAdapter(webhook_url=webhook_url)

        responses.add(
            responses.POST,
            webhook_url,
            json={"error": "Bad request"},
            status=400,
        )

        event = NotificationEvent(event_type=EventType.BLOCK, domain="example.com")
        batch = BatchedNotification(events=[event], profile_id="test")

        result = adapter.send(batch)
        assert result is False


class TestDiscordAdapterFormatting:
    """Tests for DiscordAdapter message formatting."""

    def test_formats_empty_batch(self) -> None:
        """Test formatting empty batch."""
        adapter = DiscordAdapter()
        batch = BatchedNotification(events=[], profile_id="test")
        batch.sync_end = datetime.now(timezone.utc)

        payload = adapter.format_batch(batch)

        assert "embeds" in payload
        assert len(payload["embeds"]) == 1
        assert "No changes" in payload["embeds"][0]["description"]

    def test_formats_multiple_events(self) -> None:
        """Test formatting batch with multiple events."""
        adapter = DiscordAdapter()
        events = [
            NotificationEvent(event_type=EventType.BLOCK, domain="blocked1.com"),
            NotificationEvent(event_type=EventType.BLOCK, domain="blocked2.com"),
            NotificationEvent(event_type=EventType.UNBLOCK, domain="unblocked.com"),
        ]
        batch = BatchedNotification(
            events=events,
            profile_id="test-profile",
            sync_end=datetime.now(timezone.utc),
        )

        payload = adapter.format_batch(batch)

        desc = payload["embeds"][0]["description"]
        assert "Blocked (2)" in desc
        assert "blocked1.com" in desc
        assert "blocked2.com" in desc
        assert "Unblocked (1)" in desc
        assert "unblocked.com" in desc

    def test_truncates_long_domain_list(self) -> None:
        """Test domain list is truncated when too long."""
        adapter = DiscordAdapter()
        events = [
            NotificationEvent(event_type=EventType.BLOCK, domain=f"domain{i}.com")
            for i in range(10)
        ]
        batch = BatchedNotification(
            events=events,
            profile_id="test",
            sync_end=datetime.now(timezone.utc),
        )

        payload = adapter.format_batch(batch)

        desc = payload["embeds"][0]["description"]
        assert "+5 more" in desc


class TestNotificationColors:
    """Tests for DiscordAdapter color constants."""

    def test_block_color_is_red(self) -> None:
        """Test block color is red-ish."""
        # 15158332 = 0xE74C3C (red)
        assert DiscordAdapter.COLOR_BLOCK == 15158332

    def test_unblock_color_is_green(self) -> None:
        """Test unblock color is green-ish."""
        # 3066993 = 0x2ECC71 (green)
        assert DiscordAdapter.COLOR_UNBLOCK == 3066993

    def test_batch_color_is_blue(self) -> None:
        """Test batch color is blue."""
        # 3447003 = 0x3498DB (blue)
        assert DiscordAdapter.COLOR_BATCH == 3447003


class TestNotificationManager:
    """Tests for NotificationManager."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    def test_singleton_instance(self) -> None:
        """Test get_instance returns same instance."""
        nm1 = NotificationManager.get_instance()
        nm2 = NotificationManager.get_instance()
        assert nm1 is nm2

    def test_get_notification_manager_returns_singleton(self) -> None:
        """Test get_notification_manager helper."""
        nm = get_notification_manager()
        assert nm is NotificationManager.get_instance()

    def test_configure_with_empty_config(self) -> None:
        """Test configure with empty config."""
        nm = NotificationManager.get_instance()
        nm.configure({})
        assert len(nm._adapters) == 0

    def test_configure_with_disabled_notifications(self) -> None:
        """Test configure with notifications disabled."""
        nm = NotificationManager.get_instance()
        nm.configure({"notifications": {"enabled": False}})
        assert nm._enabled is False

    def test_configure_discord_adapter(self) -> None:
        """Test configuring Discord adapter."""
        nm = NotificationManager.get_instance()
        config = {
            "notifications": {
                "enabled": True,
                "channels": {
                    "discord": {
                        "enabled": True,
                        "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    }
                },
            }
        }
        nm.configure(config)
        assert len(nm._adapters) == 1
        assert isinstance(nm._adapters[0], DiscordAdapter)

    def test_queue_without_active_batch(self) -> None:
        """Test queue drops event when no batch is active."""
        nm = NotificationManager.get_instance()
        nm._enabled = True
        nm.queue(EventType.BLOCK, "example.com")
        assert len(nm._events) == 0

    def test_queue_with_active_batch(self) -> None:
        """Test queue adds event when batch is active."""
        nm = NotificationManager.get_instance()
        nm._enabled = True
        nm.start_batch("test-profile")
        nm.queue(EventType.BLOCK, "example.com")
        assert len(nm._events) == 1
        assert nm._events[0].domain == "example.com"
        assert nm._events[0].event_type == EventType.BLOCK

    def test_flush_clears_events(self) -> None:
        """Test flush clears event queue."""
        nm = NotificationManager.get_instance()
        nm.start_batch("test-profile")
        nm.queue(EventType.BLOCK, "example.com")
        nm.flush(async_send=False)
        assert len(nm._events) == 0
        assert nm._batch_active is False


class TestNotificationManagerContextManager:
    """Tests for NotificationManager context manager."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    @responses.activate
    def test_sync_context_flushes_on_exit(self) -> None:
        """Test sync_context flushes events on exit."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        config = {
            "notifications": {
                "enabled": True,
                "channels": {
                    "discord": {
                        "enabled": True,
                        "webhook_url": webhook_url,
                    }
                },
            }
        }

        responses.add(
            responses.POST,
            webhook_url,
            json={"success": True},
            status=200,
        )

        nm = NotificationManager.get_instance()
        with nm.sync_context("test-profile", config) as manager:
            manager.queue(EventType.BLOCK, "example.com")

        # Wait for async send
        import time

        time.sleep(0.5)

        assert len(responses.calls) == 1
        assert len(nm._events) == 0


class TestMacOSAdapter:
    """Tests for MacOSAdapter."""

    def test_name_property(self) -> None:
        """Test adapter name."""
        adapter = MacOSAdapter()
        assert adapter.name == "macOS"

    def test_is_configured_on_darwin(self) -> None:
        """Test is_configured returns True on Darwin."""
        with patch("platform.system", return_value="Darwin"):
            adapter = MacOSAdapter()
            # Re-check after patching
            adapter._is_macos = adapter._check_macos()
            assert adapter.is_configured is True

    def test_is_configured_on_linux(self) -> None:
        """Test is_configured returns False on Linux."""
        with patch("platform.system", return_value="Linux"):
            adapter = MacOSAdapter()
            adapter._is_macos = adapter._check_macos()
            assert adapter.is_configured is False

    def test_format_batch_single_event(self) -> None:
        """Test formatting single event for macOS."""
        adapter = MacOSAdapter()
        event = NotificationEvent(event_type=EventType.BLOCK, domain="example.com")
        batch = BatchedNotification(events=[event], profile_id="test")

        title, message = adapter.format_batch(batch)

        assert title == "NextDNS Blocker Sync"
        assert "Blocked: 1" in message


class TestSendNotification:
    """Tests for send_notification helper function."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        NotificationManager.reset_instance()

    @responses.activate
    def test_send_notification_immediate(self) -> None:
        """Test send_notification sends immediately."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        config = {
            "profile_id": "test-profile",
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

        responses.add(
            responses.POST,
            webhook_url,
            json={"success": True},
            status=200,
        )

        send_notification(EventType.BLOCK, "example.com", config)

        assert len(responses.calls) == 1

    def test_send_notification_skips_when_disabled(self) -> None:
        """Test send_notification skips when disabled."""
        config = {
            "notifications": {
                "enabled": False,
            },
        }

        # Should not raise
        send_notification(EventType.BLOCK, "example.com", config)
