#!/usr/bin/env python3
"""Hourly runner: check signals → log buy-now entries to Notion → send email alert."""
import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    NOTION_API_KEY,
    NOTION_DATABASE_ID,
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    ALERT_EMAIL,
)
from signals import get_signals

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _log_notion(s: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    label = f"{s['symbol']} – buy now @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal Entry":      {"title":     [{"text": {"content": label}}]},
            "Symbol":            {"rich_text": [{"text": {"content": s["symbol"]}}]},
            "Signal":            {"select":    {"name": s["signal"]}},
            "Price USD":         {"number": s["price_usd"]},
            "Price Change 5m %": {"number": s["price_change_5m"]},
            "Price Change 1h %": {"number": s["price_change_1h"]},
            "Volume 5m USD":     {"number": s["volume_5m_usd"]},
            "Liquidity USD":     {"number": s["liquidity_usd"]},
            "Pair Address":      {"rich_text": [{"text": {"content": s["pair_address"]}}]},
            "Timestamp":         {"date": {"start": now}},
            "Email Sent":        {"checkbox": True},
        },
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages", json=payload, headers=NOTION_HEADERS
    )
    resp.raise_for_status()


def _send_email(s: dict) -> None:
    dex_url = f"https://dexscreener.com/solana/{s['pair_address']}"
    plain = (
        f"BUY NOW Signal — {s['symbol']}\n"
        f"{'─' * 40}\n"
        f"Price:       ${s['price_usd']:.8f}\n"
        f"5m Change:   {s['price_change_5m']:+.2f}%\n"
        f"1h Change:   {s['price_change_1h']:+.2f}%\n"
        f"5m Volume:   ${s['volume_5m_usd']:,.0f}\n"
        f"Liquidity:   ${s['liquidity_usd']:,.0f}\n"
        f"Pair:        {s['pair_address']}\n"
        f"Time:        {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
        f"Chart: {dex_url}\n"
    )
    html = f"""
<html><body style="font-family:monospace;font-size:14px;">
<h2 style="color:#16a34a;">🚀 BUY NOW — {s['symbol']}</h2>
<table cellpadding="6">
  <tr><td>Price</td><td><b>${s['price_usd']:.8f}</b></td></tr>
  <tr><td>5m Change</td><td style="color:{'#16a34a' if s['price_change_5m']>=0 else '#dc2626'}"><b>{s['price_change_5m']:+.2f}%</b></td></tr>
  <tr><td>1h Change</td><td style="color:{'#16a34a' if s['price_change_1h']>=0 else '#dc2626'}"><b>{s['price_change_1h']:+.2f}%</b></td></tr>
  <tr><td>5m Volume</td><td><b>${s['volume_5m_usd']:,.0f}</b></td></tr>
  <tr><td>Liquidity</td><td><b>${s['liquidity_usd']:,.0f}</b></td></tr>
  <tr><td>Pair</td><td><code>{s['pair_address']}</code></td></tr>
  <tr><td>Time</td><td>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</td></tr>
</table>
<br><a href="{dex_url}">Open on DexScreener</a>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[memecoin-intel] BUY NOW: {s['symbol']}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())


def run() -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] signal check started")
    signals = get_signals()

    if not signals:
        print(f"[{ts}] no pairs configured — add addresses to WATCHED_PAIRS in config.py")
        return

    buy_count = 0
    for s in signals:
        print(f"  {s['symbol']:12s} → {s['signal']}")
        if s["signal"] != "buy now":
            continue

        buy_count += 1
        try:
            _log_notion(s)
            print(f"    ✓ logged to Notion")
        except Exception as exc:
            print(f"    ✗ Notion error: {exc}")

        try:
            _send_email(s)
            print(f"    ✓ email sent → {ALERT_EMAIL}")
        except Exception as exc:
            print(f"    ✗ email error: {exc}")

    print(f"[{ts}] done — {len(signals)} pairs checked, {buy_count} buy-now alerts")


if __name__ == "__main__":
    run()
