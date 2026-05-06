import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from notion_client import Client
from notion_client.errors import APIResponseError

from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from signals import Signal

logger = logging.getLogger(__name__)


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email(signals: list[Signal]) -> MIMEMultipart:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(signals)
    subject = f"🚀 {count} Memecoin Buy Now Signal{'s' if count != 1 else ''} — {now}"

    plain_lines = [f"Memecoin Buy Now Alerts  |  {now}", "=" * 50, ""]
    html_rows = ""

    for s in signals:
        plain_lines += [
            f"● {s.coin}  [{s.strength}]",
            f"  Price:       ${s.price_usd:.8f}",
            f"  1h Change:   +{s.price_change_1h:.1f}%",
            f"  24h Change:  {s.price_change_24h:+.1f}%",
            f"  Volume 24h:  ${s.volume_24h:,.0f}",
            f"  Notes:       {s.notes}",
            f"  Chart:       {s.pair_url}",
            "",
        ]
        badge_color = {"Strong": "#00c853", "Moderate": "#ffd600", "Weak": "#ff6d00"}.get(
            s.strength, "#aaa"
        )
        html_rows += (
            f"<tr>"
            f"<td style='padding:8px;font-weight:bold'>{s.coin}</td>"
            f"<td style='padding:8px;color:{badge_color};font-weight:bold'>{s.strength}</td>"
            f"<td style='padding:8px'>${s.price_usd:.8f}</td>"
            f"<td style='padding:8px;color:#00c853'>+{s.price_change_1h:.1f}%</td>"
            f"<td style='padding:8px'>${s.volume_24h:,.0f}</td>"
            f"<td style='padding:8px'>{s.notes}</td>"
            f"<td style='padding:8px'><a href='{s.pair_url}'>Chart ↗</a></td>"
            f"</tr>"
        )

    html = (
        "<html><body style='font-family:Arial,sans-serif'>"
        f"<h2>🚀 Memecoin Buy Now Alert</h2>"
        f"<p style='color:#888'>{now}</p>"
        "<table border='1' cellpadding='4' style='border-collapse:collapse;font-size:13px'>"
        "<tr style='background:#1a1a2e;color:#fff'>"
        "<th>Coin</th><th>Strength</th><th>Price (USD)</th>"
        "<th>1h Change</th><th>Volume 24h</th><th>Notes</th><th>Chart</th>"
        "</tr>"
        f"{html_rows}"
        "</table></body></html>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText("\n".join(plain_lines), "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_email(signals: list[Signal]) -> bool:
    """Send a buy-now alert email via Gmail SMTP. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials missing — set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False

    try:
        msg = _build_email(signals)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        logger.info(f"Alert email sent to {ALERT_EMAIL} ({len(signals)} signal(s))")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed — check GMAIL_USER and GMAIL_APP_PASSWORD")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}")
        return False


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: Signal) -> bool:
    """Create a row in the 'Memecoin Buy Now Signals' Notion database."""
    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set — cannot log to Notion")
        return False

    notion = Client(auth=NOTION_TOKEN)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Signal Name": {
                    "title": [{"text": {"content": f"Buy Now — {signal.coin}"}}]
                },
                "Coin": {
                    "rich_text": [{"text": {"content": signal.coin}}]
                },
                "Price (USD)": {"number": signal.price_usd},
                "Price Change %": {"number": signal.price_change_1h},
                "Volume 24h": {"number": signal.volume_24h},
                "Signal Strength": {"select": {"name": signal.strength}},
                "Timestamp": {"date": {"start": now_iso}},
                "Notes": {
                    "rich_text": [{"text": {"content": signal.notes}}]
                },
            },
        )
        logger.info(f"Logged '{signal.coin}' [{signal.strength}] to Notion")
        return True
    except APIResponseError as e:
        logger.error(f"Notion API error for {signal.coin}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected Notion error for {signal.coin}: {e}")
        return False


# ── Combined ──────────────────────────────────────────────────────────────────

def notify(signals: list[Signal]) -> None:
    """Send email alert and log every signal to Notion."""
    if not signals:
        return
    send_email(signals)
    for sig in signals:
        log_to_notion(sig)
