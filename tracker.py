import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

TRACKER_FILE = "pnl_log.json"


@dataclass
class Trade:
    coin: str
    action: str        # "buy" | "sell"
    price_usd: float
    amount_usd: float
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def log_trade(trade: Trade) -> None:
    records = _load()
    records.append(asdict(trade))
    with open(TRACKER_FILE, "w") as fh:
        json.dump(records, fh, indent=2)


def get_pnl_summary() -> dict:
    records = _load()
    invested = sum(r["amount_usd"] for r in records if r["action"] == "buy")
    returned = sum(r["amount_usd"] for r in records if r["action"] == "sell")
    return {"total_invested": invested, "total_returned": returned, "pnl": returned - invested}


def _load() -> list[dict]:
    if not os.path.exists(TRACKER_FILE):
        return []
    with open(TRACKER_FILE) as fh:
        return json.load(fh)
