#!/usr/bin/env python3
"""
Hourly runner: checks signals → emails vickomela36@gmail.com and logs to
Notion when any token hits 'buy now'.

Required env vars:
  GMAIL_APP_PASSWORD  – Gmail App Password (Settings → Security → App passwords)
  GMAIL_SENDER        – (optional) sender address, defaults to vickomela36@gmail.com
  NOTION_TOKEN        – Notion internal integration token
"""
from __future__ import annotations

import json
import os
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
from signals import get_signals

# Tracks which pair addresses we have already alerted in the current hour,
# so we don't spam if the script is restarted mid-hour.
_SENT_LOG = os.path.join(os.path.dirname(__file__), ".sent_signals.json")


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def _current_hour() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")


def _load_sent() -> set[str]:
    if not os.path.exists(_SENT_LOG):
        return set()
    with open(_SENT_LOG) as f:
        data = json.load(f)
    return set(data.get(_current_hour(), []))


def _mark_sent(pair_address: str) -> None:
    hour = _current_hour()
    data: dict = {}
    if os.path.exists(_SENT_LOG):
        with open(_SENT_LOG) as f:
            data = json.load(f)
    data.setdefault(hour, [])
    if pair_address not in data[hour]:
        data[hour].append(pair_address)
    # Prune entries older than 48 h
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    data = {k: v for k, v in data.items() if k >= cutoff}
    with open(_SENT_LOG, "w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_email(signal: dict) -> bool:
    if not GMAIL_APP_PASSWORD:
        print("  [email] GMAIL_APP_PASSWORD not set — skipping")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"BUY NOW: {signal['symbol']}  {signal['price_change_24h']:+.1f}% 24h"
    )
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_EMAIL

    plain = (
        f"BUY NOW SIGNAL\n"
        f"{'='*40}\n"
        f"Token:         {signal['token_name']} ({signal['symbol']})\n"
        f"Price:         ${signal['price_usd']}\n"
        f"24h Change:    {signal['price_change_24h']:+.2f}%\n"
        f"Volume 24h:    ${signal['volume_24h_usd']:,.0f}\n"
        f"Liquidity:     ${signal['liquidity_usd']:,.0f}\n"
        f"Vol/Liq Ratio: {signal['vol_liq_ratio']:.2f}x\n"
        f"DexScreener:   {signal['dexscreener_url']}\n"
        f"Time (UTC):    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n"
    )

    html = f"""
<html><body style="font-family:sans-serif;max-width:480px">
<h2 style="color:#16a34a">BUY NOW: {signal['token_name']} ({signal['symbol']})</h2>
<table cellpadding="6" style="border-collapse:collapse;width:100%">
  <tr><td><b>Price</b></td><td>${signal['price_usd']}</td></tr>
  <tr style="background:#f0fdf4">
    <td><b>24h Change</b></td>
    <td style="color:#16a34a;font-weight:bold">{signal['price_change_24h']:+.2f}%</td>
  </tr>
  <tr><td><b>Volume 24h</b></td><td>${signal['volume_24h_usd']:,.0f}</td></tr>
  <tr style="background:#f0fdf4"><td><b>Liquidity</b></td><td>${signal['liquidity_usd']:,.0f}</td></tr>
  <tr><td><b>Vol/Liq Ratio</b></td><td>{signal['vol_liq_ratio']:.2f}x</td></tr>
</table>
<p style="margin-top:16px">
  <a href="{signal['dexscreener_url']}" style="background:#16a34a;color:white;padding:8px 16px;border-radius:4px;text-decoration:none">
    View on DexScreener →
  </a>
</p>
<p style="color:#6b7280;font-size:12px">
  Signal time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}
</p>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())
        print(f"  [email] sent for {signal['symbol']}")
        return True
    except Exception as exc:
        print(f"  [email] error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def log_to_notion(signal: dict, email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        print("  [notion] NOTION_TOKEN not set — skipping")
        return False

    now_iso = datetime.now(timezone.utc).isoformat()

    # Notion percent-format stores decimals (15 % → 0.15)
    price_change_decimal = signal["price_change_24h"] / 100.0

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token Name": {
                "title": [{"text": {"content": signal["token_name"]}}]
            },
            "Symbol": {
                "rich_text": [{"text": {"content": signal["symbol"]}}]
            },
            "Signal": {"select": {"name": "buy now"}},
            "Price USD": {
                "rich_text": [{"text": {"content": str(signal["price_usd"])}}]
            },
            "24h Change %": {"number": price_change_decimal},
            "Volume 24h USD": {"number": signal["volume_24h_usd"]},
            "Liquidity USD": {"number": signal["liquidity_usd"]},
            "Vol/Liq Ratio": {"number": signal["vol_liq_ratio"]},
            "Pair Address": {
                "rich_text": [{"text": {"content": signal["pair_address"]}}]
            },
            "DexScreener URL": {
                "url": signal["dexscreener_url"] or None
            },
            "Email Sent": {"checkbox": email_sent},
            "Timestamp": {"date": {"start": now_iso}},
        },
    }

    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        print(f"  [notion] logged {signal['symbol']}")
        return True
    except Exception as exc:
        print(f"  [notion] error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] memecoin-intel: checking signals…")

    signals = get_signals()
    buy_signals = [s for s in signals if s["signal"] == "buy now"]
    print(f"  {len(signals)} pairs scanned, {len(buy_signals)} buy signal(s) found")

    already_sent = _load_sent()

    for sig in buy_signals:
        addr = sig["pair_address"]
        if addr in already_sent:
            print(f"  already alerted {sig['symbol']} this hour — skipping")
            continue

        print(f"  *** BUY NOW: {sig['symbol']}  {sig['price_change_24h']:+.1f}%  "
              f"vol/liq={sig['vol_liq_ratio']:.1f}x ***")

        email_ok = send_email(sig)
        notion_ok = log_to_notion(sig, email_ok)

        if email_ok or notion_ok:
            _mark_sent(addr)


if __name__ == "__main__":
    run()
