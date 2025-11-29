"""Tests for notification module."""

import pytest
import smtplib
from unittest.mock import Mock, patch, MagicMock
import requests

from notifications import NotificationManager, NotificationError


@pytest.fixture
def email_config():
    """Email notification configuration."""
    return {
        'NOTIFICATION_EMAIL_ENABLED': 'true',
        'NOTIFICATION_EMAIL_SMTP_HOST': 'smtp.gmail.com',
        'NOTIFICATION_EMAIL_SMTP_PORT': '587',
        'NOTIFICATION_EMAIL_SMTP_USER': 'test@gmail.com',
        'NOTIFICATION_EMAIL_SMTP_PASSWORD': 'test_password',
        'NOTIFICATION_EMAIL_FROM': 'test@gmail.com',
        'NOTIFICATION_EMAIL_TO': 'recipient@example.com',
        'NOTIFICATION_EMAIL_USE_TLS': 'true'
    }


@pytest.fixture
def telegram_config():
    """Telegram notification configuration."""
    return {
        'NOTIFICATION_TELEGRAM_ENABLED': 'true',
        'NOTIFICATION_TELEGRAM_BOT_TOKEN': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
        'NOTIFICATION_TELEGRAM_CHAT_ID': '123456789'
    }


@pytest.fixture
def discord_config():
    """Discord notification configuration."""
    return {
        'NOTIFICATION_DISCORD_ENABLED': 'true',
        'NOTIFICATION_DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/123456/abcdef'
    }


@pytest.fixture
def slack_config():
    """Slack notification configuration."""
    return {
        'NOTIFICATION_SLACK_ENABLED': 'true',
        'NOTIFICATION_SLACK_WEBHOOK_URL': 'https://hooks.slack.com/services/TEST/WEBHOOK/URL'
    }


@pytest.fixture
def all_channels_config(email_config, telegram_config, discord_config, slack_config):
    """Configuration with all notification channels enabled."""
    config = {}
    config.update(email_config)
    config.update(telegram_config)
    config.update(discord_config)
    config.update(slack_config)
    return config


class TestNotificationManagerInitialization:
    """Tests for NotificationManager initialization."""

    def test_init_no_channels_enabled(self):
        """Test initialization with no channels configured."""
        manager = NotificationManager({})
        assert manager.enabled_channels == []

    def test_init_email_enabled(self, email_config):
        """Test initialization with email enabled."""
        manager = NotificationManager(email_config)
        assert 'email' in manager.enabled_channels
        assert len(manager.enabled_channels) == 1

    def test_init_telegram_enabled(self, telegram_config):
        """Test initialization with Telegram enabled."""
        manager = NotificationManager(telegram_config)
        assert 'telegram' in manager.enabled_channels
        assert len(manager.enabled_channels) == 1

    def test_init_discord_enabled(self, discord_config):
        """Test initialization with Discord enabled."""
        manager = NotificationManager(discord_config)
        assert 'discord' in manager.enabled_channels
        assert len(manager.enabled_channels) == 1

    def test_init_slack_enabled(self, slack_config):
        """Test initialization with Slack enabled."""
        manager = NotificationManager(slack_config)
        assert 'slack' in manager.enabled_channels
        assert len(manager.enabled_channels) == 1

    def test_init_all_channels_enabled(self, all_channels_config):
        """Test initialization with all channels enabled."""
        manager = NotificationManager(all_channels_config)
        assert len(manager.enabled_channels) == 4
        assert 'email' in manager.enabled_channels
        assert 'telegram' in manager.enabled_channels
        assert 'discord' in manager.enabled_channels
        assert 'slack' in manager.enabled_channels

    def test_init_email_disabled_when_enabled_false(self):
        """Test that email is not enabled when NOTIFICATION_EMAIL_ENABLED is false."""
        config = {
            'NOTIFICATION_EMAIL_ENABLED': 'false',
            'NOTIFICATION_EMAIL_SMTP_HOST': 'smtp.gmail.com',
            'NOTIFICATION_EMAIL_TO': 'test@example.com'
        }
        manager = NotificationManager(config)
        assert 'email' not in manager.enabled_channels

    def test_init_email_disabled_when_missing_required(self):
        """Test that email is not enabled when required fields are missing."""
        config = {
            'NOTIFICATION_EMAIL_ENABLED': 'true',
            'NOTIFICATION_EMAIL_SMTP_HOST': 'smtp.gmail.com'
            # Missing NOTIFICATION_EMAIL_TO
        }
        manager = NotificationManager(config)
        assert 'email' not in manager.enabled_channels


class TestEmailNotifications:
    """Tests for email notifications."""

    @patch('notifications.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp, email_config):
        """Test successful email notification."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        manager = NotificationManager(email_config)
        result = manager._send_email("Test Title", "Test message", "info")

        assert result is True
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@gmail.com', 'test_password')
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch('notifications.smtplib.SMTP')
    def test_send_email_no_tls(self, mock_smtp, email_config):
        """Test email notification without TLS."""
        email_config['NOTIFICATION_EMAIL_USE_TLS'] = 'false'
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        manager = NotificationManager(email_config)
        result = manager._send_email("Test Title", "Test message", "info")

        assert result is True
        mock_server.starttls.assert_not_called()

    @patch('notifications.smtplib.SMTP')
    def test_send_email_no_auth(self, mock_smtp, email_config):
        """Test email notification without authentication."""
        email_config['NOTIFICATION_EMAIL_SMTP_USER'] = ''
        email_config['NOTIFICATION_EMAIL_SMTP_PASSWORD'] = ''
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        manager = NotificationManager(email_config)
        result = manager._send_email("Test Title", "Test message", "info")

        assert result is True
        mock_server.login.assert_not_called()

    @patch('notifications.smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp, email_config):
        """Test email notification failure."""
        mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

        manager = NotificationManager(email_config)
        result = manager._send_email("Test Title", "Test message", "info")

        assert result is False

    def test_send_email_missing_config(self):
        """Test email notification with missing configuration."""
        manager = NotificationManager({})
        result = manager._send_email("Test Title", "Test message", "info")
        assert result is False


class TestTelegramNotifications:
    """Tests for Telegram notifications."""

    @patch('notifications.requests.post')
    def test_send_telegram_success(self, mock_post, telegram_config):
        """Test successful Telegram notification."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(telegram_config)
        result = manager._send_telegram("Test Title", "Test message", "success")

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['chat_id'] == '123456789'
        assert 'Test Title' in call_args[1]['json']['text']
        assert call_args[1]['json']['parse_mode'] == 'Markdown'

    @patch('notifications.requests.post')
    def test_send_telegram_error_event(self, mock_post, telegram_config):
        """Test Telegram notification with error event type."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(telegram_config)
        result = manager._send_telegram("Error", "Something went wrong", "error")

        assert result is True
        call_args = mock_post.call_args
        assert '❌' in call_args[1]['json']['text']

    @patch('notifications.requests.post')
    def test_send_telegram_failure(self, mock_post, telegram_config):
        """Test Telegram notification failure."""
        mock_post.side_effect = requests.exceptions.RequestException("Connection failed")

        manager = NotificationManager(telegram_config)
        result = manager._send_telegram("Test Title", "Test message", "info")

        assert result is False

    def test_send_telegram_missing_config(self):
        """Test Telegram notification with missing configuration."""
        manager = NotificationManager({})
        result = manager._send_telegram("Test Title", "Test message", "info")
        assert result is False


class TestDiscordNotifications:
    """Tests for Discord notifications."""

    @patch('notifications.requests.post')
    def test_send_discord_success(self, mock_post, discord_config):
        """Test successful Discord notification."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(discord_config)
        result = manager._send_discord("Test Title", "Test message", "success")

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://discord.com/api/webhooks/123456/abcdef'
        assert 'embeds' in call_args[1]['json']
        assert call_args[1]['json']['embeds'][0]['title'] == 'Test Title'
        assert call_args[1]['json']['embeds'][0]['color'] == 3066993  # Green for success

    @patch('notifications.requests.post')
    def test_send_discord_error_event(self, mock_post, discord_config):
        """Test Discord notification with error event type."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(discord_config)
        result = manager._send_discord("Error", "Something went wrong", "error")

        assert result is True
        call_args = mock_post.call_args
        assert call_args[1]['json']['embeds'][0]['color'] == 15158332  # Red for error

    @patch('notifications.requests.post')
    def test_send_discord_failure(self, mock_post, discord_config):
        """Test Discord notification failure."""
        mock_post.side_effect = requests.exceptions.RequestException("Connection failed")

        manager = NotificationManager(discord_config)
        result = manager._send_discord("Test Title", "Test message", "info")

        assert result is False

    def test_send_discord_missing_config(self):
        """Test Discord notification with missing configuration."""
        manager = NotificationManager({})
        result = manager._send_discord("Test Title", "Test message", "info")
        assert result is False


class TestSlackNotifications:
    """Tests for Slack notifications."""

    @patch('notifications.requests.post')
    def test_send_slack_success(self, mock_post, slack_config):
        """Test successful Slack notification."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(slack_config)
        result = manager._send_slack("Test Title", "Test message", "success")

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://hooks.slack.com/services/TEST/WEBHOOK/URL'
        assert 'attachments' in call_args[1]['json']
        assert call_args[1]['json']['attachments'][0]['title'] == ':white_check_mark: Test Title'
        assert call_args[1]['json']['attachments'][0]['color'] == 'good'

    @patch('notifications.requests.post')
    def test_send_slack_warning_event(self, mock_post, slack_config):
        """Test Slack notification with warning event type."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = NotificationManager(slack_config)
        result = manager._send_slack("Warning", "Something to watch", "warning")

        assert result is True
        call_args = mock_post.call_args
        assert call_args[1]['json']['attachments'][0]['color'] == 'warning'

    @patch('notifications.requests.post')
    def test_send_slack_failure(self, mock_post, slack_config):
        """Test Slack notification failure."""
        mock_post.side_effect = requests.exceptions.RequestException("Connection failed")

        manager = NotificationManager(slack_config)
        result = manager._send_slack("Test Title", "Test message", "info")

        assert result is False

    def test_send_slack_missing_config(self):
        """Test Slack notification with missing configuration."""
        manager = NotificationManager({})
        result = manager._send_slack("Test Title", "Test message", "info")
        assert result is False


class TestNotificationMethods:
    """Tests for high-level notification methods."""

    @patch('notifications.NotificationManager._send_email')
    def test_notify_block(self, mock_send_email, email_config):
        """Test notify_block method."""
        mock_send_email.return_value = True
        manager = NotificationManager(email_config)
        result = manager.notify_block("example.com", "Scheduled block")
        assert result is True
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == "Domain Blocked"
        assert "example.com" in call_args[0][1]
        assert call_args[0][2] == "success"

    @patch('notifications.NotificationManager._send_telegram')
    def test_notify_unblock(self, mock_send_telegram, telegram_config):
        """Test notify_unblock method."""
        mock_send_telegram.return_value = True
        manager = NotificationManager(telegram_config)
        result = manager.notify_unblock("example.com", "Scheduled unblock")
        assert result is True
        mock_send_telegram.assert_called_once()
        call_args = mock_send_telegram.call_args
        assert call_args[0][0] == "Domain Unblocked"
        assert "example.com" in call_args[0][1]
        assert call_args[0][2] == "info"

    @patch('notifications.NotificationManager._send_discord')
    def test_notify_error(self, mock_send_discord, discord_config):
        """Test notify_error method."""
        mock_send_discord.return_value = True
        manager = NotificationManager(discord_config)
        result = manager.notify_error("API request failed", "NextDNS API")
        assert result is True
        mock_send_discord.assert_called_once()
        call_args = mock_send_discord.call_args
        assert call_args[0][0] == "Error Occurred"
        assert "API request failed" in call_args[0][1]
        assert call_args[0][2] == "error"

    @patch('notifications.NotificationManager._send_slack')
    def test_notify_warning(self, mock_send_slack, slack_config):
        """Test notify_warning method."""
        mock_send_slack.return_value = True
        manager = NotificationManager(slack_config)
        result = manager.notify_warning("Rate limit approaching", "API usage")
        assert result is True
        mock_send_slack.assert_called_once()
        call_args = mock_send_slack.call_args
        assert call_args[0][0] == "Warning"
        assert "Rate limit approaching" in call_args[0][1]
        assert call_args[0][2] == "warning"


class TestMultipleChannels:
    """Tests for multiple notification channels."""

    @patch('notifications.NotificationManager._send_email')
    @patch('notifications.NotificationManager._send_telegram')
    @patch('notifications.NotificationManager._send_discord')
    @patch('notifications.NotificationManager._send_slack')
    def test_send_notification_all_channels(
        self, mock_slack, mock_discord, mock_telegram, mock_email, all_channels_config
    ):
        """Test sending notification to all enabled channels."""
        mock_email.return_value = True
        mock_telegram.return_value = True
        mock_discord.return_value = True
        mock_slack.return_value = True

        manager = NotificationManager(all_channels_config)
        result = manager.send_notification("Test Title", "Test message", "info")

        assert result is True
        mock_email.assert_called_once()
        mock_telegram.assert_called_once()
        mock_discord.assert_called_once()
        mock_slack.assert_called_once()

    @patch('notifications.NotificationManager._send_email')
    @patch('notifications.NotificationManager._send_telegram')
    def test_send_notification_partial_failure(
        self, mock_telegram, mock_email, email_config, telegram_config
    ):
        """Test notification when some channels fail."""
        config = {**email_config, **telegram_config}
        mock_email.return_value = True
        mock_telegram.return_value = False  # Telegram fails

        manager = NotificationManager(config)
        result = manager.send_notification("Test Title", "Test message", "info")

        assert result is True  # At least one succeeded
        mock_email.assert_called_once()
        mock_telegram.assert_called_once()

    def test_send_notification_no_channels(self):
        """Test sending notification when no channels are enabled."""
        manager = NotificationManager({})
        result = manager.send_notification("Test Title", "Test message", "info")
        assert result is False


class TestEventTypes:
    """Tests for different event types."""

    @patch('notifications.NotificationManager._send_telegram')
    def test_event_type_info(self, mock_send, telegram_config):
        """Test info event type."""
        mock_send.return_value = True
        manager = NotificationManager(telegram_config)
        manager.send_notification("Info", "Message", "info")
        call_args = mock_send.call_args
        assert call_args[0][2] == "info"
        assert "ℹ️" in call_args[0][1] or "ℹ" in call_args[0][1]

    @patch('notifications.NotificationManager._send_telegram')
    def test_event_type_success(self, mock_send, telegram_config):
        """Test success event type."""
        mock_send.return_value = True
        manager = NotificationManager(telegram_config)
        manager.send_notification("Success", "Message", "success")
        call_args = mock_send.call_args
        assert call_args[0][2] == "success"
        assert "✅" in call_args[0][1]

    @patch('notifications.NotificationManager._send_telegram')
    def test_event_type_warning(self, mock_send, telegram_config):
        """Test warning event type."""
        mock_send.return_value = True
        manager = NotificationManager(telegram_config)
        manager.send_notification("Warning", "Message", "warning")
        call_args = mock_send.call_args
        assert call_args[0][2] == "warning"
        assert "⚠️" in call_args[0][1] or "⚠" in call_args[0][1]

    @patch('notifications.NotificationManager._send_telegram')
    def test_event_type_error(self, mock_send, telegram_config):
        """Test error event type."""
        mock_send.return_value = True
        manager = NotificationManager(telegram_config)
        manager.send_notification("Error", "Message", "error")
        call_args = mock_send.call_args
        assert call_args[0][2] == "error"
        assert "❌" in call_args[0][1]

