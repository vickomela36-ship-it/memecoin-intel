"""
Daily runner — checks all tracked coins for signals, sends email alerts,
and logs every 'buy now' signal to Notion.

Run directly:
    python run_daily.py

Or via GitHub Actions (see .github/workflows/daily_signal_check.yml).
"""

import sys
import datetime

from signals import run_signals
from notifier import send_email_alert, log_signal_to_notion


def main() -> int:
    print(f"[run_daily] Starting signal check — {datetime.datetime.utcnow().isoformat()} UTC")

    try:
        all_signals = run_signals()
    except Exception as exc:
        print(f"[run_daily] ERROR fetching signals: {exc}")
        return 1

    print(f"[run_daily] Checked {len(all_signals)} coins:")
    for s in all_signals:
        print(f"  {s.name:20s} score={s.score:3d}  signal={s.signal}")

    buy_signals = [s for s in all_signals if s.signal == "buy now"]

    if not buy_signals:
        print("[run_daily] No 'buy now' signals today — no email or Notion log.")
        return 0

    print(f"[run_daily] {len(buy_signals)} 'buy now' signal(s) found!")

    # Send a single consolidated email for all buy signals
    email_ok = send_email_alert(buy_signals)

    # Log each buy-now coin as a separate Notion row
    for sig in buy_signals:
        log_signal_to_notion(sig, email_sent=email_ok)

    return 0


if __name__ == "__main__":
    sys.exit(main())
