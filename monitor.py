#!/usr/bin/env python3
"""
Hourly monitor: run signals.py, then (via Claude MCP tools) email + log to Notion.

This script is NOT meant to be run directly for email/Notion actions.
It outputs a structured JSON report that the Claude loop prompt consumes.
Run manually to inspect what the current signals look like:
    python3 monitor.py
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
NOTION_DATA_SOURCE_ID = "891878b2-2870-41a3-83c7-17ead22fb7ef"
ALERT_EMAIL = "vickomela36@gmail.com"


def run_signals() -> list[dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "signals.py")],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"signals.py failed: {result.stderr}")
    return json.loads(result.stdout)


def build_email_html(signal: dict) -> str:
    return f"""
<html><body>
<h2>🚨 Memecoin BUY NOW Signal: {signal['token']}</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
  <tr><td><b>Token</b></td><td>{signal['token']} ({signal['chain'].upper()})</td></tr>
  <tr><td><b>Signal Score</b></td><td>{signal['score']}/100</td></tr>
  <tr><td><b>Price (USD)</b></td><td>${signal['price_usd']:.8g}</td></tr>
  <tr><td><b>1h Change</b></td><td>+{signal['price_change_1h']:.1f}%</td></tr>
  <tr><td><b>24h Change</b></td><td>{signal['price_change_24h']:+.1f}%</td></tr>
  <tr><td><b>Volume 24h</b></td><td>${signal['volume_24h_usd']:,.0f}</td></tr>
  <tr><td><b>Liquidity</b></td><td>${signal['liquidity_usd']:,.0f}</td></tr>
  <tr><td><b>Reason</b></td><td>{signal['reason']}</td></tr>
  <tr><td><b>Timestamp</b></td><td>{signal['timestamp']}</td></tr>
</table>
<p><a href="{signal['pair_url']}">View on DexScreener</a></p>
<hr><small>memecoin-intel automated alert</small>
</body></html>
"""


def build_email_text(signal: dict) -> str:
    return (
        f"BUY NOW Signal: {signal['token']} ({signal['chain'].upper()})\n"
        f"Score: {signal['score']}/100\n"
        f"Price: ${signal['price_usd']:.8g}\n"
        f"1h Change: +{signal['price_change_1h']:.1f}%\n"
        f"24h Change: {signal['price_change_24h']:+.1f}%\n"
        f"Volume 24h: ${signal['volume_24h_usd']:,.0f}\n"
        f"Liquidity: ${signal['liquidity_usd']:,.0f}\n"
        f"Reason: {signal['reason']}\n"
        f"Timestamp: {signal['timestamp']}\n"
        f"Chart: {signal['pair_url']}\n"
    )


if __name__ == "__main__":
    signals = run_signals()
    buy_now = [s for s in signals if s.get("signal") == "buy now"]

    report = {
        "total_candidates": len(signals),
        "buy_now_count": len(buy_now),
        "notion_data_source_id": NOTION_DATA_SOURCE_ID,
        "alert_email": ALERT_EMAIL,
        "buy_now_signals": buy_now,
        "all_signals": signals,
    }

    print(json.dumps(report, indent=2))

    if not buy_now:
        print("\nNo BUY NOW signals this run.", file=sys.stderr)
    else:
        print(f"\n{len(buy_now)} BUY NOW signal(s) found:", file=sys.stderr)
        for s in buy_now:
            print(f"  • {s['token']} — score {s['score']}, {s['reason']}", file=sys.stderr)
