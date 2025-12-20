"""Tests for Discord webhook notifications."""

import json
import os
from datetime import datetime
from unittest.mock import patch

import requests
import responses

from nextdns_blocker.notifications import (
    COLOR_BLOCK,
    COLOR_UNBLOCK,
    NOTIFICATION_TIMEOUT,
    get_webhook_url,
    is_notifications_enabled,
    send_discord_notification,
)


class TestNotificationConfiguration:
    """Tests for notification configuration functions."""

    def test_is_notifications_enabled_true(self):
        """Test that notifications are enabled when DISCORD_NOTIFICATIONS_ENABLED=true."""
        with patch.dict(os.environ, {"DISCORD_NOTIFICATIONS_ENABLED": "true"}):
            assert is_notifications_enabled() is True

    def test_is_notifications_enabled_false(self):
        """Test that notifications are disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_notifications_enabled() is False

    def test_is_notifications_enabled_case_insensitive(self):
        """Test that notification enabled check is case insensitive."""
        with patch.dict(os.environ, {"DISCORD_NOTIFICATIONS_ENABLED": "TRUE"}):
            assert is_notifications_enabled() is True
        with patch.dict(os.environ, {"DISCORD_NOTIFICATIONS_ENABLED": "True"}):
            assert is_notifications_enabled() is True

    def test_get_webhook_url_set(self):
        """Test getting webhook URL when set."""
        test_url = "https://discord.com/api/webhooks/123/abc"
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": test_url}):
            assert get_webhook_url() == test_url

    def test_get_webhook_url_not_set(self):
        """Test getting webhook URL when not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_webhook_url() is None


class TestDiscordNotifications:
    """Tests for Discord webhook notification sending."""

    @responses.activate
    def test_send_block_notification_success(self):
        """Test successful block notification."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, json={}, status=204)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("reddit.com", "block")

        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.url == webhook_url
        assert request.method == "POST"

        payload = json.loads(request.body)
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

        embed = payload["embeds"][0]
        assert embed["title"] == "Domain Blocked"
        assert embed["description"] == "reddit.com"
        assert embed["color"] == COLOR_BLOCK
        assert embed["footer"]["text"] == "NextDNS Blocker"
        assert "timestamp" in embed

    @responses.activate
    def test_send_unblock_notification_success(self):
        """Test successful unblock notification."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, json={}, status=204)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("reddit.com", "unblock")

        assert len(responses.calls) == 1
        request = responses.calls[0].request
        payload = json.loads(request.body)
        embed = payload["embeds"][0]
        assert embed["title"] == "Domain Unblocked"
        assert embed["description"] == "reddit.com"
        assert embed["color"] == COLOR_UNBLOCK

    @responses.activate
    def test_notification_disabled(self):
        """Test that no notification is sent when disabled."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "false",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("reddit.com", "block")

        assert len(responses.calls) == 0

    @responses.activate
    def test_no_webhook_url(self):
        """Test that no notification is sent when webhook URL is not set."""
        with patch.dict(os.environ, {"DISCORD_NOTIFICATIONS_ENABLED": "true"}):
            send_discord_notification("reddit.com", "block")

        assert len(responses.calls) == 0

    def test_notification_timeout(self):
        """Test that notification handles timeout gracefully."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"

        with patch("requests.post") as mock_post:
            # Simulate timeout exception
            mock_post.side_effect = requests.exceptions.Timeout("Request timeout")

            with patch.dict(
                os.environ,
                {
                    "DISCORD_NOTIFICATIONS_ENABLED": "true",
                    "DISCORD_WEBHOOK_URL": webhook_url,
                },
            ):
                # Should not raise exception
                send_discord_notification("reddit.com", "block")

            # Verify request was attempted
            mock_post.assert_called_once()

    @responses.activate
    def test_notification_http_error(self):
        """Test that notification handles HTTP errors gracefully."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, json={"error": "Invalid webhook"}, status=404)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            # Should not raise exception
            send_discord_notification("reddit.com", "block")

        assert len(responses.calls) == 1

    @responses.activate
    def test_invalid_event_type(self):
        """Test that invalid event types are handled gracefully."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("reddit.com", "invalid_event")

        assert len(responses.calls) == 0

    @responses.activate
    def test_notification_payload_structure(self):
        """Test that notification payload has correct structure."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, json={}, status=204)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("example.com", "block")

        request = responses.calls[0].request
        payload = json.loads(request.body)

        # Verify payload structure
        assert isinstance(payload, dict)
        assert "embeds" in payload
        assert isinstance(payload["embeds"], list)
        assert len(payload["embeds"]) == 1

        embed = payload["embeds"][0]
        assert "title" in embed
        assert "description" in embed
        assert "color" in embed
        assert "timestamp" in embed
        assert "footer" in embed
        assert embed["footer"]["text"] == "NextDNS Blocker"

        # Verify timestamp format (ISO format with timezone)
        timestamp = embed["timestamp"]
        # Should be parseable as ISO datetime
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    @responses.activate
    def test_notification_uses_correct_timeout(self):
        """Test that notification uses the correct timeout value."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 204
            mock_post.return_value.raise_for_status = lambda: None

            with patch.dict(
                os.environ,
                {
                    "DISCORD_NOTIFICATIONS_ENABLED": "true",
                    "DISCORD_WEBHOOK_URL": webhook_url,
                },
            ):
                send_discord_notification("example.com", "block")

            # Verify timeout was used
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["timeout"] == NOTIFICATION_TIMEOUT


class TestAllowlistNotifications:
    """Tests for allowlist notification types (allow/disallow)."""

    def test_allow_notification_has_correct_color(self):
        """Test that allow notifications use the correct color."""
        from nextdns_blocker.notifications import COLOR_ALLOW

        assert COLOR_ALLOW == 3066993  # Green

    def test_disallow_notification_has_correct_color(self):
        """Test that disallow notifications use the correct color."""
        from nextdns_blocker.notifications import COLOR_DISALLOW

        assert COLOR_DISALLOW == 15105570  # Orange

    @responses.activate
    def test_allow_notification_sent_with_correct_title(self):
        """Test that allow notification is sent with correct title."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, status=204)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("aws.amazon.com", "allow")

        assert len(responses.calls) == 1
        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["embeds"][0]["title"] == "Domain Added to Allowlist"
        assert request_body["embeds"][0]["description"] == "aws.amazon.com"

    @responses.activate
    def test_disallow_notification_sent_with_correct_title(self):
        """Test that disallow notification is sent with correct title."""
        webhook_url = "https://discord.com/api/webhooks/123/abc"
        responses.add(responses.POST, webhook_url, status=204)

        with patch.dict(
            os.environ,
            {
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
                "DISCORD_WEBHOOK_URL": webhook_url,
            },
        ):
            send_discord_notification("aws.amazon.com", "disallow")

        assert len(responses.calls) == 1
        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["embeds"][0]["title"] == "Domain Removed from Allowlist"
        assert request_body["embeds"][0]["description"] == "aws.amazon.com"
