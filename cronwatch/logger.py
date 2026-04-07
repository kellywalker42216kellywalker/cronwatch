"""Logging module for cronwatch.

Provides structured logging for cron job execution, capturing stdout/stderr,
exit codes, timing information, and persisting logs to disk.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Module-level logger for cronwatch internals
_logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure the root logger for cronwatch CLI output.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger("cronwatch")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


class JobLogger:
    """Records structured execution details for a single cron job run.

    Each run is stored as a newline-delimited JSON (NDJSON) entry in a
    per-job log file under the configured log directory.
    """

    def __init__(self, job_name: str, log_dir: str) -> None:
        """
        Args:
            job_name: Identifier for the cron job (used in filenames and records).
            log_dir:  Directory where log files are written.
        """
        self.job_name = job_name
        self.log_dir = Path(log_dir)
        self._start_time: Optional[datetime] = None
        self._record: dict = {}

    # ------------------------------------------------------------------
    # Context-manager interface
    # ------------------------------------------------------------------

    def __enter__(self) -> "JobLogger":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # If an unhandled exception escaped the block, record it as a failure.
        if exc_type is not None:
            self.finish(
                exit_code=1,
                stdout="",
                stderr=f"{exc_type.__name__}: {exc_val}",
                success=False,
            )
        return False  # do not suppress exceptions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the beginning of a job run."""
        self._start_time = datetime.now(timezone.utc)
        _logger.debug("Job '%s' started at %s", self.job_name, self._start_time.isoformat())

    def finish(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        success: bool,
    ) -> dict:
        """Finalise the run record and persist it to disk.

        Args:
            exit_code: Process exit code.
            stdout:    Captured standard output.
            stderr:    Captured standard error.
            success:   Whether the job is considered successful.

        Returns:
            The completed log record as a dict.
        """
        end_time = datetime.now(timezone.utc)
        duration = (
            (end_time - self._start_time).total_seconds()
            if self._start_time
            else None
        )

        self._record = {
            "job": self.job_name,
            "started_at": self._start_time.isoformat() if self._start_time else None,
            "finished_at": end_time.isoformat(),
            "duration_seconds": duration,
            "exit_code": exit_code,
            "success": success,
            "stdout": stdout.strip() if stdout else "",
            "stderr": stderr.strip() if stderr else "",
        }

        self._write_record(self._record)
        log_fn = _logger.debug if success else _logger.warning
        log_fn(
            "Job '%s' finished — success=%s exit_code=%s duration=%.2fs",
            self.job_name,
            success,
            exit_code,
            duration or 0.0,
        )
        return self._record

    @property
    def record(self) -> dict:
        """Return the most recently written log record."""
        return self._record

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_path(self) -> Path:
        """Return the path to this job's log file, creating directories as needed."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Sanitise job name for use in a filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.job_name)
        return self.log_dir / f"{safe_name}.log"

    def _write_record(self, record: dict) -> None:
        """Append a JSON-encoded record to the job's log file."""
        path = self._log_path()
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + os.linesep)
        except OSError as exc:
            _logger.error("Failed to write log record for '%s': %s", self.job_name, exc)
