#!/usr/bin/env python3
"""
One-shot signal check: fetch signals, email + Notion-log every 'buy now'.

Run directly:  python check_signals.py
Scheduled:     python scheduler.py        (runs this every hour)
"""
import logging

from config import GMAIL_SENDER, NOTION_TOKEN
from notifier import log_to_notion, send_email
from signals import get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_check() -> int:
    """Run one signal check cycle. Returns count of buy-now signals found."""
    log.info("Running memecoin signal check …")
    all_signals = get_signals()
    buy_now = [s for s in all_signals if s.get("signal") == "buy now"]

    if not buy_now:
        log.info("No buy now signals this round.")
        return 0

    log.info("Found %d buy now signal(s).", len(buy_now))

    for sig in buy_now:
        token = sig.get("token", "UNKNOWN")

        if GMAIL_SENDER:
            try:
                send_email(sig)
                log.info("  ✉  Email sent for %s.", token)
            except Exception as exc:
                log.error("  ✉  Email failed for %s: %s", token, exc)
        else:
            log.warning("  ✉  GMAIL_SENDER not set — skipping email for %s.", token)

        if NOTION_TOKEN:
            try:
                log_to_notion(sig)
                log.info("  📒 Notion row created for %s.", token)
            except Exception as exc:
                log.error("  📒 Notion log failed for %s: %s", token, exc)
        else:
            log.warning("  📒 NOTION_TOKEN not set — skipping Notion log for %s.", token)

    return len(buy_now)


if __name__ == "__main__":
    run_check()
