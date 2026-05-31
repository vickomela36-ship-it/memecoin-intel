import sys
from signals import get_signals
from notifier import send_email, log_to_notion
from config import TRACKED_COINS


def main() -> None:
    print("memecoin-intel: fetching market data...")
    try:
        all_signals = get_signals(TRACKED_COINS)
    except Exception as exc:
        print(f"Error fetching signals: {exc}", file=sys.stderr)
        sys.exit(1)

    buy_now = [s for s in all_signals if s["signal"] == "Buy Now"]

    print(f"\nResults ({len(all_signals)} coins evaluated):")
    for s in all_signals:
        tag = "*** BUY NOW ***" if s["signal"] == "Buy Now" else s["signal"].ljust(7)
        print(f"  {s['name']:<22} {s['change_24h']:+6.1f}% 24h   {tag}")

    print()
    if buy_now:
        print(f"{len(buy_now)} Buy Now signal(s) found — sending email and logging to Notion...")
        send_email(buy_now)
        log_to_notion(buy_now)
    else:
        print("No Buy Now signals today.")


if __name__ == "__main__":
    main()
