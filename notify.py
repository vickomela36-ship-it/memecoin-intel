import smtplib
import logging
import requests
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_TO, NOTION_TOKEN, NOTION_DATABASE_ID,
)

if TYPE_CHECKING:
    from signals import TokenSignal

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ── Email ──────────────────────────────────────────────────────────────────────

def _build_html(tokens: list["TokenSignal"]) -> str:
    rows = ""
    for t in tokens:
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee"><strong>{t.token_name}</strong> ({t.ticker})</td>
          <td style="padding:8px;border-bottom:1px solid #eee">${t.price_usd:.6g}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;color:#16a34a">+{t.price_change_24h:.1f}%</td>
          <td style="padding:8px;border-bottom:1px solid #eee">${t.volume_24h:,.0f}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">${t.market_cap:,.0f}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{t.notes}</td>
          <td style="padding:8px;border-bottom:1px solid #eee"><a href="{t.pair_url}">Chart</a></td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;color:#111;max-width:900px;margin:auto">
      <h2 style="color:#16a34a">🟢 Memecoin Intel — BUY NOW Signals ({date.today()})</h2>
      <p>{len(tokens)} token(s) hit all buy criteria today.</p>
      <table style="border-collapse:collapse;width:100%">
        <thead>
          <tr style="background:#f0fdf4">
            <th style="padding:8px;text-align:left">Token</th>
            <th style="padding:8px;text-align:left">Price</th>
            <th style="padding:8px;text-align:left">24h %</th>
            <th style="padding:8px;text-align:left">Volume 24h</th>
            <th style="padding:8px;text-align:left">Mkt Cap</th>
            <th style="padding:8px;text-align:left">Why</th>
            <th style="padding:8px;text-align:left">Link</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Not financial advice. Always DYOR before trading.
      </p>
    </body></html>"""


def send_email(tokens: list["TokenSignal"]) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured — skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🟢 BUY NOW: {len(tokens)} Memecoin Signal(s) — {date.today()}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO

    plain = "\n".join(
        f"{t.ticker} ({t.token_name}): ${t.price_usd:.6g} | +{t.price_change_24h:.1f}% 24h | {t.notes}"
        for t in tokens
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(tokens), "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
        logger.info(f"Email sent to {EMAIL_TO} with {len(tokens)} signal(s)")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# ── Notion ─────────────────────────────────────────────────────────────────────

def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def log_to_notion(token: "TokenSignal", email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not configured — skipping Notion log")
        return False

    today = date.today().isoformat()
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token Name": {"title": [{"text": {"content": token.token_name}}]},
            "Ticker": {"rich_text": [{"text": {"content": token.ticker}}]},
            "Signal": {"select": {"name": token.signal}},
            "Price USD": {"number": token.price_usd},
            "Price Change 24h %": {"number": token.price_change_24h},
            "Volume 24h USD": {"number": token.volume_24h},
            "Market Cap USD": {"number": token.market_cap},
            "Contract Address": {"rich_text": [{"text": {"content": token.contract_address}}]},
            "Chain": {"rich_text": [{"text": {"content": token.chain}}]},
            "Signal Date": {"date": {"start": today}},
            "Email Sent": {"checkbox": email_sent},
            "Notes": {"rich_text": [{"text": {"content": token.notes[:2000]}}]},
        },
    }

    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            json=payload,
            headers=_notion_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"Logged {token.ticker} to Notion")
        return True
    except Exception as e:
        logger.error(f"Failed to log {token.ticker} to Notion: {e}")
        return False
