"""PnL logging — records entry/exit prices and calculates realized PnL."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(os.getenv("PNL_LOG_FILE", "pnl_log.json"))


def _load() -> list[dict]:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []


def _save(records: list[dict]) -> None:
    LOG_FILE.write_text(json.dumps(records, indent=2))


def record_entry(coin: str, symbol: str, price: float, amount_usd: float) -> None:
    records = _load()
    records.append({
        "id":         len(records) + 1,
        "coin":       coin,
        "symbol":     symbol,
        "action":     "buy",
        "price_usd":  price,
        "amount_usd": amount_usd,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "pnl_usd":    None,
    })
    _save(records)


def record_exit(coin: str, exit_price: float) -> float | None:
    records = _load()
    entry = next(
        (r for r in reversed(records) if r["coin"] == coin and r["action"] == "buy"),
        None,
    )
    if not entry:
        return None

    tokens = entry["amount_usd"] / entry["price_usd"]
    pnl = (exit_price - entry["price_usd"]) * tokens

    records.append({
        "id":         len(records) + 1,
        "coin":       coin,
        "symbol":     entry["symbol"],
        "action":     "sell",
        "price_usd":  exit_price,
        "amount_usd": exit_price * tokens,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "pnl_usd":    round(pnl, 4),
    })
    _save(records)
    return pnl


def get_summary() -> dict:
    records = _load()
    realized = sum(r["pnl_usd"] for r in records if r.get("pnl_usd") is not None)
    return {"total_trades": len(records), "realized_pnl_usd": round(realized, 4)}
