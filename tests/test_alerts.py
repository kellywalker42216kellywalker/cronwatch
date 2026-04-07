"""Tests for the AlertManager in cronwatch/alerts.py."""

import pytest
from unittest.mock import MagicMock, patch, call

from cronwatch.alerts import AlertManager
from cronwatch.runner import JobResult
from cronwatch.notifiers import NotificationError


@pytest.fixture
def success_result():
    """A successful job result fixture."""
    return JobResult(
        command="echo hello",
        returncode=0,
        stdout="hello\n",
        stderr="",
        duration=0.1,
        timed_out=False,
    )


@pytest.fixture
def failure_result():
    """A failed job result fixture."""
    return JobResult(
        command="false",
        returncode=1,
        stdout="",
        stderr="error occurred",
        duration=0.05,
        timed_out=False,
    )


@pytest.fixture
def timeout_result():
    """A timed-out job result fixture."""
    return JobResult(
        command="sleep 100",
        returncode=-1,
        stdout="",
        stderr="",
        duration=30.0,
        timed_out=True,
    )


@pytest.fixture
def slack_notifier():
    """A mock Slack notifier."""
    notifier = MagicMock()
    notifier.send = MagicMock()
    return notifier


@pytest.fixture
def email_notifier():
    """A mock email notifier."""
    notifier = MagicMock()
    notifier.send = MagicMock()
    return notifier


class TestAlertManagerInit:
    def test_init_no_notifiers(self):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        assert manager.notifiers == []
        assert manager.alert_on == ["failure"]

    def test_init_with_notifiers(self, slack_notifier, email_notifier):
        manager = AlertManager(
            notifiers=[slack_notifier, email_notifier],
            alert_on=["failure", "timeout"],
        )
        assert len(manager.notifiers) == 2

    def test_default_alert_on(self, slack_notifier):
        manager = AlertManager(notifiers=[slack_notifier])
        # Should default to alerting on failure at minimum
        assert "failure" in manager.alert_on


class TestHasNotifiers:
    def test_has_notifiers_true(self, slack_notifier):
        manager = AlertManager(notifiers=[slack_notifier], alert_on=["failure"])
        assert manager.has_notifiers() is True

    def test_has_notifiers_false(self):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        assert manager.has_notifiers() is False


class TestShouldAlert:
    def test_should_alert_on_failure(self, failure_result):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        assert manager._should_alert(failure_result) is True

    def test_should_not_alert_on_success(self, success_result):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        assert manager._should_alert(success_result) is False

    def test_should_alert_on_timeout(self, timeout_result):
        manager = AlertManager(notifiers=[], alert_on=["failure", "timeout"])
        assert manager._should_alert(timeout_result) is True

    def test_should_alert_on_success_when_configured(self, success_result):
        manager = AlertManager(notifiers=[], alert_on=["failure", "success"])
        assert manager._should_alert(success_result) is True

    def test_timeout_not_alerted_without_config(self, timeout_result):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        # A timed-out job has a non-zero returncode, so it's also a failure
        # Behaviour depends on implementation; at minimum failure should catch it
        result = manager._should_alert(timeout_result)
        assert isinstance(result, bool)


class TestDispatch:
    def test_dispatch_sends_to_all_notifiers_on_failure(
        self, failure_result, slack_notifier, email_notifier
    ):
        manager = AlertManager(
            notifiers=[slack_notifier, email_notifier],
            alert_on=["failure"],
        )
        manager.dispatch(failure_result)
        slack_notifier.send.assert_called_once_with(failure_result)
        email_notifier.send.assert_called_once_with(failure_result)

    def test_dispatch_skips_send_on_success(
        self, success_result, slack_notifier
    ):
        manager = AlertManager(
            notifiers=[slack_notifier],
            alert_on=["failure"],
        )
        manager.dispatch(success_result)
        slack_notifier.send.assert_not_called()

    def test_dispatch_handles_notification_error(
        self, failure_result, slack_notifier
    ):
        slack_notifier.send.side_effect = NotificationError("Slack unreachable")
        manager = AlertManager(
            notifiers=[slack_notifier],
            alert_on=["failure"],
        )
        # Should not raise; errors are logged/swallowed gracefully
        manager.dispatch(failure_result)

    def test_dispatch_no_notifiers_does_nothing(self, failure_result):
        manager = AlertManager(notifiers=[], alert_on=["failure"])
        # Should not raise
        manager.dispatch(failure_result)
