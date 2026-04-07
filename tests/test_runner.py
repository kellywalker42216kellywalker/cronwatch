"""Tests for the JobRunner and JobResult classes."""

import time
import pytest
from unittest.mock import patch, MagicMock

from cronwatch.runner import JobResult, JobRunner, JobTimeoutError


# --- Fixtures ---

@pytest.fixture
def basic_config():
    """Minimal runner configuration."""
    return {
        "timeout": 30,
        "capture_output": True,
    }


@pytest.fixture
def runner(basic_config):
    """A JobRunner instance with basic config."""
    return JobRunner(config=basic_config)


# --- JobResult Tests ---

class TestJobResult:
    def test_success_result(self):
        result = JobResult(
            command="echo hello",
            exit_code=0,
            stdout="hello\n",
            stderr="",
            duration=0.1,
        )
        assert result.success is True

    def test_failure_result(self):
        result = JobResult(
            command="false",
            exit_code=1,
            stdout="",
            stderr="error",
            duration=0.05,
        )
        assert result.success is False

    def test_short_output_truncates(self):
        long_output = "x" * 600
        result = JobResult(
            command="cmd",
            exit_code=0,
            stdout=long_output,
            stderr="",
            duration=0.1,
        )
        assert len(result.short_output) <= 512

    def test_short_output_uses_stderr_on_failure(self):
        result = JobResult(
            command="cmd",
            exit_code=1,
            stdout="",
            stderr="something went wrong",
            duration=0.1,
        )
        assert "something went wrong" in result.short_output

    def test_short_output_falls_back_to_stdout(self):
        result = JobResult(
            command="cmd",
            exit_code=1,
            stdout="fallback output",
            stderr="",
            duration=0.1,
        )
        assert "fallback output" in result.short_output

    def test_timed_out_flag(self):
        result = JobResult(
            command="sleep 100",
            exit_code=-1,
            stdout="",
            stderr="",
            duration=30.0,
            timed_out=True,
        )
        assert result.timed_out is True
        assert result.success is False


# --- JobRunner Tests ---

class TestJobRunner:
    def test_run_successful_command(self, runner):
        result = runner.run("echo hello")
        assert result.success is True
        assert "hello" in result.stdout
        assert result.exit_code == 0

    def test_run_failing_command(self, runner):
        result = runner.run("exit 1", shell=True)
        assert result.success is False
        assert result.exit_code == 1

    def test_run_captures_stderr(self, runner):
        result = runner.run("echo error >&2", shell=True)
        assert "error" in result.stderr

    def test_run_records_duration(self, runner):
        result = runner.run("echo hi")
        assert result.duration >= 0.0

    def test_run_stores_command(self, runner):
        result = runner.run("echo hi")
        assert result.command == "echo hi"

    def test_timeout_raises_job_timeout_error(self):
        config = {"timeout": 1, "capture_output": True}
        runner = JobRunner(config=config)
        result = runner.run("sleep 10")
        assert result.timed_out is True
        assert result.success is False

    def test_run_with_env_override(self, runner):
        import os
        result = runner.run("echo $MY_VAR", shell=True, env={**os.environ, "MY_VAR": "cronwatch"})
        assert "cronwatch" in result.stdout

    def test_no_capture_output(self):
        config = {"timeout": 30, "capture_output": False}
        runner = JobRunner(config=config)
        # Should not raise; stdout/stderr will be empty strings
        result = runner.run("echo silent")
        assert result.exit_code == 0
