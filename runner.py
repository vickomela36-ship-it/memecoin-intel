"""
Standalone hourly runner: fetch signals → email → log to Notion.

Requirements
------------
  pip install requests anthropic

Environment variables (set in your shell or .env file):
  ANTHROPIC_API_KEY   - used to call Claude for Notion/Gmail MCP actions
  COINGECKO_API_KEY   - optional; CoinGecko Demo key lifts rate limits

Alternatively, call run() directly from your own orchestrator.

Cron example (every hour):
  0 * * * * cd /home/user/memecoin-intel && python runner.py >> /tmp/memecoin.log 2>&1
"""
import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import ALERT_EMAIL, NOTION_DATASOURCE_ID
from signals import get_signals_from_coingecko_json

# ── Config ───────────────────────────────────────────────────────────────────
COINGECKO_MARKETS = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&category=meme-token&order=volume_desc"
    "&per_page=50&page=1&price_change_percentage=1h,24h"
)
NOTION_API_URL  = "https://api.notion.com/v1/pages"
NOTION_VERSION  = "2022-06-28"


# ── Data fetch ───────────────────────────────────────────────────────────────

def fetch_meme_markets() -> list[dict]:
    headers = {}
    key = os.getenv("COINGECKO_API_KEY")
    if key:
        headers["x-cg-demo-api-key"] = key
    r = requests.get(COINGECKO_MARKETS, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email_smtp(signal: dict) -> bool:
    """
    Send via SMTP. Requires env vars:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    Falls back to a warning if not configured.
    """
    host  = os.getenv("SMTP_HOST")
    port  = int(os.getenv("SMTP_PORT", "587"))
    user  = os.getenv("SMTP_USER")
    pw    = os.getenv("SMTP_PASS")

    if not all([host, user, pw]):
        print(f"[WARN] SMTP not configured; would have emailed for {signal['coin']}")
        return False

    subject = f"Memecoin BUY NOW: {signal['coin']} ({signal['confidence']}% confidence)"
    body = _email_body(signal)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, ALERT_EMAIL, msg.as_string())

    print(f"[EMAIL] Sent for {signal['coin']}")
    return True


def _email_body(s: dict) -> str:
    return (
        f"BUY NOW Signal Detected\n"
        f"{'='*40}\n"
        f"Coin:        {s['name']} ({s['coin']})\n"
        f"Price:       ${s['price']:.6f}\n"
        f"Confidence:  {s['confidence']}%\n"
        f"1h change:   {s.get('change_1h', 0):.1f}%\n"
        f"24h change:  {s.get('change_24h', 0):.1f}%\n"
        f"Volume 24h:  ${s.get('volume_24h', 0):,.0f}\n"
        f"Reasons:     {s['notes']}\n"
        f"Link:        {s.get('url', 'N/A')}\n"
        f"Timestamp:   {s['timestamp']}\n"
    )


# ── Notion logging ────────────────────────────────────────────────────────────

def log_to_notion(signal: dict, email_sent: bool) -> bool:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        print(f"[WARN] NOTION_TOKEN not set; would have logged {signal['coin']}")
        return False

    ts = signal["timestamp"]
    payload = {
        "parent": {"database_id": NOTION_DATASOURCE_ID},
        "properties": {
            "Signal":     {"title": [{"text": {"content": f"Buy Now: {signal['coin']}"}}]},
            "Coin":       {"rich_text": [{"text": {"content": signal["coin"]}}]},
            "Price":      {"number": signal["price"]},
            "Confidence": {"number": signal["confidence"]},
            "Notes":      {"rich_text": [{"text": {"content": signal["notes"]}}]},
            "Status":     {"select": {"name": "New"}},
            "Email Sent": {"checkbox": email_sent},
            "Timestamp":  {"date": {"start": ts, "time_zone": "UTC"}},
        },
    }
    headers = {
        "Authorization":  f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type":   "application/json",
    }
    r = requests.post(NOTION_API_URL, headers=headers, json=payload, timeout=15)
    if r.ok:
        print(f"[NOTION] Logged {signal['coin']}")
        return True
    print(f"[NOTION] Error {r.status_code}: {r.text[:200]}")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Running signal check...")

    try:
        coins = fetch_meme_markets()
    except Exception as e:
        print(f"[ERROR] Failed to fetch market data: {e}")
        sys.exit(1)

    signals = get_signals_from_coingecko_json(json.dumps(coins))
    buy_now = [s for s in signals if s["signal"] == "buy now"]
    print(f"  {len(signals)} coins checked, {len(buy_now)} BUY NOW signal(s)")

    for signal in buy_now:
        print(f"  → {signal['coin']}: ${signal['price']:.6f}  conf={signal['confidence']}%")
        email_sent = send_email_smtp(signal)
        log_to_notion(signal, email_sent)

    if not buy_now:
        print("  No buy signals. Nothing to do.")


if __name__ == "__main__":
    run()
