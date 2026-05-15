"""
Daily runner: fetches memecoin signals, emails buy-now alerts,
and logs every buy-now signal to the Notion database.
"""

import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    ALERT_EMAIL,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from signals import get_buy_now_signals


# ── Email ──────────────────────────────────────────────────────────────────────

def _build_email_html(signals: list) -> str:
    rows = ""
    for s in signals:
        rows += (
            f"<tr>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{s['coin']} ({s['symbol']})</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>${s['price_usd']:,.8g}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;color:{'#16a34a' if s['price_change_24h']>=0 else '#dc2626'};'>"
            f"{s['price_change_24h']:+.1f}%</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{s['confidence']:.0f}%</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{s['reason']}</td>"
            f"</tr>"
        )
    date_str = datetime.now().strftime("%B %d, %Y")
    return f"""
<html><body style="font-family:sans-serif;max-width:800px;margin:auto;">
  <h2 style="color:#16a34a;">🚀 Memecoin Buy Now Signals — {date_str}</h2>
  <p>{len(signals)} signal(s) detected today:</p>
  <table style="border-collapse:collapse;width:100%;">
    <thead>
      <tr style="background:#f3f4f6;">
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Coin</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Price (USD)</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">24h Change</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Confidence</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Reason</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#6b7280;font-size:12px;margin-top:24px;">
    Memecoin Intel — automated daily signal alert.
    This is not financial advice.
  </p>
</body></html>
"""


def send_email(signals: list) -> None:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️  Email credentials missing (GMAIL_ADDRESS / GMAIL_APP_PASSWORD). Skipping.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[Memecoin Intel] {len(signals)} Buy Now Signal(s) — {date_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(_build_email_html(signals), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_ADDRESS, ALERT_EMAIL, msg.as_string())

    print(f"✉️  Email sent to {ALERT_EMAIL}")


# ── Notion ─────────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict) -> None:
    if not NOTION_TOKEN:
        print("⚠️  NOTION_TOKEN missing. Skipping Notion log.")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    title = f"{signal['coin']} ({signal['symbol']}) — Buy Now"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": title}}]
            },
            "Signal Type": {"select": {"name": "buy now"}},
            "Coin": {"rich_text": [{"text": {"content": signal["coin"]}}]},
            "Price USD": {"number": signal["price_usd"]},
            "Confidence": {"number": signal["confidence"]},
            "Reason": {"rich_text": [{"text": {"content": signal["reason"]}}]},
            "Timestamp": {"date": {"start": now}},
        },
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    print(f"📋 Logged to Notion: {title}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Memecoin Intel daily run — {run_time} ===")

    buy_signals = get_buy_now_signals()

    if not buy_signals:
        print("No 'buy now' signals today. Nothing to send or log.")
        return

    print(f"\nFound {len(buy_signals)} buy now signal(s):")
    for s in buy_signals:
        print(
            f"  • {s['coin']} ({s['symbol']}): "
            f"${s['price_usd']:,.8g}  {s['price_change_24h']:+.1f}%  "
            f"confidence={s['confidence']}%"
        )

    print()

    for signal in buy_signals:
        try:
            log_to_notion(signal)
        except Exception as e:
            print(f"  ✗ Notion log failed for {signal['coin']}: {e}")

    try:
        send_email(buy_signals)
    except Exception as e:
        print(f"  ✗ Email failed: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
