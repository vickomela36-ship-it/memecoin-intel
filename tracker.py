"""PnL logging for memecoin trades."""

import json
import os
from datetime import datetime, timezone

TRADE_LOG = os.path.join(os.path.dirname(__file__), "trades.json")


def _load() -> list:
    if not os.path.exists(TRADE_LOG):
        return []
    with open(TRADE_LOG) as f:
        return json.load(f)


def _save(trades: list) -> None:
    with open(TRADE_LOG, "w") as f:
        json.dump(trades, f, indent=2)


def record_entry(symbol: str, pair_address: str, price: float, amount_usd: float) -> dict:
    trade = {
        "id": f"{pair_address}_{int(datetime.now(timezone.utc).timestamp())}",
        "symbol": symbol,
        "pair_address": pair_address,
        "entry_price": price,
        "amount_usd": amount_usd,
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "exit_price": None,
        "exit_time": None,
        "pnl_usd": None,
        "pnl_pct": None,
    }
    trades = _load()
    trades.append(trade)
    _save(trades)
    return trade


def record_exit(trade_id: str, exit_price: float) -> dict | None:
    trades = _load()
    for t in trades:
        if t["id"] == trade_id and t["exit_price"] is None:
            t["exit_price"] = exit_price
            t["exit_time"] = datetime.now(timezone.utc).isoformat()
            pnl = (exit_price - t["entry_price"]) / t["entry_price"] * t["amount_usd"]
            t["pnl_usd"] = round(pnl, 4)
            t["pnl_pct"] = round((exit_price - t["entry_price"]) / t["entry_price"] * 100, 2)
            _save(trades)
            return t
    return None


def get_open_trades() -> list:
    return [t for t in _load() if t["exit_price"] is None]


def get_total_pnl() -> float:
    return sum(t["pnl_usd"] for t in _load() if t["pnl_usd"] is not None)
