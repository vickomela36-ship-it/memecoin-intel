"""
Hourly signal runner — checks memecoins, emails + logs to Notion on 'buy now'.

Required env vars:
  GMAIL_APP_PASSWORD   Gmail app password (generate at myaccount.google.com/apppasswords)
  NOTION_TOKEN         Notion integration secret (starts with ntn_ or secret_)

Optional env vars:
  ALERT_EMAIL          Override recipient (default: vickomela36@gmail.com)
  GMAIL_SENDER         Override sender address (default: same as ALERT_EMAIL)
  COINGECKO_API_KEY    Use CoinGecko instead of CoinCap

State file ~/.memecoin_last_alert tracks the last alerted coin+price to
prevent duplicate alerts within the same hour.
"""

import json
import os
import smtplib
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import signals as sig
from config import ALERT_EMAIL, NOTION_SIGNALS_DB

GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
GMAIL_SENDER = os.getenv("GMAIL_SENDER", ALERT_EMAIL)

STATE_FILE = Path.home() / ".memecoin_last_alert"
LOG_FILE = Path(__file__).parent / "runner.log"

NOTION_API = "https://api.notion.com/v1"


# ── Logging ──────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── Dedup guard ───────────────────────────────────────────────────────────────

def _already_alerted(symbol: str, price: float) -> bool:
    """Return True if we already sent an alert for this coin at ~this price."""
    if not STATE_FILE.exists():
        return False
    try:
        state = json.loads(STATE_FILE.read_text())
        return state.get("symbol") == symbol and abs(state.get("price", 0) - price) / max(price, 1e-9) < 0.01
    except Exception:
        return False


def _record_alert(symbol: str, price: float) -> None:
    STATE_FILE.write_text(json.dumps({"symbol": symbol, "price": price}))


# ── Email via Gmail SMTP ──────────────────────────────────────────────────────

def send_email(signal: dict) -> bool:
    if not GMAIL_APP_PASSWORD:
        _log("WARN: GMAIL_APP_PASSWORD not set — skipping email")
        return False

    coin = signal["coin"]
    sym = signal["symbol"]
    price = signal["price_usd"]
    c24 = signal["change_24h_pct"]
    c7d = signal.get("change_7d_pct")
    rsi = signal["rsi_proxy"]
    reason = signal["reason"]
    ts = signal["timestamp"]
    vol = signal.get("volume_24h_usd", 0)
    mcap = signal.get("market_cap_usd", 0)

    c7d_str = f"{c7d:+.2f}%" if c7d is not None else "N/A"
    vol_str = f"${vol:,.0f}"
    mcap_str = f"${mcap:,.0f}"

    subject = f"\U0001f6a8 Memecoin Buy Signal: {coin} ({sym})"

    html = f"""
<h2>\U0001f6a8 Memecoin Buy Signal Detected</h2>
<table style="border-collapse:collapse;font-family:monospace;font-size:14px">
  <tr><td style="padding:4px 12px 4px 0;color:#888">Coin</td><td><strong>{coin} ({sym})</strong></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">Price</td><td><strong>${price:.6g}</strong></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">24h Change</td><td style="color:green"><strong>{c24:+.2f}%</strong></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">7d Change</td><td style="color:red"><strong>{c7d_str}</strong></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">RSI Proxy</td><td><strong>{rsi:.1f}</strong> (oversold &lt; 35)</td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">Volume 24h</td><td><strong>{vol_str}</strong></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#888">Market Cap</td><td><strong>{mcap_str}</strong></td></tr>
</table>
<br>
<p><strong>Signal reason:</strong> {reason}</p>
<p style="color:#888;font-size:12px">⚠️ Automated alert — not financial advice. Do your own research.<br>
Generated: {ts} | memecoin-intel</p>
"""
    plain = (
        f"\U0001f6a8 BUY SIGNAL: {coin} ({sym})\n\n"
        f"Price:      ${price:.6g}\n"
        f"24h Change: {c24:+.2f}%\n"
        f"7d Change:  {c7d_str}\n"
        f"RSI Proxy:  {rsi:.1f}\n"
        f"Volume 24h: {vol_str}\n"
        f"Market Cap: {mcap_str}\n\n"
        f"Reason: {reason}\n\n"
        f"Generated: {ts}\n"
        f"⚠️  Not financial advice."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, [ALERT_EMAIL], msg.as_string())
        _log(f"Email sent to {ALERT_EMAIL} for {sym}")
        return True
    except Exception as e:
        _log(f"ERROR sending email: {e}")
        return False


# ── Notion REST API logging ───────────────────────────────────────────────────

def log_to_notion(signal: dict, email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        _log("WARN: NOTION_TOKEN not set — skipping Notion log")
        return False

    sym = signal["symbol"]
    coin = signal["coin"]
    price = signal["price_usd"]
    rsi = signal["rsi_proxy"]
    reason = signal["reason"]
    ts = signal["timestamp"]

    payload = {
        "parent": {"database_id": NOTION_SIGNALS_DB.replace("-", "")},
        "properties": {
            "Signal": {"title": [{"text": {"content": f"BUY NOW - {sym}"}}]},
            "Coin": {"rich_text": [{"text": {"content": coin}}]},
            "Price": {"number": price},
            "Confidence": {"number": rsi},
            "Email Sent": {"checkbox": email_sent},
            "Status": {"select": {"name": "New"}},
            "Notes": {"rich_text": [{"text": {"content": reason}}]},
            "Timestamp": {"date": {"start": ts}},
        },
    }

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{NOTION_API}/pages",
        data=body,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode())
            _log(f"Notion logged: {resp_data.get('url', 'ok')}")
            return True
    except Exception as e:
        _log(f"ERROR logging to Notion: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    test_mode = "--test" in sys.argv
    _log(f"Running signal check (test={test_mode})")

    result = sig._mock_buy_signal() if test_mode else sig.run()
    _log(f"Signal: {result['signal']}")

    if result["signal"] == "error":
        _log(f"ERROR: {result.get('error')}")
        sys.exit(1)

    if result["signal"] == "hold":
        _log(f"Hold — {result.get('coins_checked', 0)} coins checked, no action.")
        sys.exit(0)

    # signal == "buy now"
    sym = result["symbol"]
    price = result["price_usd"]

    if _already_alerted(sym, price) and not test_mode:
        _log(f"Skipping duplicate alert for {sym} @ ${price}")
        sys.exit(0)

    email_ok = send_email(result)
    notion_ok = log_to_notion(result, email_sent=email_ok)
    _record_alert(sym, price)

    _log(f"Done — email={'sent' if email_ok else 'skipped'}, notion={'logged' if notion_ok else 'skipped'}")


if __name__ == "__main__":
    main()
