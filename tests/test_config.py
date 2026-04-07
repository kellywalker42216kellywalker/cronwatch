"""Tests for the cronwatch configuration module."""

import os
import pytest
import tempfile
import yaml

from cronwatch.config import Config, ConfigError


@pytest.fixture
def minimal_config():
    """Return a minimal valid config dictionary."""
    return {
        "jobs": {
            "test_job": {
                "command": "echo hello",
                "schedule": "0 * * * *"
            }
        }
    }


@pytest.fixture
def full_config():
    """Return a full config dictionary with all optional fields."""
    return {
        "log_dir": "/tmp/cronwatch_test_logs",
        "log_level": "DEBUG",
        "timeout": 300,
        "slack": {
            "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
            "channel": "#alerts",
            "username": "cronwatch"
        },
        "email": {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "from_address": "cron@example.com",
            "to_addresses": ["admin@example.com"],
            "use_tls": True
        },
        "jobs": {
            "backup_job": {
                "command": "/usr/local/bin/backup.sh",
                "schedule": "0 2 * * *",
                "timeout": 600,
                "notify_on": ["failure", "timeout"],
                "env": {
                    "BACKUP_DIR": "/mnt/backups"
                }
            }
        }
    }


@pytest.fixture
def config_file(minimal_config):
    """Write a minimal config to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(minimal_config, f)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def full_config_file(full_config):
    """Write a full config to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(full_config, f)
        path = f.name
    yield path
    os.unlink(path)


class TestConfigLoading:
    """Tests for loading and parsing configuration files."""

    def test_load_minimal_config(self, config_file):
        config = Config(config_path=config_file)
        assert config is not None
        assert "test_job" in config.jobs

    def test_load_full_config(self, full_config_file):
        config = Config(config_path=full_config_file)
        assert config.log_level == "DEBUG"
        assert config.slack is not None
        assert config.email is not None
        assert "backup_job" in config.jobs

    def test_missing_config_file_raises(self):
        with pytest.raises((ConfigError, FileNotFoundError)):
            Config(config_path="/nonexistent/path/config.yaml")

    def test_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(": invalid: yaml: content: [\n")
            path = f.name
        try:
            with pytest.raises((ConfigError, Exception)):
                Config(config_path=path)
        finally:
            os.unlink(path)

    def test_missing_jobs_section_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump({"log_level": "INFO"}, f)
            path = f.name
        try:
            with pytest.raises(ConfigError):
                Config(config_path=path)
        finally:
            os.unlink(path)


class TestJobConfig:
    """Tests for per-job configuration parsing."""

    def test_job_has_command(self, config_file):
        config = Config(config_path=config_file)
        job = config.jobs["test_job"]
        assert job.get("command") == "echo hello"

    def test_job_inherits_global_timeout(self, full_config_file):
        config = Config(config_path=full_config_file)
        # Global timeout is 300; job-level overrides to 600
        job = config.jobs["backup_job"]
        assert job.get("timeout") == 600

    def test_job_notify_on_defaults(self, config_file):
        config = Config(config_path=config_file)
        job = config.jobs["test_job"]
        # Should default to notifying on failure
        notify_on = job.get("notify_on", ["failure"])
        assert "failure" in notify_on


class TestSlackConfig:
    """Tests for Slack notifier configuration."""

    def test_slack_config_parsed(self, full_config_file):
        config = Config(config_path=full_config_file)
        assert config.slack["webhook_url"].startswith("https://")
        assert config.slack["channel"] == "#alerts"

    def test_no_slack_config_returns_none(self, config_file):
        config = Config(config_path=config_file)
        assert config.slack is None


class TestEmailConfig:
    """Tests for email notifier configuration."""

    def test_email_config_parsed(self, full_config_file):
        config = Config(config_path=full_config_file)
        assert config.email["smtp_host"] == "smtp.example.com"
        assert config.email["smtp_port"] == 587
        assert "admin@example.com" in config.email["to_addresses"]

    def test_no_email_config_returns_none(self, config_file):
        config = Config(config_path=config_file)
        assert config.email is None
