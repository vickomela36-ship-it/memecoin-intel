import os
import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import NOTION_DATABASE_ID, EMAIL_RECIPIENT

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(buy_signals: list[dict]) -> None:
    sender = os.environ.get("GMAIL_SENDER", "")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not sender or not app_password:
        print("GMAIL_SENDER / GMAIL_APP_PASSWORD not set — skipping email")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[Memecoin Intel] {len(buy_signals)} BUY NOW signal(s) — {timestamp}"

    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd">{s['name']} ({s['token']})</td>
          <td style="padding:8px;border:1px solid #ddd">${s['price']:.6f}</td>
          <td style="padding:8px;border:1px solid #ddd;color:{'#2e7d32' if s['change_24h'] > 0 else '#c62828'}">{s['change_24h']:+.2f}%</td>
          <td style="padding:8px;border:1px solid #ddd">${s['volume_24h']:,.0f}</td>
          <td style="padding:8px;border:1px solid #ddd">${s['market_cap']:,.0f}</td>
        </tr>"""
        for s in buy_signals
    )

    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#222">
    <h2 style="color:#2e7d32">Memecoin Intel — BUY NOW Alert</h2>
    <p>The following memecoins triggered a <strong>BUY NOW</strong> signal on <strong>{timestamp}</strong>:</p>
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <thead>
        <tr style="background:#f5f5f5;font-weight:bold">
          <th style="padding:8px;border:1px solid #ddd">Token</th>
          <th style="padding:8px;border:1px solid #ddd">Price</th>
          <th style="padding:8px;border:1px solid #ddd">24h Change</th>
          <th style="padding:8px;border:1px solid #ddd">24h Volume</th>
          <th style="padding:8px;border:1px solid #ddd">Market Cap</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="margin-top:20px;color:#666;font-size:12px">
      Automated alert from memecoin-intel. Not financial advice.
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(sender, app_password)
        srv.sendmail(sender, EMAIL_RECIPIENT, msg.as_string())
    print(f"Email sent to {EMAIL_RECIPIENT}")


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict) -> None:
    notion_token = os.environ.get("NOTION_TOKEN", "")
    if not notion_token:
        print("NOTION_TOKEN not set — skipping Notion log")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry_title = f"{signal['token']} — {today}"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal Entry": {"title": [{"text": {"content": entry_title}}]},
            "Date": {"date": {"start": today}},
            "Token": {"rich_text": [{"text": {"content": signal["token"]}}]},
            "Signal": {"select": {"name": signal["signal"]}},
            "Price USD": {"number": signal["price"]},
            "24h Change %": {"number": round(signal["change_24h"], 4)},
            "24h Volume USD": {"number": signal["volume_24h"]},
            "Market Cap USD": {"number": signal["market_cap"]},
            "Notes": {"rich_text": [{"text": {"content": signal.get("name", "")}}]},
        },
    }

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    resp = requests.post(NOTION_API_URL, json=payload, headers=headers, timeout=15)
    if resp.ok:
        print(f"Notion: logged {signal['token']}")
    else:
        print(f"Notion error for {signal['token']}: {resp.status_code} — {resp.text}")
