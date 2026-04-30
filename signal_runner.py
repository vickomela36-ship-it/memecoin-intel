"""
signal_runner.py — hourly orchestrator for memecoin-intel.

For each 'buy now' signal from signals.py:
  1. Sends an alert email to ALERT_EMAIL via Gmail SMTP
  2. Logs a row to the Notion "Memecoin Buy Signals Log" database

Run manually:   python signal_runner.py
Run via cron:   0 * * * * cd /home/user/memecoin-intel && python signal_runner.py >> logs/runner.log 2>&1
"""

import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# Local imports
sys.path.insert(0, os.path.dirname(__file__))
from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from signals import run as get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_email_html(signals: list[dict]) -> str:
    rows = ""
    for s in signals:
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;color:#16a34a">{s['coin']}</td>
          <td style="padding:8px;border:1px solid #ddd">{s['name']}</td>
          <td style="padding:8px;border:1px solid #ddd">${s['price_usd']:.8f}</td>
          <td style="padding:8px;border:1px solid #ddd">{s['confidence']}/100</td>
          <td style="padding:8px;border:1px solid #ddd;color:#16a34a">+{s['change_1h']:.1f}%</td>
          <td style="padding:8px;border:1px solid #ddd">{s['change_6h']:.1f}%</td>
          <td style="padding:8px;border:1px solid #ddd">${s['volume_24h']:,.0f}</td>
          <td style="padding:8px;border:1px solid #ddd"><a href="{s['pair_url']}">Chart</a></td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;padding:20px">
      <h2 style="color:#15803d">🚀 Memecoin BUY NOW Signal{'' if len(signals)==1 else 's'}</h2>
      <p style="color:#555">Detected at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
      <table style="border-collapse:collapse;width:100%">
        <thead>
          <tr style="background:#f0fdf4">
            <th style="padding:8px;border:1px solid #ddd">Symbol</th>
            <th style="padding:8px;border:1px solid #ddd">Name</th>
            <th style="padding:8px;border:1px solid #ddd">Price</th>
            <th style="padding:8px;border:1px solid #ddd">Confidence</th>
            <th style="padding:8px;border:1px solid #ddd">1h %</th>
            <th style="padding:8px;border:1px solid #ddd">6h %</th>
            <th style="padding:8px;border:1px solid #ddd">Vol 24h</th>
            <th style="padding:8px;border:1px solid #ddd">Link</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:20px;color:#888;font-size:12px">
        ⚠️ Not financial advice. Always DYOR before trading memecoins.
      </p>
    </body></html>"""


def send_email(buy_signals: list[dict]) -> bool:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not set — skipping email. Set GMAIL_SENDER and GMAIL_APP_PASSWORD.")
        return False

    subject = (
        f"🚀 BUY NOW: {buy_signals[0]['coin']}"
        if len(buy_signals) == 1
        else f"🚀 BUY NOW: {len(buy_signals)} memecoin signals"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_EMAIL

    plain = "\n".join(
        f"{s['coin']} | ${s['price_usd']:.8f} | conf {s['confidence']} | 1h {s['change_1h']:.1f}% | {s['pair_url']}"
        for s in buy_signals
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_email_html(buy_signals), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())
        log.info("Email sent to %s — %s", ALERT_EMAIL, subject)
        return True
    except Exception as exc:
        log.error("Email send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Notion logging
# ---------------------------------------------------------------------------

def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def log_to_notion(signal: dict, email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        log.warning("NOTION_TOKEN not set — skipping Notion log.")
        return False

    ts = signal.get("timestamp", datetime.now(timezone.utc).isoformat())
    # Notion date property needs ISO-8601 without microseconds
    ts_clean = ts[:19] + "+00:00" if len(ts) > 19 else ts

    label = f"BUY NOW — {signal['coin']} @ ${signal['price_usd']:.8f}"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal": {"title": [{"text": {"content": label}}]},
            "Coin": {"rich_text": [{"text": {"content": signal.get("coin", "")}}]},
            "Price": {"number": signal.get("price_usd", 0)},
            "Confidence": {"number": signal.get("confidence", 0)},
            "Timestamp": {"date": {"start": ts_clean}},
            "Email Sent": {"checkbox": email_sent},
            "Notes": {
                "rich_text": [
                    {
                        "text": {
                            "content": (
                                f"1h: {signal.get('change_1h', 0):.1f}% | "
                                f"6h: {signal.get('change_6h', 0):.1f}% | "
                                f"24h: {signal.get('change_24h', 0):.1f}% | "
                                f"Vol24h: ${signal.get('volume_24h', 0):,.0f} | "
                                f"{signal.get('pair_url', '')}"
                            )
                        }
                    }
                ]
            },
            "Status": {"select": {"name": "New"}},
        },
    }

    try:
        r = requests.post(
            f"{NOTION_API}/pages",
            headers=_notion_headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        log.info("Notion row created for %s (conf %d)", signal["coin"], signal["confidence"])
        return True
    except Exception as exc:
        log.error("Notion log failed: %s — %s", exc, getattr(exc, "response", {}) and exc.response.text[:300])
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Signal runner started ===")
    all_signals = get_signals()

    if not all_signals:
        log.info("No signals returned.")
        return

    # Filter errors
    valid = [s for s in all_signals if "error" not in s]
    buy_now = [s for s in valid if s.get("signal") == "buy now"]

    log.info("Scanned %d pairs — %d buy-now signal(s)", len(valid), len(buy_now))

    if not buy_now:
        log.info("No 'buy now' signals this run. Nothing to do.")
        return

    # Send one consolidated email for all buy signals
    email_sent = send_email(buy_now)

    # Log each signal individually to Notion
    for sig in buy_now:
        log_to_notion(sig, email_sent)

    # Emit JSON summary (useful when called from a Claude loop prompt)
    print(json.dumps({"buy_signals": buy_now, "email_sent": email_sent}, indent=2))


if __name__ == "__main__":
    main()
