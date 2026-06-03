#!/usr/bin/env python3
"""Daily entry point: scan for buy signals, email alerts, log to Notion."""

import sys
from signals import run_scan
from notifier import send_email, log_to_notion


def main() -> int:
    print("Scanning trending Solana tokens for buy-now signals...")
    signals = run_scan()

    if not signals:
        print("No buy-now signals today.")
        return 0

    print(f"\nFound {len(signals)} buy-now signal(s):")
    for s in signals:
        print(f"  {s.token:10} {s.chain:8} +{s.price_change_24h:6.1f}%"
              f"  vol=${s.volume_24h:>12,.0f}  [{s.signal_strength}]")

    # Attempt email first so we know the sent status for Notion
    email_ok = False
    try:
        send_email(signals)
        email_ok = True
    except Exception as exc:
        print(f"[error] Email failed: {exc}", file=sys.stderr)

    # Log every signal to Notion regardless of email outcome
    notion_errors = 0
    for sig in signals:
        try:
            log_to_notion(sig, email_sent=email_ok)
        except Exception as exc:
            print(f"[error] Notion log failed for {sig.token}: {exc}", file=sys.stderr)
            notion_errors += 1

    if not email_ok:
        return 1
    if notion_errors:
        print(f"[warn] {notion_errors} Notion log(s) failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
