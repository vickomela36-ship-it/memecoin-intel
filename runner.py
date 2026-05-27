import sys
from signals import generate_signals, MEMECOIN_IDS
from notifier import send_buy_signal_email
from notion_logger import log_buy_signal

ALERT_EMAIL = "vickomela36@gmail.com"


def main():
    print("Fetching memecoin data and generating signals...")
    coins = generate_signals(MEMECOIN_IDS)

    buy_signals = [c for c in coins if c.signal == "buy now"]

    print(f"Checked {len(coins)} coins — {len(buy_signals)} buy signal(s) found")
    for c in coins:
        print(f"  {c.symbol:<12} signal={c.signal:<8} "
              f"price=${c.price_usd:.6g}  24h={c.change_24h:+.2f}%")

    if not buy_signals:
        print("No buy signals today. Exiting.")
        return

    email_sent = False
    try:
        send_buy_signal_email(buy_signals, ALERT_EMAIL)
        email_sent = True
    except Exception as exc:
        print(f"Warning: email failed — {exc}", file=sys.stderr)

    for coin in buy_signals:
        try:
            log_buy_signal(coin, email_sent=email_sent)
        except Exception as exc:
            print(f"Warning: Notion log failed for {coin.name} — {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
