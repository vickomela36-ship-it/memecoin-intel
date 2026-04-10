"""
PnL tracker — logs trades, tracks open positions, and computes returns.
Persists to a local JSON file.
"""

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from config import TRADES_LOG_FILE, TAKE_PROFIT_2X, TAKE_PROFIT_3X, STOP_LOSS_PCT


@dataclass
class Position:
    mint_address: str
    token_name: str
    entry_price: float
    entry_time: str
    size_sol: float
    status: str = "OPEN"       # OPEN, CLOSED
    exit_price: float | None = None
    exit_time: str | None = None
    exit_reason: str | None = None
    pnl_pct: float | None = None
    pnl_sol: float | None = None
    confidence: float = 0.0
    signal_reason: str = ""


class Tracker:
    def __init__(self, log_file: str = TRADES_LOG_FILE):
        self.log_file = log_file
        self.positions: list[Position] = []
        self._load()

    def _load(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    data = json.load(f)
                self.positions = [Position(**p) for p in data]
            except (json.JSONDecodeError, TypeError):
                self.positions = []

    def _save(self):
        with open(self.log_file, "w") as f:
            json.dump([asdict(p) for p in self.positions], f, indent=2)

    def open_position(
        self,
        mint_address: str,
        token_name: str,
        entry_price: float,
        size_sol: float,
        confidence: float = 0.0,
        signal_reason: str = "",
    ) -> Position:
        pos = Position(
            mint_address=mint_address,
            token_name=token_name,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc).isoformat(),
            size_sol=size_sol,
            confidence=confidence,
            signal_reason=signal_reason,
        )
        self.positions.append(pos)
        self._save()
        return pos

    def close_position(
        self, mint_address: str, exit_price: float, exit_reason: str
    ) -> Position | None:
        pos = self.get_open_position(mint_address)
        if not pos:
            return None

        pos.status = "CLOSED"
        pos.exit_price = exit_price
        pos.exit_time = datetime.now(timezone.utc).isoformat()
        pos.exit_reason = exit_reason
        pos.pnl_pct = ((exit_price - pos.entry_price) / pos.entry_price) * 100
        pos.pnl_sol = pos.size_sol * (pos.pnl_pct / 100)
        self._save()
        return pos

    def get_open_position(self, mint_address: str) -> Position | None:
        for p in self.positions:
            if p.mint_address == mint_address and p.status == "OPEN":
                return p
        return None

    def get_open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.status == "OPEN"]

    def get_closed_positions(self) -> list[Position]:
        return [p for p in self.positions if p.status == "CLOSED"]

    def has_open_position(self, mint_address: str) -> bool:
        return self.get_open_position(mint_address) is not None

    def open_position_count(self) -> int:
        return len(self.get_open_positions())

    # ── Summary stats ────────────────────────────────────────────────────

    def summary(self) -> dict:
        closed = self.get_closed_positions()
        if not closed:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl_sol": 0.0,
                "avg_pnl_pct": 0.0,
                "best_trade_pct": 0.0,
                "worst_trade_pct": 0.0,
            }

        wins = [p for p in closed if (p.pnl_pct or 0) > 0]
        losses = [p for p in closed if (p.pnl_pct or 0) <= 0]
        pnls = [p.pnl_pct or 0 for p in closed]
        sol_pnls = [p.pnl_sol or 0 for p in closed]

        return {
            "total_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(closed) * 100,
            "total_pnl_sol": sum(sol_pnls),
            "avg_pnl_pct": sum(pnls) / len(pnls),
            "best_trade_pct": max(pnls),
            "worst_trade_pct": min(pnls),
        }
