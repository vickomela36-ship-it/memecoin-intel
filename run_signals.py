#!/usr/bin/env python3
"""
Runs the memecoin signal check and prints buy-now signals as JSON to stdout.
Claude reads this output and handles notifications via Gmail/Notion MCP tools.

Usage:
    python run_signals.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WATCH_TOKENS, BUY_SCORE_THRESHOLD
from signals import run as fetch_signals

signals = fetch_signals(WATCH_TOKENS or None, BUY_SCORE_THRESHOLD)

buy_signals = [
    {
        "token":  s.token,
        "signal": s.signal,
        "price":  s.price,
        "score":  s.score,
        "reason": s.reason,
    }
    for s in signals
    if s.signal == "buy now"
]

summary = {
    "total_scanned": len(signals),
    "buy_now_count": len(buy_signals),
    "buy_signals":   buy_signals,
}

print(json.dumps(summary, indent=2))
