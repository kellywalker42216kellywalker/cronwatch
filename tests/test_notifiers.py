"""Tests for cronwatch notifiers (Slack and Email)."""

import pytest
from unittest.mock import patch, MagicMock, call
from cronwatch.notifiers import SlackNotifier, EmailNotifier, NotificationError


@pytest.fixture
def slack_config():
    return {
        "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
        "channel": "#alerts",
        "username": "CronWatch",
    }


@pytest.fixture
def email_config():
    return {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "username": "user@example.com",
        "password": "secret",
        "from_addr": "cronwatch@example.com",
        "to_addrs": ["admin@example.com", "ops@example.com"],
        "use_tls": True,
    }


@pytest.fixture
def job_result():
    return {
        "job_name": "backup_job",
        "exit_code": 1,
        "stdout": "Backup started...",
        "stderr": "Error: disk full",
        "duration": 42.5,
        "start_time": "2024-01-15T10:00:00",
    }


class TestSlackNotifier:
    def test_init(self, slack_config):
        notifier = SlackNotifier(slack_config)
        assert notifier.webhook_url == slack_config["webhook_url"]
        assert notifier.channel == slack_config["channel"]

    def test_init_missing_webhook_raises(self):
        with pytest.raises((KeyError, NotificationError)):
            SlackNotifier({})

    @patch("cronwatch.notifiers.urllib.request.urlopen")
    def test_send_success(self, mock_urlopen, slack_config, job_result):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__ = lambda s: mock_response
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        notifier = SlackNotifier(slack_config)
        # Should not raise
        notifier.send(job_result)
        assert mock_urlopen.called

    @patch("cronwatch.notifiers.urllib.request.urlopen")
    def test_send_http_error_raises(self, mock_urlopen, slack_config, job_result):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=None, code=500, msg="Server Error", hdrs=None, fp=None
        )

        notifier = SlackNotifier(slack_config)
        with pytest.raises(NotificationError):
            notifier.send(job_result)

    @patch("cronwatch.notifiers.urllib.request.urlopen")
    def test_send_url_error_raises(self, mock_urlopen, slack_config, job_result):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        notifier = SlackNotifier(slack_config)
        with pytest.raises(NotificationError):
            notifier.send(job_result)

    def test_build_payload_contains_job_name(self, slack_config, job_result):
        notifier = SlackNotifier(slack_config)
        payload = notifier._build_payload(job_result)
        payload_str = str(payload)
        assert "backup_job" in payload_str

    def test_build_payload_contains_exit_code(self, slack_config, job_result):
        notifier = SlackNotifier(slack_config)
        payload = notifier._build_payload(job_result)
        payload_str = str(payload)
        assert "1" in payload_str


class TestEmailNotifier:
    def test_init(self, email_config):
        notifier = EmailNotifier(email_config)
        assert notifier.smtp_host == email_config["smtp_host"]
        assert notifier.smtp_port == email_config["smtp_port"]
        assert notifier.to_addrs == email_config["to_addrs"]

    def test_init_missing_host_raises(self):
        with pytest.raises((KeyError, NotificationError)):
            EmailNotifier({})

    @patch("cronwatch.notifiers.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class, email_config, job_result):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(email_config)
        notifier.send(job_result)

        assert mock_smtp_class.called

    @patch("cronwatch.notifiers.smtplib.SMTP")
    def test_send_smtp_error_raises(self, mock_smtp_class, email_config, job_result):
        import smtplib
        mock_smtp_class.side_effect = smtplib.SMTPException("connection failed")

        notifier = EmailNotifier(email_config)
        with pytest.raises(NotificationError):
            notifier.send(job_result)

    def test_build_message_subject_contains_job_name(self, email_config, job_result):
        notifier = EmailNotifier(email_config)
        msg = notifier._build_message(job_result)
        assert "backup_job" in msg["Subject"]

    def test_build_message_failure_subject(self, email_config, job_result):
        notifier = EmailNotifier(email_config)
        msg = notifier._build_message(job_result)
        # Exit code 1 should indicate failure in subject
        assert "FAILED" in msg["Subject"] or "fail" in msg["Subject"].lower()

    def test_build_message_success_subject(self, email_config, job_result):
        job_result["exit_code"] = 0
        notifier = EmailNotifier(email_config)
        msg = notifier._build_message(job_result)
        assert "SUCCESS" in msg["Subject"] or "success" in msg["Subject"].lower()

    def test_build_message_recipients(self, email_config, job_result):
        notifier = EmailNotifier(email_config)
        msg = notifier._build_message(job_result)
        assert "admin@example.com" in msg["To"]
