"""
Persistent daily daemon. Runs the memecoin signal check every day at 08:00 UTC.
Start with: python3 daemon.py
Or install as a systemd service: bash setup_service.sh
"""
import time
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

RUN_HOUR_UTC = 8


def _seconds_until_next_run() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    log.info("Daemon started. Signal check fires daily at %02d:00 UTC.", RUN_HOUR_UTC)
    while True:
        wait = _seconds_until_next_run()
        log.info("Next check in %.1f hours (at %02d:00 UTC).", wait / 3600, RUN_HOUR_UTC)
        time.sleep(wait)

        log.info("=== Daily signal check starting ===")
        try:
            from daily_runner import run
            run()
        except Exception as exc:
            log.error("Signal check failed: %s", exc)
        log.info("=== Daily signal check complete ===")


if __name__ == "__main__":
    main()
