"""
Notification layer.

send_email()    — sends an HTML alert via Gmail SMTP.
log_to_notion() — appends a row to the "Memecoin Buy Signals" Notion DB.
"""

import logging
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

log = logging.getLogger(__name__)

_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
_NOTION_VERSION   = "2022-06-28"


# ── Email ────────────────────────────────────────────────────────────────────

def _build_html(signals: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = "".join(
        f"""<tr>
          <td style="padding:6px 10px"><b>{s['token']}</b></td>
          <td style="padding:6px 10px">{s['chain'].upper()}</td>
          <td style="padding:6px 10px">${s['price_usd']}</td>
          <td style="padding:6px 10px;color:{'green' if float(s['change_1h'] or 0) >= 0 else 'red'}">
            {s['change_1h']}%
          </td>
          <td style="padding:6px 10px">${float(s['volume_24h'] or 0):,.0f}</td>
          <td style="padding:6px 10px">${float(s['liquidity'] or 0):,.0f}</td>
          <td style="padding:6px 10px"><a href="{s['dex_url']}">Chart ↗</a></td>
        </tr>"""
        for s in signals
    )
    return f"""
    <html><body style="font-family:sans-serif;background:#f9f9f9;padding:20px">
      <div style="max-width:700px;margin:auto;background:#fff;border-radius:8px;
                  padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
        <h2 style="color:#16a34a;margin-top:0">🚀 Memecoin Buy Signal(s) — {ts}</h2>
        <p><b>{len(signals)}</b> token(s) triggered a <b>BUY NOW</b> signal this hour.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <thead><tr style="background:#f3f4f6">
            <th style="padding:6px 10px;text-align:left">Token</th>
            <th style="padding:6px 10px;text-align:left">Chain</th>
            <th style="padding:6px 10px;text-align:left">Price</th>
            <th style="padding:6px 10px;text-align:left">1h %</th>
            <th style="padding:6px 10px;text-align:left">Vol 24h</th>
            <th style="padding:6px 10px;text-align:left">Liquidity</th>
            <th style="padding:6px 10px;text-align:left">Link</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px;font-size:12px;color:#9ca3af">
          Sent by memecoin-intel · Do your own research before trading.
        </p>
      </div>
    </body></html>"""


def send_email(signals: list[dict]) -> None:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials missing — skipping email (set GMAIL_SENDER and GMAIL_APP_PASSWORD in .env)")
        return

    subject = f"🚀 {len(signals)} Memecoin Buy Signal(s) Detected"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = ALERT_EMAIL

    msg.attach(MIMEText("Open in an HTML-capable email client to view this alert.", "plain"))
    msg.attach(MIMEText(_build_html(signals), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())
        log.info("Email sent → %s", ALERT_EMAIL)
    except smtplib.SMTPAuthenticationError:
        log.error("Gmail auth failed — check GMAIL_SENDER and GMAIL_APP_PASSWORD")
    except Exception as exc:
        log.error("Email send failed: %s", exc)


# ── Notion ───────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict) -> None:
    if not NOTION_TOKEN:
        log.warning("NOTION_TOKEN missing — skipping Notion log")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def rt(value: str) -> dict:
        return {"rich_text": [{"text": {"content": str(value)}}]}

    properties: dict = {
        "Token":          {"title":  [{"text": {"content": signal["token"]}}]},
        "Signal":         {"select": {"name": "buy now"}},
        "Chain":          rt(signal["chain"]),
        "DEX":            rt(signal["dex"]),
        "Price USD":      rt(signal["price_usd"]),
        "Token Address":  rt(signal["token_address"]),
        "1h Change %":    rt(signal["change_1h"]),
        "6h Change %":    rt(signal["change_6h"]),
        "24h Change %":   rt(signal["change_24h"]),
        "Volume 24h USD": rt(signal["volume_24h"]),
        "Liquidity USD":  rt(signal["liquidity"]),
        "Reason":         rt(signal["reason"]),
        "Checked At":     {"date": {"start": now}},
    }

    # DEX URL is a URL property — only set if non-empty
    if signal.get("dex_url"):
        properties["DEX URL"] = {"url": signal["dex_url"]}

    payload = {
        "parent":     {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    headers = {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Content-Type":   "application/json",
        "Notion-Version": _NOTION_VERSION,
    }

    try:
        resp = requests.post(_NOTION_PAGES_URL, headers=headers, json=payload, timeout=15)
        if resp.ok:
            log.info("Notion logged ✓ %s", signal["token"])
        else:
            log.error("Notion error %s: %s", resp.status_code, resp.text[:300])
    except Exception as exc:
        log.error("Notion request failed: %s", exc)
