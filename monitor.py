"""
Standalone hourly monitor — run this on your local machine.

    pip install requests
    python monitor.py                    # run once
    python monitor.py --loop             # run every hour indefinitely

Required environment variables:
    NOTION_API_KEY      your Notion integration secret
    GMAIL_SENDER        Gmail address to send FROM
    GMAIL_APP_PASSWORD  16-char Gmail app password (not your login password)

Optional:
    WALLET_ADDRESS      your Solana wallet (informational only)
"""

import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import ALERT_EMAIL, CHECK_INTERVAL_MINUTES, NOTION_DATA_SOURCE_ID
from signals import get_buy_signals, mark_notified

NOTION_VERSION = "2022-06-28"
NOTION_BASE     = "https://api.notion.com/v1"


# ── Notion ─────────────────────────────────────────────────────────────────────

def _notion_headers() -> dict:
    key = os.environ.get("NOTION_API_KEY", "")
    if not key:
        raise EnvironmentError("NOTION_API_KEY not set")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def log_to_notion(signal: dict) -> str:
    """Create a row in the Memecoin Buy Signals database. Returns the page ID."""
    ts = signal["timestamp"]
    payload = {
        "parent": {"database_id": NOTION_DATA_SOURCE_ID},
        "properties": {
            "Token Name":      {"title": [{"text": {"content": signal["token_name"]}}]},
            "Symbol":          {"rich_text": [{"text": {"content": signal["symbol"]}}]},
            "Signal":          {"select": {"name": "buy now"}},
            "Price USD":       {"rich_text": [{"text": {"content": signal["price_usd"]}}]},
            "Timestamp":       {"date": {"start": ts, "time_zone": None}},
            "24h Change %":    {"number": signal["change_24h_pct"] / 100},
            "Volume 24h USD":  {"number": signal["volume_24h_usd"]},
            "Liquidity USD":   {"number": signal["liquidity_usd"]},
            "Vol/Liq Ratio":   {"number": signal["vol_liq_ratio"]},
            "Pair Address":    {"rich_text": [{"text": {"content": signal["pair_address"]}}]},
            "DexScreener URL": {"url": signal["dexscreener_url"] or None},
            "Email Sent":      {"checkbox": False},
        },
    }
    r = requests.post(f"{NOTION_BASE}/pages", headers=_notion_headers(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["id"]


def mark_email_sent(page_id: str) -> None:
    payload = {"properties": {"Email Sent": {"checkbox": True}}}
    r = requests.patch(
        f"{NOTION_BASE}/pages/{page_id}",
        headers=_notion_headers(),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()


# ── Gmail SMTP ─────────────────────────────────────────────────────────────────

def _html_email(signal: dict) -> str:
    dex_link = signal["dexscreener_url"]
    link_html = f'<a href="{dex_link}">View on DexScreener</a>' if dex_link else "N/A"
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2 style="color:#16a34a">🚨 BUY NOW Signal Detected</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Token</td>
        <td style="padding:8px;border:1px solid #e5e7eb">{signal["token_name"]} ({signal["symbol"]})</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Price</td>
        <td style="padding:8px;border:1px solid #e5e7eb">${signal["price_usd"]}</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">24h Change</td>
        <td style="padding:8px;border:1px solid #e5e7eb;color:#16a34a">+{signal["change_24h_pct"]}%</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Volume 24h</td>
        <td style="padding:8px;border:1px solid #e5e7eb">${signal["volume_24h_usd"]:,.0f}</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Liquidity</td>
        <td style="padding:8px;border:1px solid #e5e7eb">${signal["liquidity_usd"]:,.0f}</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Vol/Liq Ratio</td>
        <td style="padding:8px;border:1px solid #e5e7eb">{signal["vol_liq_ratio"]}x</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Pair Address</td>
        <td style="padding:8px;border:1px solid #e5e7eb;font-size:12px">{signal["pair_address"]}</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">DexScreener</td>
        <td style="padding:8px;border:1px solid #e5e7eb">{link_html}</td></tr>
    <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">Detected at</td>
        <td style="padding:8px;border:1px solid #e5e7eb">{signal["timestamp"]}</td></tr>
  </table>
  <p style="font-size:12px;color:#6b7280;margin-top:20px">
    ⚠️ This is an automated signal — always do your own research before trading.
  </p>
</body>
</html>
"""


def send_email(signal: dict) -> None:
    sender   = os.environ.get("GMAIL_SENDER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not sender or not password:
        raise EnvironmentError("GMAIL_SENDER or GMAIL_APP_PASSWORD not set")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 BUY NOW: {signal['symbol']} ({signal['token_name']})"
    msg["From"]    = sender
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(_html_email(signal), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, ALERT_EMAIL, msg.as_string())


# ── Main run loop ──────────────────────────────────────────────────────────────

def run_once() -> int:
    """Check signals, notify, and return count of buy-now signals processed."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checking signals…")
    signals = get_buy_signals(skip_seen=True)

    if not signals:
        print("  No new buy signals.")
        return 0

    print(f"  Found {len(signals)} buy signal(s).")
    notified_pairs = []

    for sig in signals:
        name = f"{sig['symbol']} ({sig['token_name']})"
        try:
            page_id = log_to_notion(sig)
            print(f"  ✓ Logged to Notion: {name}")
        except Exception as e:
            print(f"  ✗ Notion log failed for {name}: {e}")
            page_id = None

        try:
            send_email(sig)
            print(f"  ✓ Email sent for: {name}")
            if page_id:
                mark_email_sent(page_id)
        except Exception as e:
            print(f"  ✗ Email failed for {name}: {e}")

        notified_pairs.append(sig["pair_address"])

    mark_notified(notified_pairs)
    return len(signals)


def main() -> None:
    loop = "--loop" in sys.argv
    if loop:
        interval = CHECK_INTERVAL_MINUTES * 60
        print(f"Starting monitor loop (every {CHECK_INTERVAL_MINUTES} min). Ctrl-C to stop.")
        while True:
            run_once()
            time.sleep(interval)
    else:
        run_once()


if __name__ == "__main__":
    main()
