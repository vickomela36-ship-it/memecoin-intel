import logging
import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)

logger = logging.getLogger(__name__)

_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
_NOTION_HEADERS = {
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def send_email(signal: dict) -> bool:
    """Send a buy-now alert via Gmail SMTP. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.warning("Gmail credentials not set — skipping email for %s", signal["symbol"])
        return False

    symbol = signal["symbol"]
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html_body = f"""
    <html><body style="font-family:sans-serif">
    <h2 style="color:#16a34a">BUY NOW Signal — {symbol}</h2>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
      <tr><td><b>Pair Address</b></td><td>{signal['pair_address']}</td></tr>
      <tr><td><b>Price USD</b></td><td>${signal['price_usd']:.8f}</td></tr>
      <tr><td><b>Price Change 5m</b></td><td>+{signal['price_change_5m']:.2f}%</td></tr>
      <tr><td><b>Price Change 1h</b></td><td>+{signal['price_change_1h']:.2f}%</td></tr>
      <tr><td><b>Volume 5m</b></td><td>${signal['volume_5m_usd']:,.0f}</td></tr>
      <tr><td><b>Liquidity</b></td><td>${signal['liquidity_usd']:,.0f}</td></tr>
      <tr><td><b>Detected at</b></td><td>{now_str}</td></tr>
    </table>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Memecoin Intel] BUY NOW: {symbol}"
    msg["From"] = GMAIL_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        logger.info("Email sent for %s", symbol)
        return True
    except Exception as e:
        logger.error("Email failed for %s: %s", symbol, e)
        return False


def log_to_notion(signal: dict, email_sent: bool = False) -> bool:
    """Append a buy-now signal row to the Notion database. Returns True on success."""
    if not NOTION_TOKEN:
        logger.warning("NOTION_TOKEN not set — skipping Notion log for %s", signal["symbol"])
        return False

    now = datetime.now(timezone.utc)
    entry_title = f"{signal['symbol']} — {now.strftime('%Y-%m-%d %H:%M')} UTC"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal Entry": {"title": [{"text": {"content": entry_title}}]},
            "Symbol": {"rich_text": [{"text": {"content": signal["symbol"]}}]},
            "Pair Address": {"rich_text": [{"text": {"content": signal["pair_address"]}}]},
            "Signal": {"select": {"name": "buy now"}},
            "Price USD": {"number": signal["price_usd"]},
            "Price Change 5m %": {"number": signal["price_change_5m"]},
            "Price Change 1h %": {"number": signal["price_change_1h"]},
            "Volume 5m USD": {"number": signal["volume_5m_usd"]},
            "Liquidity USD": {"number": signal["liquidity_usd"]},
            "Email Sent": {"checkbox": email_sent},
            "Timestamp": {"date": {"start": now.isoformat()}},
        },
    }

    headers = {**_NOTION_HEADERS, "Authorization": f"Bearer {NOTION_TOKEN}"}
    try:
        resp = requests.post(_NOTION_PAGES_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("Logged %s to Notion", signal["symbol"])
        return True
    except Exception as e:
        logger.error("Notion log failed for %s: %s", signal["symbol"], e)
        return False


def process_buy_signal(signal: dict) -> None:
    """Send email alert and log to Notion for a single buy-now signal."""
    email_sent = send_email(signal)
    log_to_notion(signal, email_sent=email_sent)
