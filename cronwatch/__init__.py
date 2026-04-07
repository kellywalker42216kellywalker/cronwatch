"""
cronwatch - A lightweight CLI tool to monitor, log, and alert on cron job failures.

Provides Slack and email integration for notifications when cron jobs
fail, timeout, or produce unexpected output.
"""

__version__ = "0.1.0"
__author__ = "cronwatch contributors"
__license__ = "MIT"

from cronwatch.runner import JobResult, JobRunner, JobTimeoutError
from cronwatch.config import Config, ConfigError
from cronwatch.notifiers import SlackNotifier, EmailNotifier, NotificationError
from cronwatch.logger import setup_logging, JobLogger

__all__ = [
    "__version__",
    "JobResult",
    "JobRunner",
    "JobTimeoutError",
    "Config",
    "ConfigError",
    "SlackNotifier",
    "EmailNotifier",
    "NotificationError",
    "setup_logging",
    "JobLogger",
]
