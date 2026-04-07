"""Alert management for cronwatch.

Coordinates notifications across multiple channels (Slack, email)
based on job results and configuration thresholds.
"""

import logging
from typing import Optional

from cronwatch.notifiers import SlackNotifier, EmailNotifier, NotificationError
from cronwatch.runner import JobResult

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert dispatch for job results.

    Reads alert configuration and routes notifications to the
    appropriate notifiers based on job outcome and thresholds.
    """

    def __init__(self, config: dict):
        """Initialize AlertManager with configuration.

        Args:
            config: Dictionary containing alert/notifier configuration,
                    typically from Config.get_job_config().
        """
        self.config = config
        self._slack: Optional[SlackNotifier] = None
        self._email: Optional[EmailNotifier] = None

        slack_cfg = config.get("slack")
        if slack_cfg and slack_cfg.get("enabled", True):
            self._slack = SlackNotifier(slack_cfg)
            logger.debug("Slack notifier initialized")

        email_cfg = config.get("email")
        if email_cfg and email_cfg.get("enabled", True):
            self._email = EmailNotifier(email_cfg)
            logger.debug("Email notifier initialized")

    def _should_alert(self, result: JobResult) -> bool:
        """Determine whether an alert should be sent for this result.

        Alerts are sent when:
        - The job failed (non-zero exit code or timeout)
        - The job succeeded but alert_on_success is configured
        - Output exceeded the configured max_output_lines threshold

        Args:
            result: The completed JobResult to evaluate.

        Returns:
            True if an alert should be dispatched.
        """
        alert_cfg = self.config.get("alerts", {})

        if not result.success:
            return True

        if alert_cfg.get("alert_on_success", False):
            logger.debug("alert_on_success is enabled; alerting on successful job")
            return True

        return False

    def dispatch(self, result: JobResult, job_name: str) -> None:
        """Dispatch alerts for a job result.

        Sends notifications to all configured and enabled notifiers
        when the result meets alerting criteria.

        Args:
            result: The completed JobResult.
            job_name: Human-readable name for the job (used in messages).
        """
        if not self._should_alert(result):
            logger.debug("No alert needed for job '%s' (exit_code=%d)", job_name, result.exit_code)
            return

        logger.info(
            "Dispatching alerts for job '%s' (exit_code=%d, success=%s)",
            job_name,
            result.exit_code,
            result.success,
        )

        errors = []

        if self._slack:
            try:
                self._slack.send(result, job_name)
                logger.debug("Slack alert sent for job '%s'", job_name)
            except NotificationError as exc:
                logger.error("Slack notification failed for job '%s': %s", job_name, exc)
                errors.append(f"slack: {exc}")

        if self._email:
            try:
                self._email.send(result, job_name)
                logger.debug("Email alert sent for job '%s'", job_name)
            except NotificationError as exc:
                logger.error("Email notification failed for job '%s': %s", job_name, exc)
                errors.append(f"email: {exc}")

        if errors:
            # Log aggregate failure but don't raise — partial delivery is
            # better than crashing the monitoring process itself.
            logger.warning(
                "Some notifications failed for job '%s': %s",
                job_name,
                "; ".join(errors),
            )

    @property
    def has_notifiers(self) -> bool:
        """Return True if at least one notifier is configured."""
        return self._slack is not None or self._email is not None
