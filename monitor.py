"""
Hourly monitor — checks signals, emails on 'buy now', logs to Notion.

Usage:
  python monitor.py          # runs every hour (blocks)
  python monitor.py --once   # single check and exit (good for cron)

Env vars (put in .env or export before running):
  GMAIL_USER, GMAIL_APP_PASSWORD, NOTION_TOKEN
  Optional signal tuning: BUY_MIN_CHANGE_1H, BUY_MIN_LIQUIDITY,
                          BUY_MIN_VOL_LIQ_RATIO, TARGET_CHAIN
"""

import sys
import time
import logging
import schedule
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

from signals  import get_signal
from notifier import send_buy_email, log_to_notion


def check_and_notify() -> None:
    log.info("── Signal check starting ──")
    data   = get_signal()
    signal = data.get("signal", "")

    log.info("Signal: %s | token=%s | timestamp=%s",
             signal, data.get("token", "—"), data.get("timestamp", ""))

    if signal == "buy now":
        token = data.get("token", "UNKNOWN")
        log.info("BUY NOW detected for %s! Sending email and logging to Notion…", token)

        try:
            send_buy_email(data)
        except Exception as exc:
            log.error("Email failed: %s", exc)

        try:
            log_to_notion(data)
        except Exception as exc:
            log.error("Notion log failed: %s", exc)

    elif signal == "error":
        log.warning("Signal check error: %s", data.get("reason", "unknown"))
    else:
        log.info("No buy signal (%s). Nothing to do.", signal)

    log.info("── Signal check complete ──\n")


def main() -> None:
    once = "--once" in sys.argv

    if once:
        check_and_notify()
        return

    log.info("memecoin-intel monitor started — checking every 1 hour.")
    log.info("Press Ctrl+C to stop.\n")

    check_and_notify()                      # immediate first run
    schedule.every(1).hour.do(check_and_notify)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Monitor stopped.")


if __name__ == "__main__":
    main()
