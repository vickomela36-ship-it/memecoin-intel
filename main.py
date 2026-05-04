#!/usr/bin/env python3
"""
Standalone runner — scans tokens, sends email, and logs to Notion for every
'buy now' signal found.  Run directly or via cron (see run_hourly.sh).
"""
import json
import sys
from signals import scan_all_tokens
from notifier import send_email, log_to_notion


def main() -> int:
    print("Scanning tokens for buy signals…")
    signals = scan_all_tokens()

    if not signals:
        print("No buy signals found.")
        print(json.dumps({"signals": [], "count": 0}))
        return 0

    print(f"Found {len(signals)} buy signal(s)!")
    for sig in signals:
        print(f"\n  BUY NOW: {sig['token']} @ ${sig['price_usd']:.8f}  score={sig['score']}/100")
        print(f"  {sig['reason']}")
        email_sent = send_email(sig)
        log_to_notion(sig, email_sent=email_sent)

    # JSON summary to stdout — useful when consumed by scripts / Claude loop
    print(json.dumps({"signals": signals, "count": len(signals)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
