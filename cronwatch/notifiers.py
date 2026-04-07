"""Notification backends for cronwatch.

Supports Slack (via webhook) and email (via SMTP) notifications
when cron jobs fail or recover.
"""

import logging
import smtplib
import urllib.request
import urllib.error
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when a notification fails to send."""
    pass


class SlackNotifier:
    """Send notifications to a Slack channel via incoming webhook."""

    def __init__(self, webhook_url: str, channel: Optional[str] = None,
                 username: str = "cronwatch", icon_emoji: str = ":warning:"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def send(self, subject: str, body: str, success: bool = False) -> None:
        """Send a Slack message.

        Args:
            subject: Short summary (used as attachment title).
            body: Detailed message body.
            success: If True, use a green colour; otherwise red.
        """
        colour = "good" if success else "danger"
        payload: dict = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "fallback": subject,
                    "color": colour,
                    "title": subject,
                    "text": body,
                    "mrkdwn_in": ["text"],
                }
            ],
        }
        if self.channel:
            payload["channel"] = self.channel

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    raise NotificationError(
                        f"Slack returned HTTP {resp.status}"
                    )
        except urllib.error.URLError as exc:
            raise NotificationError(f"Slack request failed: {exc}") from exc

        logger.debug("Slack notification sent: %s", subject)


class EmailNotifier:
    """Send notifications via SMTP."""

    def __init__(self, smtp_host: str, smtp_port: int, sender: str,
                 recipients: list[str], username: Optional[str] = None,
                 password: Optional[str] = None, use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = recipients
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, subject: str, body: str, success: bool = False) -> None:  # noqa: ARG002
        """Send an email notification.

        Args:
            subject: Email subject line.
            body: Plain-text email body.
            success: Unused here but kept for a uniform interface.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(body, "plain"))

        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)

            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(self.sender, self.recipients, msg.as_string())
            server.quit()
        except smtplib.SMTPException as exc:
            raise NotificationError(f"SMTP error: {exc}") from exc

        logger.debug("Email notification sent to %s: %s", self.recipients, subject)


def build_notifiers_from_config(config) -> list:
    """Instantiate notifiers declared in a Config object.

    Returns a (possibly empty) list of notifier instances.
    """
    notifiers = []

    slack_cfg = config.get("slack", {})
    if slack_cfg.get("webhook_url"):
        notifiers.append(
            SlackNotifier(
                webhook_url=slack_cfg["webhook_url"],
                channel=slack_cfg.get("channel"),
                username=slack_cfg.get("username", "cronwatch"),
                icon_emoji=slack_cfg.get("icon_emoji", ":warning:"),
            )
        )

    email_cfg = config.get("email", {})
    if email_cfg.get("smtp_host") and email_cfg.get("recipients"):
        notifiers.append(
            EmailNotifier(
                smtp_host=email_cfg["smtp_host"],
                smtp_port=int(email_cfg.get("smtp_port", 587)),
                sender=email_cfg["sender"],
                recipients=email_cfg["recipients"],
                username=email_cfg.get("username"),
                password=email_cfg.get("password"),
                use_tls=email_cfg.get("use_tls", True),
            )
        )

    return notifiers
