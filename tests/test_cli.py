"""Tests for the cronwatch CLI module."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from cronwatch.cli import parse_args, run_job, main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """Return a minimal mock Config object."""
    cfg = MagicMock()
    cfg.job_name = "test-job"
    cfg.command = "echo hello"
    cfg.timeout = 60
    cfg.log_dir = "/tmp/cronwatch-test-logs"
    cfg.log_level = "INFO"
    cfg.notifiers = []
    cfg.success_notify = False
    cfg.failure_notify = True
    cfg.env = {}
    return cfg


@pytest.fixture
def mock_job_result_success():
    """Return a mock successful job result dict."""
    return {
        "job_name": "test-job",
        "command": "echo hello",
        "exit_code": 0,
        "success": True,
        "stdout": "hello\n",
        "stderr": "",
        "duration": 0.05,
        "start_time": "2024-01-01T00:00:00",
        "end_time": "2024-01-01T00:00:01",
    }


@pytest.fixture
def mock_job_result_failure():
    """Return a mock failed job result dict."""
    return {
        "job_name": "test-job",
        "command": "exit 1",
        "exit_code": 1,
        "success": False,
        "stdout": "",
        "stderr": "error message\n",
        "duration": 0.02,
        "start_time": "2024-01-01T00:00:00",
        "end_time": "2024-01-01T00:00:01",
    }


# ---------------------------------------------------------------------------
# parse_args tests
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_required_command_argument(self):
        args = parse_args(["--job", "backup", "--", "rsync", "-av", "/src", "/dst"])
        assert args.command == ["rsync", "-av", "/src", "/dst"]

    def test_job_name(self):
        args = parse_args(["--job", "my-job", "--", "echo", "hi"])
        assert args.job == "my-job"

    def test_config_flag(self, tmp_path):
        cfg_file = tmp_path / "cronwatch.yml"
        cfg_file.write_text("job_name: test\n")
        args = parse_args(["--config", str(cfg_file), "--", "echo", "hi"])
        assert args.config == str(cfg_file)

    def test_defaults(self):
        args = parse_args(["--", "echo", "hi"])
        assert args.job is None
        assert args.config is None
        assert args.verbose is False

    def test_verbose_flag(self):
        args = parse_args(["--verbose", "--", "echo", "hi"])
        assert args.verbose is True

    def test_missing_command_raises(self):
        with pytest.raises(SystemExit):
            parse_args([])


# ---------------------------------------------------------------------------
# run_job tests
# ---------------------------------------------------------------------------

class TestRunJob:
    def test_successful_command(self, mock_config):
        mock_config.command = "echo hello"
        result = run_job(mock_config)
        assert result["exit_code"] == 0
        assert result["success"] is True
        assert "hello" in result["stdout"]

    def test_failing_command(self, mock_config):
        mock_config.command = "bash -c 'exit 42'"
        result = run_job(mock_config)
        assert result["exit_code"] == 42
        assert result["success"] is False

    def test_result_contains_timing_info(self, mock_config):
        mock_config.command = "echo hi"
        result = run_job(mock_config)
        assert "duration" in result
        assert "start_time" in result
        assert "end_time" in result
        assert result["duration"] >= 0

    def test_timeout_kills_process(self, mock_config):
        mock_config.command = "sleep 10"
        mock_config.timeout = 1
        result = run_job(mock_config)
        assert result["success"] is False
        assert result["timed_out"] is True

    def test_stderr_captured(self, mock_config):
        mock_config.command = "bash -c 'echo err >&2; exit 1'"
        result = run_job(mock_config)
        assert "err" in result["stderr"]


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------

class TestMain:
    @patch("cronwatch.cli.Config")
    @patch("cronwatch.cli.setup_logging")
    @patch("cronwatch.cli.JobLogger")
    @patch("cronwatch.cli.run_job")
    def test_main_success_exits_zero(
        self, mock_run, mock_job_logger, mock_setup_logging, mock_config_cls, mock_config, mock_job_result_success
    ):
        mock_config_cls.return_value = mock_config
        mock_run.return_value = mock_job_result_success
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_job_logger.return_value = ctx

        with patch("sys.argv", ["cronwatch", "--job", "test-job", "--", "echo", "hello"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    @patch("cronwatch.cli.Config")
    @patch("cronwatch.cli.setup_logging")
    @patch("cronwatch.cli.JobLogger")
    @patch("cronwatch.cli.run_job")
    def test_main_failure_exits_nonzero(
        self, mock_run, mock_job_logger, mock_setup_logging, mock_config_cls, mock_config, mock_job_result_failure
    ):
        mock_config_cls.return_value = mock_config
        mock_run.return_value = mock_job_result_failure
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_job_logger.return_value = ctx

        with patch("sys.argv", ["cronwatch", "--job", "test-job", "--", "bash", "-c", "exit 1"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code != 0
