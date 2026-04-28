"""
Hourly monitor: run signals.py, send email + log to Notion for every 'buy now' hit.

Intended to be invoked by the Claude Code loop skill, which has access to
Gmail MCP (mcp__Gmail__create_draft) and Notion MCP (mcp__Notion__notion-create-pages).

Usage (human-readable prompt for the loop):
  Run python3 /home/user/memecoin-intel/monitor.py and process its JSON output:
  for each result where signal == "buy now":
    1. Send an email to vickomela36@gmail.com via Gmail MCP.
    2. Log the row to Notion data source collection://684a50fb-f6b5-44c6-b1f5-36a3a6f2679e.
  Print a summary of actions taken.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Allow running from any working directory
sys.path.insert(0, os.path.dirname(__file__))

from signals import get_signals

_DEMO_SIGNALS = [
    {
        "Token":          "Bonk",
        "Symbol":         "BONK",
        "Signal":         "buy now",
        "Price USD":      "0.00002341",
        "1h Change %":    "6.8%",
        "6h Change %":    "12.4%",
        "24h Change %":   "31.2%",
        "Volume 24h USD": "$4,523,812",
        "Liquidity USD":  "$987,432",
        "Buy Pressure":   "67.3%",
        "DexScreener URL": "https://dexscreener.com/solana/bonk",
        "Checked At":     datetime.now(timezone.utc).isoformat(),
        "_address":       "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    },
    {
        "Token":          "dogwifhat",
        "Symbol":         "WIF",
        "Signal":         "buy now",
        "Price USD":      "1.832",
        "1h Change %":    "4.1%",
        "6h Change %":    "9.3%",
        "24h Change %":   "18.7%",
        "Volume 24h USD": "$12,088,900",
        "Liquidity USD":  "$3,241,500",
        "Buy Pressure":   "61.0%",
        "DexScreener URL": "https://dexscreener.com/solana/wif",
        "Checked At":     datetime.now(timezone.utc).isoformat(),
        "_address":       "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    },
]


def main(demo: bool = False):
    if demo:
        results = _DEMO_SIGNALS
        print("[monitor] demo mode — using mock signals", file=sys.stderr)
    else:
        results = get_signals()

    buy_now = [r for r in results if r["Signal"] == "buy now"]
    others  = [r for r in results if r["Signal"] != "buy now"]

    output = {
        "total_checked": len(results),
        "buy_now_count": len(buy_now),
        "buy_now":  buy_now,
        "others":   others,
    }
    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main(demo="--demo" in sys.argv)
