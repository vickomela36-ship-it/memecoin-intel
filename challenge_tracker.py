"""
Challenge tracker — bankroll math for turning a small stake into a target
over a fixed number of days via compounded high-conviction plays.

Pure math + JSON persistence. No Streamlit dependency (thread-safe).
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

CHALLENGE_FILE = "challenge.json"


# ═══════════════════════════════════════════════════════════════════════════════
# Position sizing rules per play tier
#
# Fractions are % of CURRENT bankroll. Stops are hard exits.
# The ladder is: sell 50% at TP1, 25% at TP2, let 25% ride (moonbag).
# ═══════════════════════════════════════════════════════════════════════════════

SIZING_RULES = {
    "A": {
        "label": "A-grade recovery",
        "fraction": 0.40, "stop_pct": 15,
        "tp1_mult": 1.6, "tp2_mult": 2.5,
        "why": "Highest win-rate setup. Big size, tight stop, modest targets.",
    },
    "B": {
        "label": "B-grade recovery",
        "fraction": 0.25, "stop_pct": 18,
        "tp1_mult": 1.8, "tp2_mult": 3.0,
        "why": "Solid setup. Moderate size.",
    },
    "5x POTENTIAL": {
        "label": "5x degen play",
        "fraction": 0.20, "stop_pct": 25,
        "tp1_mult": 2.0, "tp2_mult": 5.0,
        "why": "High risk. Wider stop for volatility, bigger targets.",
    },
    "10x RUNNER": {
        "label": "10x degen play",
        "fraction": 0.12, "stop_pct": 30,
        "tp1_mult": 3.0, "tp2_mult": 10.0,
        "why": "Very high risk. Small size, huge asymmetry.",
    },
    "100x MOONSHOT": {
        "label": "100x moonshot",
        "fraction": 0.07, "stop_pct": 40,
        "tp1_mult": 5.0, "tp2_mult": 20.0,
        "why": "Lottery ticket. Never size beyond 7% — most go to zero.",
    },
}

DEFAULT_RULE = {
    "label": "Unrated play",
    "fraction": 0.10, "stop_pct": 20,
    "tp1_mult": 2.0, "tp2_mult": 4.0,
    "why": "No grade — default conservative sizing.",
}


@dataclass
class ChallengeState:
    start_bankroll: float = 100.0
    target: float = 10_000.0
    days: int = 7
    current_bankroll: float = 100.0
    started_at: str = ""
    trades: list = field(default_factory=list)
    active: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════════════

def load_challenge():
    if os.path.exists(CHALLENGE_FILE):
        try:
            with open(CHALLENGE_FILE, "r") as f:
                data = json.load(f)
            return ChallengeState(**data)
        except (json.JSONDecodeError, TypeError, OSError):
            pass
    return ChallengeState()


def save_challenge(state):
    try:
        with open(CHALLENGE_FILE, "w") as f:
            json.dump(asdict(state), f, indent=2)
    except OSError:
        pass


def start_challenge(start_bankroll=100.0, target=10_000.0, days=7):
    state = ChallengeState(
        start_bankroll=start_bankroll,
        target=target,
        days=days,
        current_bankroll=start_bankroll,
        started_at=datetime.now(timezone.utc).isoformat(),
        trades=[],
        active=True,
    )
    save_challenge(state)
    return state


def log_challenge_trade(state, symbol, entry_usd, exit_usd, note=""):
    """Record a completed trade: money in, money out. Updates bankroll."""
    pnl = exit_usd - entry_usd
    state.current_bankroll = max(0.0, state.current_bankroll + pnl)
    state.trades.append({
        "symbol": symbol,
        "entry_usd": round(entry_usd, 2),
        "exit_usd": round(exit_usd, 2),
        "pnl": round(pnl, 2),
        "multiple": round(exit_usd / entry_usd, 2) if entry_usd > 0 else 0,
        "bankroll_after": round(state.current_bankroll, 2),
        "note": note,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    save_challenge(state)
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# Pace math
# ═══════════════════════════════════════════════════════════════════════════════

def days_elapsed(state):
    if not state.started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(state.started_at)
        delta = datetime.now(timezone.utc) - started
        return max(0.0, delta.total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 0.0


def required_daily_multiple(current, target, days_left):
    """The compounded multiple needed each remaining day."""
    if current <= 0 or days_left <= 0:
        return float("inf")
    if current >= target:
        return 1.0
    return (target / current) ** (1.0 / days_left)


def pace_bankroll(state, day):
    """What the bankroll SHOULD be at a given day to stay on pace."""
    total_mult = state.target / state.start_bankroll
    return state.start_bankroll * (total_mult ** (min(day, state.days) / state.days))


def pace_status(state):
    """Returns (status, on_pace_bankroll, required_mult_per_day)."""
    elapsed = days_elapsed(state)
    days_left = max(0.01, state.days - elapsed)
    on_pace = pace_bankroll(state, elapsed)
    req = required_daily_multiple(state.current_bankroll, state.target, days_left)

    if state.current_bankroll >= state.target:
        status = "TARGET HIT"
    elif state.current_bankroll >= on_pace:
        status = "AHEAD OF PACE"
    elif state.current_bankroll >= on_pace * 0.6:
        status = "BEHIND PACE"
    else:
        status = "CRITICAL"
    return status, on_pace, req


# ═══════════════════════════════════════════════════════════════════════════════
# Position sizing
# ═══════════════════════════════════════════════════════════════════════════════

def get_sizing_rule(tier_or_grade):
    return SIZING_RULES.get(tier_or_grade, DEFAULT_RULE)


def position_plan(bankroll, tier_or_grade, price_usd=0.0):
    """Build a concrete dollar trade plan for a play at the current bankroll."""
    rule = get_sizing_rule(tier_or_grade)
    size_usd = bankroll * rule["fraction"]
    stop_loss_usd = size_usd * (rule["stop_pct"] / 100.0)

    # Expected proceeds if ladder plays out fully:
    # 50% out at tp1, 25% out at tp2, 25% rides (valued at tp2 conservatively)
    ladder_proceeds = (
        size_usd * 0.50 * rule["tp1_mult"]
        + size_usd * 0.25 * rule["tp2_mult"]
    )

    plan = {
        "label": rule["label"],
        "fraction_pct": rule["fraction"] * 100,
        "size_usd": round(size_usd, 2),
        "stop_pct": rule["stop_pct"],
        "max_loss_usd": round(stop_loss_usd, 2),
        "tp1_mult": rule["tp1_mult"],
        "tp2_mult": rule["tp2_mult"],
        "tp1_sell": "Sell 50%",
        "tp2_sell": "Sell 25%",
        "moonbag": "Let 25% ride",
        "banked_if_ladder_hits": round(ladder_proceeds, 2),
        "why": rule["why"],
    }
    if price_usd > 0:
        plan["stop_price"] = price_usd * (1 - rule["stop_pct"] / 100.0)
        plan["tp1_price"] = price_usd * rule["tp1_mult"]
        plan["tp2_price"] = price_usd * rule["tp2_mult"]
    return plan


def daily_play_plan(bankroll, req_mult):
    """Suggest a day's play structure to hit the required multiple.

    Strategy: one core A/B recovery play + one or two degen shots.
    Returns a list of dicts describing suggested allocations.
    """
    plays = [
        {**position_plan(bankroll, "A"), "slot": "Core play (A/B grade)"},
        {**position_plan(bankroll, "5x POTENTIAL"), "slot": "Degen shot #1"},
        {**position_plan(bankroll, "10x RUNNER"), "slot": "Degen shot #2 (optional)"},
    ]
    reserve_pct = 100 - sum(p["fraction_pct"] for p in plays)
    return plays, max(0.0, reserve_pct)
