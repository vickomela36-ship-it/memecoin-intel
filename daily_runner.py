"""
Daily memecoin signal runner.
- Fetches buy/sell signals for configured memecoins via CoinGecko
- Sends an email alert to ALERT_EMAIL for every 'buy now' signal
- Logs every 'buy now' signal to the Notion database
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from notion_client import Client as NotionClient

import config
from signals import run_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("daily_runner.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def send_email(signal: dict) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[Memecoin Intel] BUY NOW: {signal['coin']} ({signal['name']})"
    )
    msg["From"] = config.GMAIL_FROM
    msg["To"] = config.ALERT_EMAIL

    plain = (
        f"BUY NOW Signal — {signal['coin']} ({signal['name']})\n"
        f"Price:      ${signal['price_usd']:.8g}\n"
        f"24h Change: {signal['price_change_24h']:+.2f}%\n"
        f"Confidence: {signal['confidence'] * 100:.0f}%\n"
        f"Reason:     {signal['reason']}\n"
        f"Time:       {signal['timestamp']}\n\n"
        "This is an automated alert from memecoin-intel. Not financial advice."
    )

    html = f"""
<html><body style="font-family:sans-serif;max-width:560px;margin:auto">
  <div style="background:#16a34a;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">🚀 BUY NOW: {signal['coin']}</h2>
    <p style="margin:4px 0 0">{signal['name']}</p>
  </div>
  <div style="border:1px solid #d1fae5;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px">
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:6px 0;color:#6b7280">Price</td>
          <td style="padding:6px 0;font-weight:600">${signal['price_usd']:.8g}</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">24h Change</td>
          <td style="padding:6px 0;font-weight:600;color:#16a34a">{signal['price_change_24h']:+.2f}%</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Confidence</td>
          <td style="padding:6px 0;font-weight:600">{signal['confidence'] * 100:.0f}%</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Reason</td>
          <td style="padding:6px 0">{signal['reason']}</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Timestamp</td>
          <td style="padding:6px 0;font-size:13px">{signal['timestamp']}</td></tr>
    </table>
    <p style="margin-top:20px;font-size:11px;color:#9ca3af">
      Automated alert from memecoin-intel · Not financial advice
    </p>
  </div>
</body></html>
"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.GMAIL_FROM, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_FROM, config.ALERT_EMAIL, msg.as_string())

    log.info("Email sent for %s to %s", signal["coin"], config.ALERT_EMAIL)


def log_to_notion(signal: dict) -> None:
    notion = NotionClient(auth=config.NOTION_API_KEY)
    notion.pages.create(
        parent={"database_id": config.NOTION_DATABASE_ID},
        properties={
            "Signal": {
                "title": [{"text": {"content": signal["signal_label"]}}]
            },
            "Signal Type": {"select": {"name": "buy now"}},
            "Coin": {
                "rich_text": [{"text": {"content": signal["coin"]}}]
            },
            "Price USD": {"number": signal["price_usd"]},
            "Confidence": {"number": signal["confidence"]},
            "Reason": {
                "rich_text": [{"text": {"content": signal["reason"]}}]
            },
            "Timestamp": {"date": {"start": signal["timestamp"]}},
        },
    )
    log.info("Logged %s to Notion", signal["coin"])


def run() -> None:
    log.info("=== Daily memecoin signal run: %s ===", date.today())

    try:
        signals = run_signals(config.MEMECOIN_IDS)
    except Exception as exc:
        log.error("Failed to fetch signals: %s", exc)
        return

    buy_signals = [s for s in signals if s["signal"] == "buy now"]
    log.info(
        "Checked %d coin(s) — %d buy now signal(s)", len(signals), len(buy_signals)
    )

    for s in signals:
        log.info(
            "  %-6s %-8s confidence=%.0f%%  %s",
            s["coin"], s["signal"], s["confidence"] * 100, s["reason"],
        )

    for s in buy_signals:
        if config.GMAIL_FROM and config.GMAIL_APP_PASSWORD:
            try:
                send_email(s)
            except Exception as exc:
                log.error("Email failed for %s: %s", s["coin"], exc)
        else:
            log.warning("Gmail not configured — skipping email for %s", s["coin"])

        if config.NOTION_API_KEY:
            try:
                log_to_notion(s)
            except Exception as exc:
                log.error("Notion logging failed for %s: %s", s["coin"], exc)
        else:
            log.warning("Notion not configured — skipping log for %s", s["coin"])

    log.info("=== Run complete ===")


if __name__ == "__main__":
    run()
