#!/usr/bin/env python3
"""Hourly memecoin buy-signal monitor.

For every 'buy now' signal found:
  1. Logs the entry to the Notion database.
  2. Sends a consolidated alert email to the configured recipient.

Run directly or via cron (see setup_cron.sh).
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
    RECIPIENT_EMAIL,
    WATCH_LIST,
)
from signals import get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

_NOTION_URL = "https://api.notion.com/v1/pages"
_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# Notion logging
# ---------------------------------------------------------------------------

def _log_to_notion(signal: dict) -> None:
    if not NOTION_TOKEN:
        log.warning("NOTION_TOKEN not configured — skipping Notion log.")
        return

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {
                "title": [{"text": {"content": signal["token"]}}]
            },
            "Chain": {
                "rich_text": [{"text": {"content": signal["chain"]}}]
            },
            "Token Address": {
                "rich_text": [{"text": {"content": signal["token_address"]}}]
            },
            "DexScreener URL": {
                "url": signal["dexscreener_url"] or None
            },
            "Price USD": {"number": signal["price_usd"]},
            "Price Change 1h %": {"number": signal["price_change_1h"]},
            "Volume 24h": {"number": signal["volume_24h"]},
            "Liquidity USD": {"number": signal["liquidity_usd"]},
            "Signal": {"select": {"name": "buy now"}},
        },
    }

    resp = requests.post(_NOTION_URL, headers=_NOTION_HEADERS, json=payload, timeout=15)
    if resp.ok:
        log.info("Notion: logged '%s'.", signal["token"])
    else:
        log.error("Notion error for %s: %s", signal["token"], resp.text)


# ---------------------------------------------------------------------------
# Email alert
# ---------------------------------------------------------------------------

def _send_email(signals: list[dict]) -> None:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not configured — skipping email.")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[Memecoin Intel] {len(signals)} BUY NOW signal(s) — {now}"

    rows = "".join(
        f"""
        <tr>
          <td><b>{s['token']}</b></td>
          <td>{s['chain'].upper()}</td>
          <td>${s['price_usd']:.8f}</td>
          <td style="color:green">+{s['price_change_1h']:.1f}%</td>
          <td>${s['volume_24h']:,.0f}</td>
          <td>${s['liquidity_usd']:,.0f}</td>
          <td><a href="{s['dexscreener_url']}">View</a></td>
        </tr>"""
        for s in signals
    )

    html = f"""
    <html><body style="font-family:sans-serif">
    <h2 style="color:#1a1a1a">&#128640; Memecoin BUY NOW Signals</h2>
    <p style="color:#555">{now}</p>
    <table border="1" cellpadding="8" cellspacing="0"
           style="border-collapse:collapse;width:100%">
      <thead style="background:#f0f0f0">
        <tr>
          <th>Token</th><th>Chain</th><th>Price</th>
          <th>1h Change</th><th>Volume 24h</th><th>Liquidity</th><th>Link</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="color:#999;font-size:11px;margin-top:16px">
      Criteria: &ge;5% 1h gain &bull; &ge;$50k 24h volume &bull;
      &ge;$10k liquidity &bull; vol/liq &ge;0.3
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, RECIPIENT_EMAIL, msg.as_string())
        log.info("Email sent → %s (%d signal(s)).", RECIPIENT_EMAIL, len(signals))
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to send email: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    log.info("=== Monitor run started ===")
    buy_signals = get_signals(WATCH_LIST or None)

    if not buy_signals:
        log.info("No 'buy now' signals this run.")
        return

    log.info("%d 'buy now' signal(s) found.", len(buy_signals))

    for signal in buy_signals:
        _log_to_notion(signal)

    _send_email(buy_signals)
    log.info("=== Run complete ===")


if __name__ == "__main__":
    run()
