#!/usr/bin/env python3
"""
Standalone hourly monitor: fetch signals → email + Notion for every 'buy now'.
Designed to be run by cron; uses Gmail SMTP and Notion REST API directly.

Required env vars:
    GMAIL_SENDER        your Gmail address
    GMAIL_APP_PASSWORD  16-char Google app password
    NOTION_TOKEN        Notion internal-integration secret (secret_...)
    ALERT_EMAIL         (optional) override recipient; defaults to vickomela36@gmail.com
"""

import json
import smtplib
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Local modules
from signals import get_signals, get_simulated_signals
import config


# ── Notion helpers ──────────────────────────────────────────────────────────

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _notion_request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{NOTION_API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {config.NOTION_TOKEN}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def notion_was_recently_logged(token_symbol: str) -> bool:
    """Return True if this token already has an entry in the last DEDUP_WINDOW_SECONDS."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=config.DEDUP_WINDOW_SECONDS)
    payload = {
        "filter": {
            "and": [
                {"property": "Token", "rich_text": {"equals": token_symbol}},
                {"property": "Timestamp", "date": {"on_or_after": cutoff.isoformat()}},
            ]
        },
        "page_size": 1,
    }
    try:
        result = _notion_request("POST", f"/databases/{config.NOTION_DATABASE_ID}/query", payload)
        return len(result.get("results", [])) > 0
    except Exception as e:
        print(f"[WARN] Notion dedup check failed for {token_symbol}: {e}", file=sys.stderr)
        return False


def notion_log_signal(signal: dict) -> str:
    """Create a Notion page for the signal. Returns the page URL."""
    payload = {
        "parent": {"database_id": config.NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": f"{signal['token']} — buy now"}}]
            },
            "Token": {
                "rich_text": [{"text": {"content": signal["token"]}}]
            },
            "Price": {"number": signal["price_usd"]},
            "Score": {"number": signal["score"]},
            "Reason": {
                "rich_text": [{"text": {"content": signal["reason"]}}]
            },
            "Timestamp": {
                "date": {"start": signal["timestamp"]}
            },
            "Email Sent": {"checkbox": True},
        },
    }
    result = _notion_request("POST", "/pages", payload)
    return result.get("url", "")


# ── Gmail helpers ────────────────────────────────────────────────────────────

def _build_email(signal: dict) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"BUY NOW: {signal['token']} ({signal['chain'].upper()}) "
        f"— Score {signal['score']}/100"
    )
    msg["From"] = config.GMAIL_SENDER
    msg["To"] = config.ALERT_EMAIL

    plain = (
        f"BUY NOW Signal Detected\n"
        f"{'='*40}\n"
        f"Token    : {signal['token']} ({signal['chain'].upper()})\n"
        f"Score    : {signal['score']}/100\n"
        f"Price    : ${signal['price_usd']:.8g}\n"
        f"1h Change: +{signal['price_change_1h']:.1f}%\n"
        f"24h Chg  : {signal['price_change_24h']:+.1f}%\n"
        f"Vol 24h  : ${signal['volume_24h_usd']:,.0f}\n"
        f"Liquidity: ${signal['liquidity_usd']:,.0f}\n"
        f"Reason   : {signal['reason']}\n"
        f"Time     : {signal['timestamp']}\n"
        f"Chart    : {signal['pair_url']}\n"
    )

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
<h2 style="color:#e53e3e">🚨 BUY NOW: {signal['token']} ({signal['chain'].upper()})</h2>
<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;width:100%;font-size:14px">
  <tr style="background:#fff5f5">
    <td><b>Token</b></td>
    <td>{signal['token']} ({signal['chain'].upper()})</td>
  </tr>
  <tr><td><b>Score</b></td><td><b>{signal['score']}/100</b></td></tr>
  <tr style="background:#fff5f5">
    <td><b>Price (USD)</b></td><td>${signal['price_usd']:.8g}</td>
  </tr>
  <tr><td><b>1h Change</b></td>
      <td style="color:green"><b>+{signal['price_change_1h']:.1f}%</b></td></tr>
  <tr style="background:#fff5f5">
    <td><b>24h Change</b></td>
    <td style="color:{'green' if signal['price_change_24h'] >= 0 else 'red'}">
        {signal['price_change_24h']:+.1f}%</td>
  </tr>
  <tr><td><b>Volume 24h</b></td><td>${signal['volume_24h_usd']:,.0f}</td></tr>
  <tr style="background:#fff5f5">
    <td><b>Liquidity</b></td><td>${signal['liquidity_usd']:,.0f}</td>
  </tr>
  <tr><td><b>Reason</b></td><td>{signal['reason']}</td></tr>
  <tr style="background:#fff5f5">
    <td><b>Timestamp</b></td><td>{signal['timestamp']}</td>
  </tr>
</table>
<p style="margin-top:16px">
  <a href="{signal['pair_url']}" style="
     background:#3182ce;color:white;padding:10px 20px;
     text-decoration:none;border-radius:4px">
    View on DexScreener
  </a>
</p>
<hr style="margin-top:32px">
<small style="color:#888">memecoin-intel automated alert</small>
</body></html>"""

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_email(signal: dict) -> None:
    msg = _build_email(signal)
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_SENDER, config.ALERT_EMAIL, msg.as_string())


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    simulate = "--simulate" in sys.argv
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mode = "SIMULATE" if simulate else "LIVE"
    print(f"[{ts}] Starting memecoin signal check ({mode})...")

    missing = [v for v in ("GMAIL_SENDER", "GMAIL_APP_PASSWORD", "NOTION_TOKEN")
               if not getattr(config, v)]
    if missing:
        print(f"[ERROR] Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    all_signals = get_simulated_signals() if simulate else get_signals()
    buy_now = [s for s in all_signals if s.get("signal") == "buy now"]

    print(f"[{ts}] {len(all_signals)} candidates, {len(buy_now)} BUY NOW signal(s)")

    if not buy_now:
        print(f"[{ts}] No action required.")
        return

    processed = 0
    for signal in buy_now:
        token = signal["token"]

        if notion_was_recently_logged(token):
            print(f"[{ts}] SKIP {token} — already logged within dedup window")
            continue

        # Log to Notion first (so Email Sent=true is accurate even if email fails)
        try:
            page_url = notion_log_signal(signal)
            print(f"[{ts}] Notion logged: {token} → {page_url}")
        except Exception as e:
            print(f"[{ts}] ERROR logging {token} to Notion: {e}", file=sys.stderr)
            continue

        # Send email
        try:
            send_email(signal)
            print(f"[{ts}] Email sent: {token} → {config.ALERT_EMAIL}")
        except Exception as e:
            print(f"[{ts}] ERROR sending email for {token}: {e}", file=sys.stderr)

        processed += 1

    print(f"[{ts}] Done — {processed} new alert(s) sent.")


if __name__ == "__main__":
    main()
