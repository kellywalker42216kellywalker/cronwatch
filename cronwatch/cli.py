#!/usr/bin/env python3
"""cronwatch CLI entry point.

Provides the main command-line interface for monitoring, logging,
and alerting on cron job failures.
"""

import argparse
import sys
import subprocess
import time
from datetime import datetime

from cronwatch.logger import get_logger
from cronwatch.config import load_config
from cronwatch.notifier import notify_failure, notify_success

logger = get_logger(__name__)


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="cronwatch",
        description="Monitor, log, and alert on cron job failures.",
    )

    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="The command (cron job) to execute and monitor.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="FILE",
        help="Path to a cronwatch config file (default: ~/.cronwatch.yml).",
    )
    parser.add_argument(
        "--job-name",
        default=None,
        metavar="NAME",
        help="Human-readable name for this job (used in alerts).",
    )
    parser.add_argument(
        "--notify-on-success",
        action="store_true",
        default=False,
        help="Send a notification even when the job succeeds.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help="Kill the job and treat as failure if it exceeds this duration.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="cronwatch 0.1.0",
    )

    return parser.parse_args(argv)


def run_job(command, timeout=None):
    """Execute the given command and return (returncode, stdout, stderr, duration)."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start
        return result.returncode, result.stdout, result.stderr, duration
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        logger.error("Job timed out after %s seconds.", timeout)
        return -1, stdout, stderr + f"\n[cronwatch] Timed out after {timeout}s.", duration
    except FileNotFoundError:
        duration = time.monotonic() - start
        logger.error("Command not found: %s", command[0] if command else "<empty>")
        return 127, "", f"Command not found: {command[0] if command else ''}", duration


def main(argv=None):
    """Main entry point for the cronwatch CLI."""
    args = parse_args(argv)

    if not args.command:
        print("cronwatch: error: no command specified.", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    job_name = args.job_name or " ".join(args.command)
    timeout = args.timeout or config.get("timeout")

    logger.info("Starting job: %s", job_name)
    started_at = datetime.utcnow().isoformat()

    returncode, stdout, stderr, duration = run_job(args.command, timeout=timeout)

    log_entry = {
        "job": job_name,
        "started_at": started_at,
        "duration_seconds": round(duration, 3),
        "returncode": returncode,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }

    if returncode != 0:
        logger.error(
            "Job FAILED [rc=%d, %.2fs]: %s", returncode, duration, job_name
        )
        if stderr:
            logger.error("stderr: %s", stderr.strip())
        notify_failure(job_name, log_entry, config)
    else:
        logger.info("Job succeeded [%.2fs]: %s", duration, job_name)
        if args.notify_on_success or config.get("notify_on_success"):
            notify_success(job_name, log_entry, config)

    sys.exit(0 if returncode == 0 else 1)


if __name__ == "__main__":
    main()
