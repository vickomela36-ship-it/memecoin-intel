"""
Daily memecoin signal check orchestrator.

Usage:
    python run_signal_check.py

Env vars: see config.py / .env.example
"""

import sys
from dotenv import load_dotenv

load_dotenv()  # load .env for local runs; GitHub Actions uses repository secrets

import config
from signals import get_signals
from notifier import send_buy_now_alert
from notion_logger import log_signals


def main() -> int:
    missing = config.validate()
    if missing:
        print(f"[run] Missing required env vars: {', '.join(missing)}")
        return 1

    print("[run] Fetching signals from DexScreener …")
    all_signals = get_signals()

    if not all_signals:
        print("[run] No pairs returned from DexScreener. Exiting.")
        return 0

    buy_signals = [s for s in all_signals if s["signal"] == "buy now"]
    print(f"[run] Scanned {len(all_signals)} pairs — {len(buy_signals)} buy now signal(s)")

    if not buy_signals:
        print("[run] No buy now signals today. Nothing to send or log.")
        return 0

    # Send email alert
    email_ok = send_buy_now_alert(buy_signals)

    # Log every buy-now signal to Notion
    logged = log_signals(buy_signals, email_sent=email_ok)
    print(f"[run] Logged {logged}/{len(buy_signals)} signal(s) to Notion")

    return 0


if __name__ == "__main__":
    sys.exit(main())
