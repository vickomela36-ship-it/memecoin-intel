from datetime import date
from signals import run_signal_scan
from notifier import send_email, log_to_notion
from config import TRACKED_TOKENS


def main() -> None:
    print(f"=== Memecoin Intel — Daily Run: {date.today().isoformat()} ===\n")

    if not TRACKED_TOKENS:
        print("[WARN] No tokens configured in config.py TRACKED_TOKENS. Nothing to scan.")
        return

    all_results = run_signal_scan()
    buy_now = [r for r in all_results if r["signal"] == "buy now"]

    print(f"\nScan complete: {len(all_results)} token(s) checked, {len(buy_now)} BUY NOW signal(s).\n")

    if buy_now:
        for signal in buy_now:
            log_to_notion(signal)
        send_email(buy_now)
    else:
        print("No BUY NOW signals today — no email sent.")


if __name__ == "__main__":
    main()
