#!/usr/bin/env python3
"""
notifier.py — check for unprocessed 'buy now' signals in Notion,
send a Gmail alert for each one, and mark them as Email Sent.

Runs standalone; no Claude / MCP required.
Credentials come from config.py (see config.py for setup instructions).

Usage:
    python3 notifier.py           # normal hourly run
    python3 notifier.py --demo    # inject a demo signal and notify
"""

import json
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from config import NOTION_TOKEN, NOTION_DB_ID, GMAIL_SENDER, GMAIL_APP_PASS, ALERT_RECIPIENT
except ImportError:
    print("ERROR: config.py not found or incomplete. See config.py for setup.", file=sys.stderr)
    sys.exit(2)


# ── Notion helpers ────────────────────────────────────────────────────────────
_NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}


def _notion(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=_NOTION_HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _text_val(props: dict, key: str) -> str:
    v = props.get(key, {})
    for t in ("rich_text", "title"):
        parts = v.get(t, [])
        if parts:
            return "".join(c.get("plain_text", "") for c in parts)
    return ""


def fetch_unprocessed_signals() -> list[dict]:
    """Return all 'buy now' rows added in the last 2 hours where Email Sent = false."""
    since = (datetime.now(timezone.utc) - timedelta(hours=2)).date().isoformat()
    body  = {
        "filter": {
            "and": [
                {"property": "Email Sent", "checkbox": {"equals": False}},
                {"property": "Timestamp",  "date": {"on_or_after": since}},
            ]
        },
        "sorts": [{"property": "Timestamp", "direction": "descending"}],
    }
    url  = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    resp = _notion(url, method="POST", body=body)

    signals = []
    for row in resp.get("results", []):
        props = row.get("properties", {})
        signal_title = _text_val(props, "Signal")
        if "buy" not in signal_title.lower():
            continue
        signals.append({
            "page_id":   row["id"],
            "token":     _text_val(props, "Token"),
            "price":     (props.get("Price") or {}).get("number") or 0,
            "score":     (props.get("Score") or {}).get("number") or 0,
            "reason":    _text_val(props, "Reason"),
            "signal":    signal_title,
            "timestamp": ((props.get("Timestamp") or {}).get("date") or {}).get("start", ""),
        })
    return signals


def mark_email_sent(page_id: str) -> None:
    url  = f"https://api.notion.com/v1/pages/{page_id}"
    _notion(url, method="PATCH", body={"properties": {"Email Sent": {"checkbox": True}}})


def log_signal_to_notion(sig: dict) -> str:
    """Write a new signal row and return the created page_id."""
    body = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Signal":     {"title":     [{"text": {"content": sig.get("signal", "Buy Now").title()}}]},
            "Token":      {"rich_text": [{"text": {"content": sig.get("token", "")}}]},
            "Price":      {"number":    sig.get("price", 0)},
            "Score":      {"number":    sig.get("score", 0)},
            "Reason":     {"rich_text": [{"text": {"content": sig.get("reason", "")}}]},
            "Email Sent": {"checkbox":  False},
            "Timestamp":  {"date":      {"start": (sig.get("timestamp") or datetime.now(timezone.utc).isoformat())[:10]}},
        },
    }
    resp = _notion("https://api.notion.com/v1/pages", method="POST", body=body)
    return resp["id"]


# ── Gmail SMTP ────────────────────────────────────────────────────────────────
def _email_html(sig: dict) -> str:
    ts = sig.get("timestamp", "")[:10]
    return f"""
<html><body style="font-family:sans-serif;max-width:520px;margin:auto">
  <h2 style="color:#16a34a">🚨 Memecoin Buy Signal Detected</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:8px;font-weight:bold;background:#f0fdf4">Token</td>
        <td style="padding:8px;background:#f0fdf4">{sig.get("token","—")}</td></tr>
    <tr><td style="padding:8px;font-weight:bold">Price</td>
        <td style="padding:8px">${sig.get("price",0):.8f}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;background:#f0fdf4">Score</td>
        <td style="padding:8px;background:#f0fdf4">{sig.get("score",0)} / 100</td></tr>
    <tr><td style="padding:8px;font-weight:bold">Reason</td>
        <td style="padding:8px">{sig.get("reason","—")}</td></tr>
    <tr><td style="padding:8px;font-weight:bold;background:#f0fdf4">Date</td>
        <td style="padding:8px;background:#f0fdf4">{ts}</td></tr>
  </table>
  <p style="color:#6b7280;font-size:12px;margin-top:16px">
    This alert was sent automatically by memecoin-intel. Not financial advice.
  </p>
</body></html>
"""


def send_email(sig: dict) -> None:
    token = sig.get("token", "?")
    msg   = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Memecoin Buy Signal: {token}"
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = ALERT_RECIPIENT
    msg.attach(MIMEText(_email_html(sig), "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
        smtp.sendmail(GMAIL_SENDER, ALERT_RECIPIENT, msg.as_string())
    print(f"  ✓ email sent for {token}")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(demo: bool = False) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] checking signals…")

    if demo:
        from signals import signal_demo
        sig = signal_demo()
        page_id = log_signal_to_notion(sig)
        sig["page_id"] = page_id
        signals = [sig]
        print(f"  demo signal logged → {page_id}")
    else:
        signals = fetch_unprocessed_signals()

    if not signals:
        print("  no new buy signals — nothing to do")
        return

    for sig in signals:
        token = sig.get("token", "?")
        print(f"  → buy signal: {token}  score={sig.get('score',0)}")
        try:
            send_email(sig)
        except Exception as exc:
            print(f"  ✗ email failed: {exc}", file=sys.stderr)
            continue
        try:
            mark_email_sent(sig["page_id"])
            print(f"  ✓ marked Email Sent in Notion")
        except Exception as exc:
            print(f"  ✗ notion update failed: {exc}", file=sys.stderr)

    print(f"  done — processed {len(signals)} signal(s)")


if __name__ == "__main__":
    run(demo="--demo" in sys.argv)
