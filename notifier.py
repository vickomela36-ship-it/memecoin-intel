"""
Handles notifications for buy-now signals:
  - Sends an email via Gmail (SMTP) to ALERT_EMAIL
  - Logs the signal row to the Notion "Memecoin Buy Signals Log" database

Environment variables required for Gmail SMTP:
  GMAIL_USER     — sender Gmail address
  GMAIL_APP_PASS — Gmail App Password (not your login password)
"""

import os
import smtplib
import json
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import ALERT_EMAIL

# Notion integration
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get(
    "NOTION_DB_ID",
    "44763c62-4d07-4fde-bb1c-503846807aeb",  # created by Claude setup
)
NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# Gmail SMTP
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_email_body(signal_data: dict) -> tuple[str, str]:
    """Return (subject, html_body) for a buy-now alert."""
    symbol = signal_data.get("symbol", "?")
    price = signal_data.get("price_usd", 0)
    chg5m = signal_data.get("price_change_5m", 0)
    chg1h = signal_data.get("price_change_1h", 0)
    vol5m = signal_data.get("volume_5m_usd", 0)
    liq = signal_data.get("liquidity_usd", 0)
    ts = signal_data.get("timestamp", datetime.now(timezone.utc).isoformat())
    pair = signal_data.get("pair_address", "")

    subject = f"🚀 BUY NOW Signal: {symbol} | +{chg5m:.1f}% (5m) | ${price:.6f}"

    dex_link = (
        f"https://dexscreener.com/solana/{pair}"
        if pair else "https://dexscreener.com"
    )

    html = f"""
    <html><body style="font-family:sans-serif;background:#0d0d0d;color:#e0e0e0;padding:24px">
      <h2 style="color:#00ff88">🚀 BUY NOW — {symbol}</h2>
      <table style="border-collapse:collapse;width:100%;max-width:480px">
        <tr><td style="padding:6px 12px;color:#aaa">Price</td>
            <td style="padding:6px 12px;font-weight:bold">${price:.8f}</td></tr>
        <tr style="background:#1a1a1a"><td style="padding:6px 12px;color:#aaa">5m change</td>
            <td style="padding:6px 12px;color:#00ff88">+{chg5m:.2f}%</td></tr>
        <tr><td style="padding:6px 12px;color:#aaa">1h change</td>
            <td style="padding:6px 12px;color:#00ff88">+{chg1h:.2f}%</td></tr>
        <tr style="background:#1a1a1a"><td style="padding:6px 12px;color:#aaa">Volume (5m)</td>
            <td style="padding:6px 12px">${vol5m:,.0f}</td></tr>
        <tr><td style="padding:6px 12px;color:#aaa">Liquidity</td>
            <td style="padding:6px 12px">${liq:,.0f}</td></tr>
        <tr style="background:#1a1a1a"><td style="padding:6px 12px;color:#aaa">Detected at</td>
            <td style="padding:6px 12px">{ts}</td></tr>
      </table>
      <br>
      <a href="{dex_link}" style="background:#00ff88;color:#000;padding:10px 20px;
         text-decoration:none;border-radius:6px;font-weight:bold">
        View on DexScreener →
      </a>
      <p style="color:#555;font-size:12px;margin-top:24px">
        Sent by memecoin-intel · Not financial advice.
      </p>
    </body></html>
    """
    return subject, html


def send_email_alert(signal_data: dict) -> bool:
    """Send a buy-now alert email via Gmail SMTP. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("[notifier] Gmail credentials not set — skipping email.")
        return False

    subject, html = _build_email_body(signal_data)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        print(f"[notifier] Email sent to {ALERT_EMAIL}")
        return True
    except Exception as exc:
        print(f"[notifier] Email failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Notion logging
# ---------------------------------------------------------------------------

def log_to_notion(signal_data: dict, email_sent: bool = False) -> bool:
    """Add a row to the Memecoin Buy Signals Log Notion database."""
    if not NOTION_TOKEN:
        print("[notifier] NOTION_TOKEN not set — skipping Notion log.")
        return False

    symbol = signal_data.get("symbol", "?")
    ts = signal_data.get("timestamp", datetime.now(timezone.utc).isoformat())
    # Notion date fields need ISO-8601; strip sub-second precision if needed
    notion_ts = ts[:19] if len(ts) > 19 else ts

    title = f"{symbol} – {notion_ts}"

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Signal Entry": {"title": [{"text": {"content": title}}]},
            "Signal": {"select": {"name": signal_data.get("signal", "hold")}},
            "Symbol": {"rich_text": [{"text": {"content": symbol}}]},
            "Pair Address": {
                "rich_text": [{"text": {"content": signal_data.get("pair_address", "")}}]
            },
            "Price USD": {"number": signal_data.get("price_usd", 0)},
            "Price Change 5m %": {"number": signal_data.get("price_change_5m", 0)},
            "Price Change 1h %": {"number": signal_data.get("price_change_1h", 0)},
            "Volume 5m USD": {"number": signal_data.get("volume_5m_usd", 0)},
            "Liquidity USD": {"number": signal_data.get("liquidity_usd", 0)},
            "Timestamp": {"date": {"start": notion_ts}},
            "Email Sent": {"checkbox": email_sent},
        },
    }

    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            headers=NOTION_HEADERS,
            data=json.dumps(payload),
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[notifier] Logged to Notion: {title}")
        return True
    except Exception as exc:
        print(f"[notifier] Notion log failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Combined handler
# ---------------------------------------------------------------------------

def handle_buy_signal(signal_data: dict) -> None:
    """Send email alert and log to Notion for a single buy-now signal."""
    email_ok = send_email_alert(signal_data)
    log_to_notion(signal_data, email_sent=email_ok)
