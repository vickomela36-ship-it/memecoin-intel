"""
seed_data.py — generates realistic demo trades so the dashboard has data to display.
Run once before opening the dashboard: python seed_data.py
"""

import json
from datetime import datetime, timezone, timedelta
import random

random.seed(42)

TOKENS = [
    ("BONK",  "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
    ("WIF",   "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"),
    ("POPCAT","7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"),
    ("MEW",   "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREkzUofMkWm"),
    ("MYRO",  "HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4"),
    ("SLERF", "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3"),
    ("BOME",  "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82"),
    ("MOTHER","3S8qX1MsMqRbiwKg6cQrikU5TPvsEjHhumGs9sqWmNZt"),
]

now = datetime.now(timezone.utc)

trades = []

# Closed trades — mix of wins and losses
scenarios = [
    # (token_idx, entry_price, exit_price, hours_ago_entry, duration_hours, confidence, signal_notes)
    (0, 0.0000182, 0.0000412, 72, 18, 0.82, "Dumped -38.2% | Bounced 8.1% | VolSpike 3.4x | RSI=22.1 | Buy ratio=68%"),
    (1, 0.00218,   0.00631,   60, 24, 0.75, "Dumped -44.0% | Bounced 6.3% | VolSpike 2.9x | RSI=27.5 | Buy ratio=61%"),
    (2, 0.00041,   0.000328,  48, 10, 0.61, "Dumped -31.5% | Bounced 5.2% | VolSpike 2.1x | RSI=33.0 | Buy ratio=56%"),  # stop loss
    (3, 0.000063,  0.000189,  36, 30, 0.79, "Dumped -52.1% | Bounced 12.4% | VolSpike 4.1x | RSI=18.3 | Buy ratio=71%"),
    (4, 0.00094,   0.00075,   30, 8,  0.55, "Dumped -33.0% | Bounced 5.0% | VolSpike 2.2x | RSI=34.1 | Buy ratio=57%"),  # stop loss
    (5, 0.0000089, 0.0000267, 24, 14, 0.88, "Dumped -61.2% | Bounced 18.7% | VolSpike 5.2x | RSI=16.9 | Buy ratio=74%"),
    (6, 0.00000041,0.00000123,18, 22, 0.71, "Dumped -42.3% | Bounced 9.8% | VolSpike 3.3x | RSI=25.4 | Buy ratio=63%"),
]

for tok_idx, entry, exit_p, hours_ago, dur, conf, reason in scenarios:
    name, mint = TOKENS[tok_idx]
    entry_time = now - timedelta(hours=hours_ago)
    exit_time  = entry_time + timedelta(hours=dur)
    pnl_pct    = (exit_p - entry) / entry * 100
    pnl_sol    = 2.0 * pnl_pct / 100
    pnl_pct    = round(pnl_pct, 2)
    pnl_sol    = round(pnl_sol, 4)

    if pnl_pct >= 200:
        reason_exit = "TAKE_PROFIT_3X"
    elif pnl_pct >= 100:
        reason_exit = "TAKE_PROFIT_2X"
    else:
        reason_exit = "STOP_LOSS"

    trades.append({
        "mint_address": mint,
        "token_name": name,
        "entry_price": entry,
        "entry_time": entry_time.isoformat(),
        "size_sol": 2.0,
        "status": "CLOSED",
        "exit_price": exit_p,
        "exit_time": exit_time.isoformat(),
        "exit_reason": reason_exit,
        "pnl_pct": pnl_pct,
        "pnl_sol": pnl_sol,
        "confidence": conf,
        "signal_reason": reason,
    })

# Two open positions
open_trades = [
    (7, "MOTHER", "3S8qX1MsMqRbiwKg6cQrikU5TPvsEjHhumGs9sqWmNZt",
     0.0000512, 4, 0.73,
     "Dumped -36.8% | Bounced 7.1% | VolSpike 2.8x | RSI=29.4 | Buy ratio=60% | MCap=$4,200,000"),
    (1, "WIF",    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
     0.00341,   2, 0.66,
     "Dumped -30.5% | Bounced 5.8% | VolSpike 2.3x | RSI=32.1 | Buy ratio=58% | MCap=$8,700,000"),
]

for _, name, mint, entry, hours_ago, conf, reason in open_trades:
    entry_time = now - timedelta(hours=hours_ago)
    trades.append({
        "mint_address": mint,
        "token_name": name,
        "entry_price": entry,
        "entry_time": entry_time.isoformat(),
        "size_sol": 2.0,
        "status": "OPEN",
        "exit_price": None,
        "exit_time": None,
        "exit_reason": None,
        "pnl_pct": None,
        "pnl_sol": None,
        "confidence": conf,
        "signal_reason": reason,
    })

with open("trades.json", "w") as f:
    json.dump(trades, f, indent=2)

print(f"Seeded {len(trades)} trades ({len(scenarios)} closed, {len(open_trades)} open)")
