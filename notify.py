"""
Daily runner: check signals → email + Notion log on every 'buy now'.

Required env vars (set as GitHub Actions secrets):
  GMAIL_SENDER        – the Gmail address used to send
  GMAIL_APP_PASSWORD  – Gmail App Password (not your account password)
  NOTION_TOKEN        – Notion internal integration token
  WALLET_ADDRESS      – (optional) your Solana wallet address
"""

import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    COINS_TO_TRACK,
    EMAIL_FROM,
    EMAIL_TO,
    GMAIL_APP_PASSWORD,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from signals import SignalResult, run_signals


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_email(signal: SignalResult) -> None:
    if not EMAIL_FROM or not GMAIL_APP_PASSWORD:
        print("  [warn] GMAIL_SENDER / GMAIL_APP_PASSWORD not set — skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BUY NOW Signal: {signal.coin}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    plain = (
        f"BUY NOW Signal Detected!\n\n"
        f"Coin:       {signal.coin}\n"
        f"Price:      ${signal.price_usd:.8f}\n"
        f"Confidence: {signal.confidence:.0f}/100\n"
        f"Reason:     {signal.reason}\n"
        f"Timestamp:  {ts}\n"
    )
    html = f"""<html><body>
<h2 style="color:#16a34a">BUY NOW: {signal.coin}</h2>
<table cellpadding="6" style="border-collapse:collapse;font-family:sans-serif">
  <tr><td><b>Price</b></td><td>${signal.price_usd:.8f}</td></tr>
  <tr><td><b>Confidence</b></td><td>{signal.confidence:.0f} / 100</td></tr>
  <tr><td><b>Reason</b></td><td>{signal.reason}</td></tr>
  <tr><td><b>Time</b></td><td>{ts}</td></tr>
</table>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f"  Email sent → {EMAIL_TO}")


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def log_to_notion(signal: SignalResult) -> None:
    if not NOTION_TOKEN:
        print("  [warn] NOTION_TOKEN not set — skipping Notion log.")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": f"{signal.coin} – {signal.signal}"}}]
            },
            "Coin":        {"rich_text": [{"text": {"content": signal.coin}}]},
            "Signal Type": {"select":    {"name": signal.signal}},
            "Price USD":   {"number":    signal.price_usd},
            "Confidence":  {"number":    signal.confidence},
            "Reason":      {"rich_text": [{"text": {"content": signal.reason}}]},
            "Timestamp":   {"date":      {"start": now_iso}},
        },
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization":  f"Bearer {NOTION_TOKEN}",
            "Content-Type":   "application/json",
            "Notion-Version": "2022-06-28",
        },
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    print(f"  Logged to Notion: {signal.coin}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] Running daily memecoin signal check…")

    results = run_signals(COINS_TO_TRACK)

    if not results:
        print("No signal data returned — check token addresses / network.")
        sys.exit(0)

    buy_now = [s for s in results if s.signal == "buy now"]
    print(f"\n{len(results)} coins checked | {len(buy_now)} 'buy now' signal(s)\n")

    for s in results:
        marker = "<-- BUY NOW" if s.signal == "buy now" else ""
        print(
            f"  {s.coin:<10} {s.signal:<8} "
            f"confidence={s.confidence:.0f}  price=${s.price_usd:.8f}  {marker}"
        )

    print()
    for s in buy_now:
        print(f"Processing BUY NOW for {s.coin}…")
        send_email(s)
        log_to_notion(s)

    print("\nDone.")


if __name__ == "__main__":
    main()
