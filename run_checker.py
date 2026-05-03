#!/usr/bin/env python3
"""
Hourly memecoin signal checker.

Invoked by cron (see install_cron.sh):
  0 * * * * cd /path/to/memecoin-intel && python run_checker.py >> /tmp/memecoin-checker.log 2>&1

Workflow:
  1. Fetch top trending Solana tokens from DexScreener.
  2. For every token that scores 'buy now', send an email alert.
  3. Log every 'buy now' hit to the Notion database (with email-sent status).
"""

from datetime import datetime, timezone

from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    MAX_TOKENS_TO_CHECK,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from notifier import log_to_notion, send_email
from signals import get_buy_signals


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'=' * 50}")
    print(f"[checker] Run started at {now}")
    print(f"{'=' * 50}")

    buy_signals = get_buy_signals(limit=MAX_TOKENS_TO_CHECK)

    if not buy_signals:
        print("[checker] No 'buy now' signals this run.")
        return

    tokens = [s["token"] for s in buy_signals]
    print(f"[checker] {len(buy_signals)} buy signal(s): {tokens}")

    for signal in buy_signals:
        email_ok = send_email(signal, GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL)
        log_to_notion(signal, NOTION_TOKEN, NOTION_DATABASE_ID, email_sent=email_ok)

    print(f"[checker] Done — {len(buy_signals)} signal(s) processed.")


if __name__ == "__main__":
    main()
