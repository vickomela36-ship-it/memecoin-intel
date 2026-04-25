"""
PnL logging — tracks open/closed positions in trades.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

TRADES_FILE = os.path.join(os.path.dirname(__file__), "trades.json")


def _load() -> dict:
    if not os.path.exists(TRADES_FILE):
        return {"open": {}, "closed": []}
    with open(TRADES_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def open_position(mint: str, symbol: str, entry_price: float, size_sol: float = 1.0) -> None:
    data = _load()
    data["open"][mint] = {
        "symbol":      symbol,
        "entry_price": entry_price,
        "size_sol":    size_sol,
        "opened_at":   datetime.now(timezone.utc).isoformat(),
    }
    _save(data)


def close_position(mint: str, exit_price: float, reason: str = "") -> Optional[dict]:
    data  = _load()
    trade = data["open"].pop(mint, None)
    if not trade:
        return None

    pnl_pct = (exit_price - trade["entry_price"]) / trade["entry_price"] * 100
    record  = {
        **trade,
        "mint":        mint,
        "exit_price":  exit_price,
        "pnl_pct":     round(pnl_pct, 2),
        "closed_at":   datetime.now(timezone.utc).isoformat(),
        "close_reason": reason,
    }
    data["closed"].append(record)
    _save(data)
    return record


def get_open_positions() -> dict:
    return _load()["open"]


def get_closed_trades() -> list:
    return _load()["closed"]


def summary() -> dict:
    closed = get_closed_trades()
    if not closed:
        return {"trades": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0}
    wins     = [t for t in closed if t["pnl_pct"] > 0]
    avg_pnl  = sum(t["pnl_pct"] for t in closed) / len(closed)
    return {
        "trades":    len(closed),
        "wins":      len(wins),
        "win_rate":  round(len(wins) / len(closed) * 100, 1),
        "avg_pnl_pct": round(avg_pnl, 2),
    }
