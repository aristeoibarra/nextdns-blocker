#!/usr/bin/env python3
"""
Notification module for NextDNS Blocker.

Supports multiple notification channels:
- Email (SMTP)
- Telegram bot
- Discord webhook
- Slack webhook
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


# =============================================================================
# NOTIFICATION TYPES
# =============================================================================

class NotificationError(Exception):
    """Base exception for notification errors."""
    pass


class NotificationManager:
    """Manages notifications across multiple channels."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the notification manager.

        Args:
            config: Configuration dictionary with notification settings
        """
        self.config = config
        self.enabled_channels: List[str] = []

        # Check which channels are enabled
        if self._is_email_enabled():
            self.enabled_channels.append("email")
        if self._is_telegram_enabled():
            self.enabled_channels.append("telegram")
        if self._is_discord_enabled():
            self.enabled_channels.append("discord")
        if self._is_slack_enabled():
            self.enabled_channels.append("slack")

        if self.enabled_channels:
            logger.info(f"Notifications enabled for: {', '.join(self.enabled_channels)}")
        else:
            logger.debug("No notification channels enabled")

    def _is_email_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return bool(
            self.config.get('NOTIFICATION_EMAIL_ENABLED', '').lower() == 'true' and
            self.config.get('NOTIFICATION_EMAIL_SMTP_HOST') and
            self.config.get('NOTIFICATION_EMAIL_TO')
        )

    def _is_telegram_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return bool(
            self.config.get('NOTIFICATION_TELEGRAM_ENABLED', '').lower() == 'true' and
            self.config.get('NOTIFICATION_TELEGRAM_BOT_TOKEN') and
            self.config.get('NOTIFICATION_TELEGRAM_CHAT_ID')
        )

    def _is_discord_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return bool(
            self.config.get('NOTIFICATION_DISCORD_ENABLED', '').lower() == 'true' and
            self.config.get('NOTIFICATION_DISCORD_WEBHOOK_URL')
        )

    def _is_slack_enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return bool(
            self.config.get('NOTIFICATION_SLACK_ENABLED', '').lower() == 'true' and
            self.config.get('NOTIFICATION_SLACK_WEBHOOK_URL')
        )

    def send_notification(
        self,
        title: str,
        message: str,
        event_type: str = "info"
    ) -> bool:
        """
        Send notification to all enabled channels.

        Args:
            title: Notification title
            message: Notification message
            event_type: Type of event (info, success, warning, error)

        Returns:
            True if at least one notification was sent successfully
        """
        if not self.enabled_channels:
            return False

        success = False
        for channel in self.enabled_channels:
            try:
                if channel == "email":
                    if self._send_email(title, message, event_type):
                        success = True
                elif channel == "telegram":
                    if self._send_telegram(title, message, event_type):
                        success = True
                elif channel == "discord":
                    if self._send_discord(title, message, event_type):
                        success = True
                elif channel == "slack":
                    if self._send_slack(title, message, event_type):
                        success = True
            except Exception as e:
                logger.warning(f"Failed to send {channel} notification: {e}")

        return success

    def _send_email(
        self,
        title: str,
        message: str,
        event_type: str
    ) -> bool:
        """
        Send email notification via SMTP.

        Args:
            title: Email subject
            message: Email body
            event_type: Type of event

        Returns:
            True if sent successfully
        """
        try:
            smtp_host = self.config.get('NOTIFICATION_EMAIL_SMTP_HOST')
            smtp_port = int(self.config.get('NOTIFICATION_EMAIL_SMTP_PORT', '587'))
            smtp_user = self.config.get('NOTIFICATION_EMAIL_SMTP_USER', '')
            smtp_password = self.config.get('NOTIFICATION_EMAIL_SMTP_PASSWORD', '')
            smtp_from = self.config.get('NOTIFICATION_EMAIL_FROM', smtp_user)
            smtp_to = self.config.get('NOTIFICATION_EMAIL_TO')
            use_tls = self.config.get('NOTIFICATION_EMAIL_USE_TLS', 'true').lower() == 'true'

            if not smtp_host or not smtp_to:
                return False

            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_from
            msg['To'] = smtp_to
            msg['Subject'] = f"NextDNS Blocker: {title}"

            # Add body
            body = f"{message}\n\nEvent Type: {event_type}\nTimestamp: {datetime.now().isoformat()}"
            msg.attach(MIMEText(body, 'plain'))

            # Send email
            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.send_message(msg)
            server.quit()

            logger.debug(f"Email notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    def _send_telegram(
        self,
        title: str,
        message: str,
        event_type: str
    ) -> bool:
        """
        Send Telegram notification via bot.

        Args:
            title: Notification title
            message: Notification message
            event_type: Type of event

        Returns:
            True if sent successfully
        """
        try:
            bot_token = self.config.get('NOTIFICATION_TELEGRAM_BOT_TOKEN')
            chat_id = self.config.get('NOTIFICATION_TELEGRAM_CHAT_ID')

            if not bot_token or not chat_id:
                return False

            # Format message with emoji based on event type
            emoji_map = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌"
            }
            emoji = emoji_map.get(event_type, "ℹ️")

            text = f"{emoji} *{title}*\n\n{message}\n\n_Type: {event_type}_"
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.debug(f"Telegram notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _send_discord(
        self,
        title: str,
        message: str,
        event_type: str
    ) -> bool:
        """
        Send Discord notification via webhook.

        Args:
            title: Notification title
            message: Notification message
            event_type: Type of event

        Returns:
            True if sent successfully
        """
        try:
            webhook_url = self.config.get('NOTIFICATION_DISCORD_WEBHOOK_URL')

            if not webhook_url:
                return False

            # Color mapping for Discord embeds
            color_map = {
                "info": 3447003,      # Blue
                "success": 3066993,    # Green
                "warning": 15105570,   # Orange
                "error": 15158332      # Red
            }
            color = color_map.get(event_type, 3447003)

            # Create embed
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "fields": [
                    {
                        "name": "Event Type",
                        "value": event_type,
                        "inline": True
                    },
                    {
                        "name": "Timestamp",
                        "value": datetime.now().isoformat(),
                        "inline": True
                    }
                ]
            }

            payload = {
                "embeds": [embed]
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.debug(f"Discord notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    def _send_slack(
        self,
        title: str,
        message: str,
        event_type: str
    ) -> bool:
        """
        Send Slack notification via webhook.

        Args:
            title: Notification title
            message: Notification message
            event_type: Type of event

        Returns:
            True if sent successfully
        """
        try:
            webhook_url = self.config.get('NOTIFICATION_SLACK_WEBHOOK_URL')

            if not webhook_url:
                return False

            # Emoji mapping for Slack
            emoji_map = {
                "info": ":information_source:",
                "success": ":white_check_mark:",
                "warning": ":warning:",
                "error": ":x:"
            }
            emoji = emoji_map.get(event_type, ":information_source:")

            # Color mapping for Slack attachments
            color_map = {
                "info": "#36a64f",
                "success": "good",
                "warning": "warning",
                "error": "danger"
            }
            color = color_map.get(event_type, "#36a64f")

            # Create Slack message
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {title}",
                        "text": message,
                        "fields": [
                            {
                                "title": "Event Type",
                                "value": event_type,
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.now().isoformat(),
                                "short": True
                            }
                        ],
                        "footer": "NextDNS Blocker",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.debug(f"Slack notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def notify_block(self, domain: str, reason: str = "") -> bool:
        """
        Send notification when a domain is blocked.

        Args:
            domain: Domain that was blocked
            reason: Optional reason for blocking

        Returns:
            True if notification was sent successfully
        """
        title = "Domain Blocked"
        message = f"Domain *{domain}* has been blocked."
        if reason:
            message += f"\nReason: {reason}"

        return self.send_notification(title, message, event_type="success")

    def notify_unblock(self, domain: str, reason: str = "") -> bool:
        """
        Send notification when a domain is unblocked.

        Args:
            domain: Domain that was unblocked
            reason: Optional reason for unblocking

        Returns:
            True if notification was sent successfully
        """
        title = "Domain Unblocked"
        message = f"Domain *{domain}* has been unblocked."
        if reason:
            message += f"\nReason: {reason}"

        return self.send_notification(title, message, event_type="info")

    def notify_error(self, error_message: str, context: str = "") -> bool:
        """
        Send notification when an error occurs.

        Args:
            error_message: Error message
            context: Optional context about where the error occurred

        Returns:
            True if notification was sent successfully
        """
        title = "Error Occurred"
        message = f"An error occurred: {error_message}"
        if context:
            message += f"\nContext: {context}"

        return self.send_notification(title, message, event_type="error")

    def notify_warning(self, warning_message: str, context: str = "") -> bool:
        """
        Send notification for a warning.

        Args:
            warning_message: Warning message
            context: Optional context

        Returns:
            True if notification was sent successfully
        """
        title = "Warning"
        message = warning_message
        if context:
            message += f"\nContext: {context}"

        return self.send_notification(title, message, event_type="warning")

