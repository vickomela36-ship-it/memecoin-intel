"""
Daily runner: fetch signals, notify on 'buy now', log to Notion.
Intended to be executed by GitHub Actions on a daily schedule.
"""

import sys
from signals import get_signals
from notifier import send_email, log_to_notion


def main() -> int:
    print("Fetching signals...")
    try:
        all_signals = get_signals()
    except Exception as exc:
        print(f"[error] Failed to fetch signals: {exc}", file=sys.stderr)
        return 1

    buy_signals = [s for s in all_signals if s["signal"] == "buy now"]

    print(f"Evaluated {len(all_signals)} token(s). Buy signals: {len(buy_signals)}")
    for s in all_signals:
        print(f"  {s['token']:<8} {s['signal']:<10}  ${s['price']:.6f}  {s['price_change_24h']:+.1f}%")

    if not buy_signals:
        print("No 'buy now' signals today — no email or Notion log needed.")
        return 0

    # Log each buy signal to Notion first (independent of email success)
    notion_errors = 0
    for s in buy_signals:
        try:
            log_to_notion(s)
        except Exception as exc:
            print(f"[error] Notion log failed for {s['token']}: {exc}", file=sys.stderr)
            notion_errors += 1

    # Send one combined email for all buy signals
    try:
        send_email(buy_signals)
    except Exception as exc:
        print(f"[error] Email send failed: {exc}", file=sys.stderr)
        return 1

    return 1 if notion_errors else 0


if __name__ == "__main__":
    sys.exit(main())
