"""Job runner module for cronwatch.

Handles subprocess execution of cron jobs, capturing stdout/stderr,
tracking exit codes, and measuring execution time.
"""

import subprocess
import time
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JobResult:
    """Encapsulates the result of a cron job execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Return True if the job completed successfully (exit code 0)."""
        return self.exit_code == 0 and not self.timed_out

    @property
    def short_output(self) -> str:
        """Return a truncated combined output string for notifications."""
        combined = ""
        if self.stdout.strip():
            combined += f"STDOUT:\n{self.stdout.strip()}"
        if self.stderr.strip():
            if combined:
                combined += "\n"
            combined += f"STDERR:\n{self.stderr.strip()}"
        max_len = 1500
        if len(combined) > max_len:
            return combined[:max_len] + "\n... (truncated)"
        return combined


class JobTimeoutError(Exception):
    """Raised when a job exceeds its configured timeout."""


class JobRunner:
    """Executes shell commands and returns structured JobResult objects."""

    def __init__(self, timeout: Optional[int] = None, shell: bool = False):
        """
        Initialize the JobRunner.

        Args:
            timeout: Maximum seconds to allow the job to run. None means no limit.
            shell: If True, run the command through the shell. Defaults to False
                   for security; use True only when the command requires shell features.
        """
        self.timeout = timeout
        self.shell = shell

    def run(self, command: str) -> JobResult:
        """
        Execute a command and return a JobResult.

        Args:
            command: The shell command string to execute.

        Returns:
            A JobResult instance with captured output and metadata.
        """
        started_at = datetime.now(timezone.utc)
        start_time = time.monotonic()
        timed_out = False
        error_message: Optional[str] = None
        exit_code = -1
        stdout = ""
        stderr = ""

        # Split command into args list when not using shell mode
        cmd = command if self.shell else shlex.split(command)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=self.shell,
            )
            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            error_message = f"Job timed out after {self.timeout} seconds."

        except FileNotFoundError as exc:
            exit_code = 127  # Conventional "command not found" exit code
            error_message = f"Command not found: {exc}"

        except OSError as exc:
            exit_code = -1
            error_message = f"OS error while running job: {exc}"

        finally:
            finished_at = datetime.now(timezone.utc)
            duration = time.monotonic() - start_time

        return JobResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(duration, 3),
            timed_out=timed_out,
            error=error_message,
        )
