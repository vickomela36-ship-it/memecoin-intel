#!/usr/bin/env python3
"""
Persistent hourly scheduler for the memecoin signal runner.

Usage (runs in the foreground; use nohup or screen to detach):
    python3 scheduler.py

To run in the background:
    nohup python3 scheduler.py &
    echo "PID=$!" > scheduler.pid

To stop:
    kill $(cat scheduler.pid)
"""

import logging
import signal
import sys
import time
from datetime import datetime, timezone

# Ensure runner's logging setup runs first
import runner

log = logging.getLogger("scheduler")

INTERVAL_SECONDS = 3600  # 1 hour
_running = True


def _shutdown(signum, frame):
    global _running
    log.info("Received signal %d — stopping after current cycle.", signum)
    _running = False


def main():
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("Scheduler started. Running every %d seconds (%d min).",
             INTERVAL_SECONDS, INTERVAL_SECONDS // 60)

    # Run immediately on first start, then every hour
    while _running:
        try:
            runner.run()
        except Exception as exc:
            log.exception("Unexpected error in runner: %s", exc)

        if not _running:
            break

        next_run = datetime.now(timezone.utc).replace(microsecond=0)
        log.info("Next run in %d min. Sleeping…", INTERVAL_SECONDS // 60)

        # Sleep in 60-second slices so SIGTERM/SIGINT is handled promptly
        for _ in range(INTERVAL_SECONDS // 60):
            if not _running:
                break
            time.sleep(60)

    log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
