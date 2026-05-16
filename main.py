"""Entry point: scan signals, email on Buy Now, log every hit to Notion."""

import sys
from dotenv import load_dotenv

load_dotenv()  # no-op in CI where secrets come from env; loads .env locally

from signals import scan_signals
from notify import log_to_notion, send_email


def main() -> int:
    print("[main] Scanning trending tokens via DexScreener…")
    all_signals = scan_signals()
    print(f"[main] Evaluated {len(all_signals)} token(s)")

    buy_signals = [s for s in all_signals if s.signal == "Buy Now"]
    print(f"[main] Buy Now signals: {len(buy_signals)}")

    if not buy_signals:
        print("[main] No Buy Now signals today — nothing to send or log.")
        return 0

    for s in buy_signals:
        print(f"  • {s.signal_name} ({s.chain}) — {s.notes}")

    log_to_notion(buy_signals)
    send_email(buy_signals)

    print("[main] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
