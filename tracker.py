"""PnL logging — records signal history and optional trade entries to a local CSV."""

import csv
import os
from datetime import datetime, timezone

LOG_FILE = os.getenv("PNL_LOG_FILE", "pnl_log.csv")
_FIELDS = ["timestamp", "coin", "symbol", "signal", "price", "change_24h", "rsi", "confidence", "volume_spike"]


def _ensure_header():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=_FIELDS).writeheader()


def log_result(result: dict):
    _ensure_header()
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coin": result.get("name", result.get("id", "")),
        "symbol": result.get("symbol", ""),
        "signal": result.get("signal", ""),
        "price": result.get("price", ""),
        "change_24h": result.get("change_24h", ""),
        "rsi": result.get("rsi", ""),
        "confidence": result.get("confidence", ""),
        "volume_spike": result.get("volume_spike", ""),
    }
    with open(LOG_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_FIELDS).writerow(row)
