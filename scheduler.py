"""
Hourly scheduler — runs signal checks every 60 minutes.
On start it fires one immediate check, then repeats on the hour.

Usage:
    python scheduler.py

Logs are written to both stdout and memecoin_intel.log.
"""

import logging
import time

import schedule

from notifier import log_to_notion, send_email
from signals import check_all_tokens

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("memecoin_intel.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def run_check() -> None:
    log.info("=== Hourly signal check started ===")
    try:
        results = check_all_tokens()
    except Exception as exc:
        log.error(f"check_all_tokens() failed: {exc}")
        return

    log.info(f"Checked {len(results)} token(s)")

    for sig in results:
        log.info(f"  {sig.symbol}: {sig.signal} — {sig.reason}")

        if sig.signal != "buy now":
            continue

        log.info(f"  *** BUY NOW detected for {sig.token} ({sig.symbol}) ***")

        try:
            send_email(sig)
        except Exception as exc:
            log.error(f"  Email failed for {sig.symbol}: {exc}")

        try:
            log_to_notion(sig)
        except Exception as exc:
            log.error(f"  Notion log failed for {sig.symbol}: {exc}")

    log.info("=== Check complete ===")


if __name__ == "__main__":
    log.info("Memecoin Intel Scheduler starting up…")
    run_check()                            # immediate run on launch
    schedule.every(1).hour.do(run_check)  # then every hour

    while True:
        schedule.run_pending()
        time.sleep(30)
