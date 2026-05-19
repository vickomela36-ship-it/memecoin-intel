"""Daily runner: check signals → email → Notion log."""
import sys
from datetime import datetime, timezone

from notifier import build_email_content, log_to_notion, send_email
from signals import get_signals


def run():
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] Starting daily signal check...")

    try:
        signals = get_signals()
    except Exception as exc:
        print(f"ERROR fetching signals: {exc}", file=sys.stderr)
        sys.exit(1)

    buy_now = [s for s in signals if s["signal"] == "buy now"]
    print(f"  Scanned {len(signals)} token(s) | {len(buy_now)} BUY NOW signal(s)")

    if not buy_now:
        print("  No BUY NOW signals today — nothing to do.")
        return

    # Log each signal to Notion
    notion_ok = 0
    for s in buy_now:
        try:
            log_to_notion(s)
            print(f"  Notion logged: {s['coin']} ✓")
            notion_ok += 1
        except Exception as exc:
            print(f"  ERROR logging {s['coin']} to Notion: {exc}", file=sys.stderr)

    # Send one consolidated email alert
    subject, body_html, body_text = build_email_content(buy_now)
    try:
        send_email(subject, body_html, body_text)
        print(f"  Email sent ✓  ({len(buy_now)} signal(s))")
    except Exception as exc:
        print(f"  ERROR sending email: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  Done. Notion: {notion_ok}/{len(buy_now)} logged.")


if __name__ == "__main__":
    run()
