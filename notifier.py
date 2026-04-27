"""Email + Notion notifications for buy-now signals."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from notion_client import Client

import config
from signals import Signal

log = logging.getLogger(__name__)

_notion: Client | None = None


def _get_notion() -> Client:
    global _notion
    if _notion is None:
        _notion = Client(auth=config.NOTION_TOKEN)
    return _notion


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def log_to_notion(signal: Signal) -> None:
    """Add one row to the Notion 'Memecoin Buy Now Signals' database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        _get_notion().pages.create(
            parent={"database_id": config.NOTION_DATABASE_ID},
            properties={
                "Coin": {
                    "title": [{"text": {"content": signal.coin}}]
                },
                "Timestamp": {
                    "date": {"start": now_iso}
                },
                "Signal": {
                    "select": {"name": signal.signal}
                },
                "Confidence": {
                    "select": {"name": signal.confidence}
                },
                "Price USD": {
                    "number": signal.price_usd
                },
                "Price Change 1h %": {
                    "number": signal.price_change_1h
                },
                "Volume 24h": {
                    "number": signal.volume_24h
                },
                "Notes": {
                    "rich_text": [{"text": {"content": signal.notes}}]
                },
            },
        )
        log.info("Notion: logged %s → %s", signal.coin, signal.signal)
    except Exception as exc:
        log.error("Notion write failed for %s: %s", signal.coin, exc)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_html(signals: List[Signal]) -> str:
    rows = ""
    for s in signals:
        rows += (
            f"<tr>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'><b>{s.coin}</b></td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:#16a34a'>{s.signal.upper()}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{s.confidence}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>${s.price_usd:,.6f}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{s.price_change_1h:+.2f}%</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>${s.volume_24h:,.0f}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{s.notes}</td>"
            f"</tr>"
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
<html><body style="font-family:Arial,sans-serif;color:#1f2937">
<h2 style="color:#16a34a">🟢 Memecoin BUY NOW Alert — {timestamp}</h2>
<p>{len(signals)} token(s) triggered a <b>buy now</b> signal in this hourly scan.</p>
<table style="border-collapse:collapse;width:100%">
  <thead>
    <tr style="background:#f3f4f6">
      <th style="padding:8px 12px;text-align:left">Coin</th>
      <th style="padding:8px 12px;text-align:left">Signal</th>
      <th style="padding:8px 12px;text-align:left">Confidence</th>
      <th style="padding:8px 12px;text-align:left">Price USD</th>
      <th style="padding:8px 12px;text-align:left">1h Change</th>
      <th style="padding:8px 12px;text-align:left">24h Volume</th>
      <th style="padding:8px 12px;text-align:left">Notes</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<p style="color:#6b7280;font-size:12px;margin-top:24px">
  Sent by memecoin-intel · Signals logged to Notion
</p>
</body></html>"""


def _build_plain(signals: List[Signal]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"MEMECOIN BUY NOW ALERT — {timestamp}", ""]
    for s in signals:
        lines.append(
            f"  {s.coin}: {s.signal.upper()} ({s.confidence}) | "
            f"${s.price_usd:,.6f} | {s.price_change_1h:+.2f}% 1h | "
            f"vol ${s.volume_24h:,.0f}"
        )
        lines.append(f"  Notes: {s.notes}")
        lines.append("")
    lines.append("Signals logged to Notion.")
    return "\n".join(lines)


def send_email(signals: List[Signal]) -> None:
    """Send one email listing all buy-now signals."""
    if not signals:
        return

    coins = ", ".join(s.coin for s in signals)
    subject = f"🟢 BUY NOW: {coins}" if len(signals) <= 3 else f"🟢 BUY NOW: {len(signals)} memecoins triggered"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER
    msg["To"] = config.ALERT_EMAIL

    msg.attach(MIMEText(_build_plain(signals), "plain"))
    msg.attach(MIMEText(_build_html(signals), "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.SMTP_USER, config.ALERT_EMAIL, msg.as_string())
        log.info("Email sent to %s: %s", config.ALERT_EMAIL, subject)
    except Exception as exc:
        log.error("Email send failed: %s", exc)
