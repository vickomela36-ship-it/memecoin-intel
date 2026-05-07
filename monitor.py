"""
Main monitor — run this script every hour (via /loop or cron).
Outputs JSON that the loop agent reads to drive Notion logging and Gmail drafts.

Email sending via SMTP is automatic when GMAIL_USER + GMAIL_APP_PASSWORD env vars are set.
If those vars are absent, the loop agent creates a Gmail draft instead.
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import ALERT_EMAIL, DEDUP_WINDOW_MINUTES, SMTP_PASS, SMTP_USER, STATE_FILE
from signals import get_signals


# ---------------------------------------------------------------------------
# Deduplication state (persisted between runs)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _is_duplicate(state: dict, coin: str) -> bool:
    if coin not in state:
        return False
    last = datetime.fromisoformat(state[coin])
    return (datetime.now(timezone.utc) - last) < timedelta(minutes=DEDUP_WINDOW_MINUTES)


# ---------------------------------------------------------------------------
# Email via SMTP (optional — requires GMAIL_USER + GMAIL_APP_PASSWORD)
# ---------------------------------------------------------------------------

def _send_smtp(signal: dict) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        return False

    coin = signal["coin"]
    price = signal["price"]
    confidence = signal["confidence"]
    change = signal["price_change_1h"]
    volume = signal["volume_24h"]
    url = signal.get("pair_url", "")

    subject = f"Memecoin Buy Signal: {coin}"
    chart_row = f"<tr><td><b>Chart</b></td><td><a href='{url}'>View on DexScreener</a></td></tr>" if url else ""
    html = f"""
<h2>Buy Signal Detected</h2>
<table cellpadding="6" style="border-collapse:collapse">
  <tr><td><b>Coin</b></td><td>{coin}</td></tr>
  <tr><td><b>Price</b></td><td>${price:.8f}</td></tr>
  <tr><td><b>1h Change</b></td><td>+{change:.1f}%</td></tr>
  <tr><td><b>24h Volume</b></td><td>${volume:,.0f}</td></tr>
  <tr><td><b>Confidence</b></td><td>{confidence}/100</td></tr>
  {chart_row}
</table>
<p style="color:#888;font-size:12px">
  Signal time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</p>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(SMTP_USER, SMTP_PASS)
            srv.send_message(msg)
        return True
    except Exception as exc:
        print(f"[SMTP error] {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    signals = get_signals()
    state = _load_state()

    results = []
    for sig in signals:
        if sig.get("signal") != "buy now":
            continue

        coin = sig["coin"]

        if _is_duplicate(state, coin):
            results.append({
                "action": "skip_duplicate",
                "coin": coin,
                "reason": f"Notified within the last {DEDUP_WINDOW_MINUTES} min",
            })
            continue

        email_sent = _send_smtp(sig)
        state[coin] = now

        results.append({
            "action": "notify",
            "coin": coin,
            "signal": "Buy Now",
            "price": sig["price"],
            "confidence": sig["confidence"],
            "volume_24h": sig["volume_24h"],
            "price_change_1h": sig["price_change_1h"],
            "pair_url": sig.get("pair_url", ""),
            "email_sent": email_sent,
            "notes": (
                f"+{sig['price_change_1h']:.1f}% (1h) | "
                f"Vol ${sig['volume_24h']:,.0f} | "
                f"{sig.get('txns_1h', 0)} txns"
            ),
            "timestamp": now,
        })

    _save_state(state)

    output = {
        "checked_at": now,
        "signals_found": len([r for r in results if r["action"] == "notify"]),
        "results": results,
        # Notion database context for the loop agent
        "_notion_data_source": "collection://73b5d85d-86bf-4b6e-b8d7-c43e92bc0391",
        "_alert_email": ALERT_EMAIL,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
