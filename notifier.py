"""Email and Notion notification helpers for standalone use."""
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)


def send_email(signal: dict) -> None:
    """Send a buy-now alert email via Gmail SMTP."""
    token = signal.get("token", "UNKNOWN")
    chain = signal.get("chain", "")
    price = signal.get("price_usd", 0)
    change = signal.get("price_change_1h", 0)
    volume = signal.get("volume_24h", 0)
    liquidity = signal.get("liquidity_usd", 0)
    url = signal.get("dexscreener_url", "")
    name = signal.get("token_name", token)
    addr = signal.get("token_address", "")

    subject = f"[BUY NOW] {token} on {chain.upper()} — {change:+.1f}% in 1h"
    body = (
        f"BUY NOW signal detected\n"
        f"{'='*50}\n"
        f"Token:         {name} ({token})\n"
        f"Chain:         {chain.upper()}\n"
        f"Address:       {addr}\n\n"
        f"Price:         ${price:.8f}\n"
        f"1h Change:     {change:+.1f}%\n"
        f"Volume 24h:    ${volume:,.0f}\n"
        f"Liquidity:     ${liquidity:,.0f}\n\n"
        f"DexScreener:   {url}\n\n"
        f"Checked at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())


def log_to_notion(signal: dict) -> None:
    """Insert a row into the Memecoin Buy Now Signals Notion database."""
    dex_url = signal.get("dexscreener_url") or None
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {
                "title": [{"text": {"content": signal.get("token", "UNKNOWN")}}]
            },
            "Signal": {"select": {"name": "buy now"}},
            "Price USD": {"number": signal.get("price_usd") or 0},
            "Price Change 1h %": {"number": signal.get("price_change_1h") or 0},
            "Volume 24h": {"number": signal.get("volume_24h") or 0},
            "Liquidity USD": {"number": signal.get("liquidity_usd") or 0},
            "Chain": {
                "rich_text": [{"text": {"content": signal.get("chain", "")}}]
            },
            "Token Address": {
                "rich_text": [{"text": {"content": signal.get("token_address", "")}}]
            },
            **({"DexScreener URL": {"url": dex_url}} if dex_url else {}),
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
