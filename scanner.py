"""
Scanner — the main loop that ties everything together.

1. Fetches trending high-volume Solana tokens
2. Filters by age (>24h) and market cap (>$2M)
3. Runs dump detection + recovery signal checks
4. Logs signals and manages positions
5. Monitors open positions for exit signals
"""

import time
import sys
from datetime import datetime, timezone

from config import (
    SCAN_INTERVAL_SECONDS,
    MAX_POSITION_SOL,
    MAX_OPEN_POSITIONS,
    TAKE_PROFIT_2X,
    TAKE_PROFIT_3X,
    STOP_LOSS_PCT,
    MIN_TOKEN_AGE_HOURS,
    MIN_MARKET_CAP_USD,
    MIN_24H_VOLUME_USD,
)
from jupiter_client import (
    get_prices,
    get_ohlcv,
    get_trade_volume_breakdown,
    get_trending_tokens,
    get_token_overview,
)
from helius_client import get_token_age_hours, get_market_cap
from signals import check_recovery_entry, check_exit_signals, Signal
from tracker import Tracker


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def scan_for_entries(tracker: Tracker) -> list[Signal]:
    """Scan trending tokens for recovery swing entries."""
    signals_found = []

    if tracker.open_position_count() >= MAX_OPEN_POSITIONS:
        log(f"Max positions ({MAX_OPEN_POSITIONS}) reached — skipping entry scan")
        return signals_found

    # Step 1: Get trending high-volume tokens
    log("Fetching trending tokens...")
    trending = get_trending_tokens(sort_by="volume24hUSD", limit=50)

    if not trending:
        log("No trending tokens found")
        return signals_found

    log(f"Found {len(trending)} trending tokens — filtering...")

    for token in trending:
        mint = token.get("address")
        name = token.get("symbol", token.get("name", "???"))

        if not mint:
            continue

        # Skip if we already have an open position
        if tracker.has_open_position(mint):
            continue

        # Step 2: Quick filter — get overview data first (cheap call)
        overview = get_token_overview(mint)
        if not overview:
            continue

        volume_24h = overview.get("v24hUSD", 0) or 0
        if volume_24h < MIN_24H_VOLUME_USD:
            continue

        price_usd = overview.get("price", 0) or 0
        if price_usd <= 0:
            continue

        mc = overview.get("mc", 0) or overview.get("realMc", 0) or 0
        if mc < MIN_MARKET_CAP_USD:
            # Fallback: compute from supply
            mc_computed = get_market_cap(mint, price_usd)
            if mc_computed is None or mc_computed < MIN_MARKET_CAP_USD:
                continue
            mc = mc_computed

        # Step 3: Check token age
        age = get_token_age_hours(mint)
        if age is None or age < MIN_TOKEN_AGE_HOURS:
            continue

        log(f"  Analyzing {name} ({mint[:8]}...) — MCap=${mc:,.0f} Vol=${volume_24h:,.0f} Age={age:.0f}h")

        # Step 4: Get OHLCV candles for dump detection (15m candles, 6h = 24 candles)
        candles = get_ohlcv(mint, interval="15m", limit=24)
        if len(candles) < 8:
            continue

        # Step 5: Get buy/sell volume breakdown
        vol_breakdown = get_trade_volume_breakdown(mint)
        buy_ratio = vol_breakdown["buy_ratio"] if vol_breakdown else 0.5

        # Step 6: Check for recovery entry signal
        signal = check_recovery_entry(
            mint_address=mint,
            token_name=name,
            candles=candles,
            buy_volume_ratio=buy_ratio,
            market_cap=mc,
            token_age_hours=age,
            volume_24h=volume_24h,
        )

        if signal:
            signals_found.append(signal)
            log(f"  >> SIGNAL: {signal.signal_type} for {name} @ ${signal.price:.6f} "
                f"(confidence={signal.confidence:.0%})")
            log(f"     {signal.reason}")

        time.sleep(0.3)  # Rate limiting

    return signals_found


def monitor_open_positions(tracker: Tracker):
    """Check open positions for exit signals (TP or SL)."""
    open_positions = tracker.get_open_positions()
    if not open_positions:
        return

    mints = [p.mint_address for p in open_positions]
    prices = get_prices(mints)

    for pos in open_positions:
        current_price = prices.get(pos.mint_address)
        if current_price is None:
            continue

        pnl = ((current_price - pos.entry_price) / pos.entry_price) * 100

        exit_signal = check_exit_signals(
            entry_price=pos.entry_price,
            current_price=current_price,
            take_profit_2x=TAKE_PROFIT_2X,
            take_profit_3x=TAKE_PROFIT_3X,
            stop_loss_pct=STOP_LOSS_PCT,
        )

        if exit_signal:
            closed = tracker.close_position(pos.mint_address, current_price, exit_signal)
            if closed:
                emoji = "WIN" if (closed.pnl_pct or 0) > 0 else "LOSS"
                log(f"  CLOSED {pos.token_name}: {exit_signal} @ ${current_price:.6f} "
                    f"PnL={closed.pnl_pct:+.1f}% ({closed.pnl_sol:+.4f} SOL) [{emoji}]")
        else:
            log(f"  {pos.token_name}: ${current_price:.6f} PnL={pnl:+.1f}%")


def process_signals(signals: list[Signal], tracker: Tracker):
    """Log new entry signals as positions (paper trading)."""
    for signal in signals:
        if tracker.open_position_count() >= MAX_OPEN_POSITIONS:
            break
        if tracker.has_open_position(signal.mint_address):
            continue

        pos = tracker.open_position(
            mint_address=signal.mint_address,
            token_name=signal.token_name,
            entry_price=signal.price,
            size_sol=MAX_POSITION_SOL,
            confidence=signal.confidence,
            signal_reason=signal.reason,
        )
        log(f"  OPENED position: {pos.token_name} @ ${pos.entry_price:.6f} "
            f"({pos.size_sol} SOL, confidence={pos.confidence:.0%})")


def run_scanner():
    """Main scanner loop."""
    tracker = Tracker()

    log("=" * 60)
    log("Memecoin Swing Recovery Scanner")
    log(f"Strategy: Catch 2x-3x recoveries after dumps")
    log(f"Filters: Age>{MIN_TOKEN_AGE_HOURS}h | MCap>${MIN_MARKET_CAP_USD/1e6:.0f}M | Vol>{MIN_24H_VOLUME_USD/1e3:.0f}K")
    log(f"Targets: TP={TAKE_PROFIT_2X}x/{TAKE_PROFIT_3X}x | SL={STOP_LOSS_PCT}%")
    log(f"Max positions: {MAX_OPEN_POSITIONS} @ {MAX_POSITION_SOL} SOL each")
    log("=" * 60)

    while True:
        try:
            log("--- Scan cycle start ---")

            # Monitor existing positions
            log("Checking open positions...")
            monitor_open_positions(tracker)

            # Scan for new entries
            signals = scan_for_entries(tracker)
            if signals:
                log(f"Found {len(signals)} signal(s) — processing...")
                process_signals(signals, tracker)
            else:
                log("No signals this cycle")

            # Print summary
            summary = tracker.summary()
            open_count = tracker.open_position_count()
            log(f"Open: {open_count} | Closed: {summary['total_trades']} | "
                f"Win rate: {summary['win_rate']:.0f}% | Total PnL: {summary['total_pnl_sol']:+.4f} SOL")
            log(f"--- Next scan in {SCAN_INTERVAL_SECONDS}s ---\n")

            time.sleep(SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            log("Scanner stopped by user")
            break
        except Exception as e:
            log(f"Error in scan cycle: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_scanner()
