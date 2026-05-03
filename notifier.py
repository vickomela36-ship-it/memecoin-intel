"""
Handles alerting for 'buy now' signals:
  - send_email()    → Gmail SMTP (App Password)
  - log_to_notion() → Notion database via notion-client
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

from notion_client import Client


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(signal: dict, gmail_user: str, gmail_password: str, to_email: str) -> bool:
    """Send a buy-now alert to *to_email* via Gmail SMTP SSL. Returns True on success."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[Memecoin Intel] BUY NOW: {signal['token']}"
    body = (
        f"Memecoin Buy Signal Detected\n"
        f"{'─' * 40}\n"
        f"Token      : {signal['token']}\n"
        f"Signal     : {signal['signal'].upper()}\n"
        f"Price      : ${signal['price_usd']:,.8f}\n"
        f"Market Cap : ${signal['market_cap']:>15,.0f}\n"
        f"Volume 24h : ${signal['volume_24h']:>15,.0f}\n"
        f"Change 24h : {signal['change_24h']:+.2f}%\n"
        f"Notes      : {signal['notes']}\n"
        f"Time       : {now}\n"
        f"\n"
        f"Automated alert — memecoin-intel\n"
    )

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
        print(f"[notifier] ✓ email sent  → {to_email}  ({signal['token']})")
        return True
    except Exception as e:
        print(f"[notifier] ✗ email error: {e}")
        return False


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict, notion_token: str, database_id: str, email_sent: bool) -> bool:
    """Create a row in the Notion 'Memecoin Buy Now Signals' database. Returns True on success."""
    client = Client(auth=notion_token)
    properties: dict = {
        "Token":       {"title":     [{"text": {"content": signal["token"]}}]},
        "Signal":      {"select":    {"name": signal["signal"]}},
        "Email Sent":  {"checkbox":  email_sent},
        "Notes":       {"rich_text": [{"text": {"content": signal["notes"]}}]},
    }
    if signal["price_usd"]:
        properties["Price USD"]  = {"number": signal["price_usd"]}
    if signal["market_cap"]:
        properties["Market Cap"] = {"number": signal["market_cap"]}
    if signal["volume_24h"]:
        properties["Volume 24h"] = {"number": signal["volume_24h"]}

    properties["24h Change %"] = {"number": signal["change_24h"]}

    try:
        client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
        )
        print(f"[notifier] ✓ logged     → Notion  ({signal['token']})")
        return True
    except Exception as e:
        print(f"[notifier] ✗ Notion error: {e}")
        return False
