"""Tests for cronwatch.logger module."""

import logging
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cronwatch.logger import JobLogger, setup_logging


@pytest.fixture
def log_dir(tmp_path):
    """Provide a temporary log directory."""
    log_path = tmp_path / "logs"
    log_path.mkdir()
    return log_path


@pytest.fixture
def logger_config(log_dir):
    """Provide a basic logger configuration dict."""
    return {
        "log_dir": str(log_dir),
        "log_level": "DEBUG",
        "max_bytes": 1024 * 1024,
        "backup_count": 3,
    }


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_returns_logger(self, logger_config):
        logger = setup_logging(logger_config)
        assert isinstance(logger, logging.Logger)

    def test_log_level_debug(self, logger_config):
        logger_config["log_level"] = "DEBUG"
        logger = setup_logging(logger_config)
        assert logger.level == logging.DEBUG

    def test_log_level_info(self, logger_config):
        logger_config["log_level"] = "INFO"
        logger = setup_logging(logger_config)
        assert logger.level == logging.INFO

    def test_log_level_warning(self, logger_config):
        logger_config["log_level"] = "WARNING"
        logger = setup_logging(logger_config)
        assert logger.level == logging.WARNING

    def test_invalid_log_level_defaults_to_info(self, logger_config):
        logger_config["log_level"] = "INVALID"
        logger = setup_logging(logger_config)
        assert logger.level == logging.INFO

    def test_creates_log_file(self, logger_config, log_dir):
        setup_logging(logger_config)
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

    def test_log_dir_created_if_missing(self, tmp_path, logger_config):
        missing_dir = tmp_path / "nonexistent" / "logs"
        logger_config["log_dir"] = str(missing_dir)
        setup_logging(logger_config)
        assert missing_dir.exists()


class TestJobLogger:
    """Tests for the JobLogger context manager."""

    def test_context_manager_enter_returns_self(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger as jl:
            assert jl is job_logger

    def test_records_start_time(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        before = time.time()
        with job_logger:
            after_enter = time.time()
        assert before <= job_logger.start_time <= after_enter

    def test_records_end_time(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        assert job_logger.end_time is not None
        assert job_logger.end_time >= job_logger.start_time

    def test_duration_calculated(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            time.sleep(0.05)
        assert job_logger.duration >= 0.05

    def test_success_result(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=0, stdout="ok", stderr="")
        assert result["success"] is True
        assert result["return_code"] == 0

    def test_failure_result(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=1, stdout="", stderr="error")
        assert result["success"] is False
        assert result["return_code"] == 1

    def test_result_contains_job_name(self, logger_config):
        job_logger = JobLogger(job_name="my_cron_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=0, stdout="", stderr="")
        assert result["job_name"] == "my_cron_job"

    def test_result_contains_duration(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=0, stdout="", stderr="")
        assert "duration" in result
        assert isinstance(result["duration"], float)

    def test_result_contains_stdout(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=0, stdout="hello world", stderr="")
        assert result["stdout"] == "hello world"

    def test_result_contains_stderr(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        result = job_logger.get_result(return_code=1, stdout="", stderr="something failed")
        assert result["stderr"] == "something failed"

    def test_exception_in_context_recorded(self, logger_config):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        try:
            with job_logger:
                raise RuntimeError("unexpected error")
        except RuntimeError:
            pass
        assert job_logger.exception is not None

    def test_log_file_written(self, logger_config, log_dir):
        job_logger = JobLogger(job_name="test_job", config=logger_config)
        with job_logger:
            pass
        job_logger.get_result(return_code=0, stdout="output", stderr="")
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text()
        assert len(content) > 0
