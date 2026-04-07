"""State management for cronwatch.

Tracks job execution history to support alerting logic such as
'only alert after N consecutive failures' or 'alert on recovery'.
State is persisted to a simple JSON file on disk.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = os.path.expanduser("~/.cronwatch/state")


@dataclass
class JobState:
    """Persisted state for a single job."""

    job_name: str
    last_run_at: Optional[float] = None        # Unix timestamp
    last_exit_code: Optional[int] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_alerted_at: Optional[float] = None    # Unix timestamp of last alert sent
    history: List[Dict] = field(default_factory=list)  # Recent run summaries

    # Maximum number of history entries to keep
    MAX_HISTORY: int = field(default=50, repr=False, compare=False)

    def record_run(self, exit_code: int, duration: float, timed_out: bool = False) -> None:
        """Update state after a job run."""
        self.last_run_at = time.time()
        self.last_exit_code = exit_code
        success = exit_code == 0 and not timed_out

        if success:
            self.consecutive_failures = 0
            self.consecutive_successes += 1
        else:
            self.consecutive_successes = 0
            self.consecutive_failures += 1

        self.history.append({
            "timestamp": self.last_run_at,
            "exit_code": exit_code,
            "duration": round(duration, 3),
            "timed_out": timed_out,
            "success": success,
        })

        # Trim history to avoid unbounded growth
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    def mark_alerted(self) -> None:
        """Record that an alert was dispatched right now."""
        self.last_alerted_at = time.time()

    @property
    def is_failing(self) -> bool:
        """True if the most recent run was a failure."""
        return self.consecutive_failures > 0

    @property
    def just_recovered(self) -> bool:
        """True if the job succeeded after at least one previous failure."""
        return self.consecutive_successes == 1 and (
            len(self.history) >= 2 and not self.history[-2]["success"]
        )


class StateStore:
    """Loads and persists job state to a JSON file."""

    def __init__(self, state_dir: Optional[str] = None) -> None:
        self.state_dir = Path(state_dir or DEFAULT_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("StateStore initialised at %s", self.state_dir)

    def _state_path(self, job_name: str) -> Path:
        """Return the path to the state file for a given job."""
        # Sanitise job name so it is safe to use as a filename
        safe_name = job_name.replace("/", "_").replace(" ", "_")
        return self.state_dir / f"{safe_name}.json"

    def load(self, job_name: str) -> JobState:
        """Load persisted state for *job_name*, or return a fresh JobState."""
        path = self._state_path(job_name)
        if not path.exists():
            logger.debug("No existing state for job '%s', starting fresh", job_name)
            return JobState(job_name=job_name)

        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            state = JobState(
                job_name=data.get("job_name", job_name),
                last_run_at=data.get("last_run_at"),
                last_exit_code=data.get("last_exit_code"),
                consecutive_failures=data.get("consecutive_failures", 0),
                consecutive_successes=data.get("consecutive_successes", 0),
                last_alerted_at=data.get("last_alerted_at"),
                history=data.get("history", []),
            )
            logger.debug(
                "Loaded state for job '%s': %d consecutive failures",
                job_name,
                state.consecutive_failures,
            )
            return state
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(
                "Corrupt state file for job '%s' (%s) — resetting state", job_name, exc
            )
            return JobState(job_name=job_name)

    def save(self, state: JobState) -> None:
        """Persist *state* to disk."""
        path = self._state_path(state.job_name)
        data = {
            "job_name": state.job_name,
            "last_run_at": state.last_run_at,
            "last_exit_code": state.last_exit_code,
            "consecutive_failures": state.consecutive_failures,
            "consecutive_successes": state.consecutive_successes,
            "last_alerted_at": state.last_alerted_at,
            "history": state.history,
        }
        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            logger.debug("Saved state for job '%s' to %s", state.job_name, path)
        except OSError as exc:
            logger.error("Failed to save state for job '%s': %s", state.job_name, exc)
