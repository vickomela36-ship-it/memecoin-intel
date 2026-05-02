"""
Hourly memecoin signal watcher.
Reads signals.py output, and on 'buy now':
  - Sends email to vickomela36@gmail.com via Gmail SMTP
  - Logs the event to Notion via REST API

Required environment variables:
  GMAIL_SENDER        your Gmail address (e.g. you@gmail.com)
  GMAIL_APP_PASSWORD  Gmail App Password (not your normal password)
  NOTION_API_KEY      Notion Integration secret token
  TOKEN_ADDRESS       Solana token mint address to track

Optional:
  NOTION_DB_ID        Notion database ID (defaults to the pre-created one)

Run once:  python watcher.py
Cron:      0 * * * * cd /home/user/memecoin-intel && python watcher.py >> logs/watcher.log 2>&1
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

# Import signal logic from sibling module
sys.path.insert(0, os.path.dirname(__file__))
from signals import get_signal

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RECIPIENT_EMAIL = "vickomela36@gmail.com"
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "c7f3d2af-bf40-4406-9e7f-b998f7123168")


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
_EMAIL_HTML = """\
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: Arial, sans-serif; background: #0d0d0d; color: #e0e0e0; padding: 24px; }}
  .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; max-width: 480px; margin: auto;
           border: 1px solid #00ff88; }}
  h1 {{ color: #00ff88; font-size: 1.4em; margin-top: 0; }}
  .row {{ display: flex; justify-content: space-between; padding: 6px 0;
          border-bottom: 1px solid #2a2a4a; }}
  .label {{ color: #888; font-size: 0.9em; }}
  .value {{ font-weight: bold; }}
  .confidence-high {{ color: #00ff88; }}
  .confidence-medium {{ color: #ffd700; }}
  .confidence-low {{ color: #ff6b6b; }}
  .footer {{ margin-top: 16px; font-size: 0.75em; color: #555; text-align: center; }}
</style>
</head>
<body>
<div class="card">
  <h1>🚨 BUY SIGNAL DETECTED</h1>
  <div class="row"><span class="label">Token</span><span class="value">{token}</span></div>
  <div class="row"><span class="label">Price</span><span class="value">${price:.6f}</span></div>
  <div class="row"><span class="label">1h Change</span>
    <span class="value" style="color:#00ff88">+{change_1h:.2f}%</span></div>
  <div class="row"><span class="label">24h Change</span><span class="value">{change_24h:+.2f}%</span></div>
  <div class="row"><span class="label">Volume 1h</span><span class="value">${volume:,.0f}</span></div>
  <div class="row"><span class="label">Vol Spike</span><span class="value">{spike:.1f}x avg</span></div>
  <div class="row"><span class="label">Confidence</span>
    <span class="value confidence-{conf_class}">{confidence}</span></div>
  <div class="row"><span class="label">Reason</span><span class="value">{reason}</span></div>
  <div class="row"><span class="label">Triggered</span><span class="value">{timestamp}</span></div>
  <div class="footer">memecoin-intel · automated signal alert</div>
</div>
</body>
</html>
"""


def send_email(signal: dict) -> bool:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[watcher] GMAIL_SENDER / GMAIL_APP_PASSWORD not set — skipping email")
        return False

    token = signal.get("token", "?")
    price = signal.get("price") or 0.0
    change_1h = signal.get("price_change_1h_pct") or 0.0
    change_24h = signal.get("price_change_24h_pct") or 0.0
    volume = signal.get("volume_1h_usd") or 0.0
    spike = signal.get("volume_spike_multiplier") or 0.0
    confidence = signal.get("confidence", "unknown")
    reason = signal.get("reason", "")
    timestamp = signal.get("timestamp", datetime.now(timezone.utc).isoformat())

    html_body = _EMAIL_HTML.format(
        token=token,
        price=price,
        change_1h=change_1h,
        change_24h=change_24h,
        volume=volume,
        spike=spike,
        confidence=confidence,
        conf_class=confidence if confidence in ("high", "medium", "low") else "low",
        reason=reason,
        timestamp=timestamp,
    )
    plain_body = (
        f"BUY SIGNAL: {token}\n"
        f"Price: ${price:.6f}\n"
        f"1h Change: +{change_1h:.2f}%\n"
        f"Volume 1h: ${volume:,.0f}\n"
        f"Spike: {spike:.1f}x\n"
        f"Confidence: {confidence}\n"
        f"Reason: {reason}\n"
        f"Timestamp: {timestamp}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 MEMECOIN BUY SIGNAL: {token}"
    msg["From"] = GMAIL_SENDER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, [RECIPIENT_EMAIL], msg.as_string())
        print(f"[watcher] Email sent to {RECIPIENT_EMAIL}")
        return True
    except Exception as exc:
        print(f"[watcher] Email failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Notion logging
# ---------------------------------------------------------------------------

def log_to_notion(signal: dict, email_sent: bool) -> bool:
    if not NOTION_API_KEY:
        print("[watcher] NOTION_API_KEY not set — skipping Notion log")
        return False

    token = signal.get("token", "?")
    price = signal.get("price") or None
    change_24h = signal.get("price_change_24h_pct") or None
    volume_1h = signal.get("volume_1h_usd") or None
    confidence = signal.get("confidence", "")
    reason = signal.get("reason", "")
    notes = f"{reason} | confidence: {confidence}" if reason else confidence

    props = {
        "Token": {"title": [{"text": {"content": token}}]},
        "Signal": {"select": {"name": "buy now"}},
    }
    if price is not None:
        props["Price USD"] = {"number": price}
    if change_24h is not None:
        props["24h Change %"] = {"number": change_24h}
    if volume_1h is not None:
        props["Volume 24h"] = {"number": volume_1h}
    if notes:
        props["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}
    props["Email Sent"] = {"checkbox": email_sent}

    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": props}
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        print(f"[watcher] Notion row created for {token}")
        return True
    except Exception as exc:
        print(f"[watcher] Notion log failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[watcher] {now} — checking signal …")

    signal = get_signal()
    sig_type = signal.get("signal", "hold")
    token = signal.get("token", "?")

    print(f"[watcher] signal={sig_type!r}  token={token}  reason={signal.get('reason', '')}")

    if sig_type == "buy now":
        email_ok = send_email(signal)
        log_to_notion(signal, email_sent=email_ok)
        print(f"[watcher] BUY NOW processed for {token}")
    else:
        print(f"[watcher] No action (signal={sig_type!r})")


if __name__ == "__main__":
    main()
