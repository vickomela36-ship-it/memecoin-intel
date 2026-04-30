#!/usr/bin/env python3
"""
Hourly orchestration entry-point.

This script is executed by the Claude Code hourly loop.  It runs the signal
generator and prints a structured JSON payload that Claude then uses to:
  1. Send an email via Gmail MCP for every "buy now" signal
  2. Log each "buy now" signal to the Notion database

Notion database (data_source_id): c7f3d2af-bf40-4406-9e7f-b998f7123168
Alert email target:               vickomela36@gmail.com
"""

import json
import sys
from signals import generate_signals

NOTION_DATASOURCE_ID = "c7f3d2af-bf40-4406-9e7f-b998f7123168"
ALERT_EMAIL = "vickomela36@gmail.com"


def build_email_body(sig: dict) -> str:
    return f"""\
🚨 Memecoin Buy Signal Detected

Token   : {sig['token']}
Chain   : {sig['chain'].upper()}
Signal  : {sig['signal'].upper()}

Price   : ${sig['price_usd']:.8g}
1h      : {sig['change_1h']:+.2f}%
6h      : {sig['change_6h']:+.2f}%
24h     : {sig['change_24h']:+.2f}%
Volume  : ${sig['volume_24h']:,.0f}
Liq     : ${sig['liquidity_usd']:,.0f}
MCap    : ${sig['market_cap']:,.0f}

Why     : {sig['reason']}
Pair    : {sig['pair_url']}

Scanned : {sig['timestamp']}
"""


if __name__ == "__main__":
    signals = generate_signals()

    buy_signals = [s for s in signals if s["signal"] == "buy now"]

    payload = {
        "notion_datasource_id": NOTION_DATASOURCE_ID,
        "alert_email": ALERT_EMAIL,
        "buy_signals": buy_signals,
        "total_buy_signals": len(buy_signals),
        "actions": [
            {
                "type": "send_email",
                "to": ALERT_EMAIL,
                "subject": f"🚨 Memecoin Buy Signal: {s['token']} ({s['chain'].upper()})",
                "body": build_email_body(s),
                "signal": s,
            }
            for s in buy_signals
        ],
    }

    json.dump(payload, sys.stdout, indent=2)
    print()
