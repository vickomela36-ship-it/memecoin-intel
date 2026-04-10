"""
Streamlit dashboard — real-time view of the swing recovery scanner.
Run: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from tracker import Tracker
from config import (
    TAKE_PROFIT_2X,
    TAKE_PROFIT_3X,
    STOP_LOSS_PCT,
    MIN_TOKEN_AGE_HOURS,
    MIN_MARKET_CAP_USD,
    MIN_24H_VOLUME_USD,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_SOL,
    DUMP_THRESHOLD_PCT,
    RECOVERY_BOUNCE_PCT,
    RSI_OVERSOLD_THRESHOLD,
)
from jupiter_client import get_prices

st.set_page_config(page_title="Memecoin Swing Scanner", layout="wide")
st.title("Memecoin Swing Recovery Scanner")

# ── Sidebar: Strategy Parameters ─────────────────────────────────────────
with st.sidebar:
    st.header("Strategy Parameters")
    st.markdown(f"""
    | Parameter | Value |
    |-----------|-------|
    | Min Token Age | {MIN_TOKEN_AGE_HOURS}h |
    | Min Market Cap | ${MIN_MARKET_CAP_USD/1e6:.0f}M |
    | Min 24h Volume | ${MIN_24H_VOLUME_USD/1e3:.0f}K |
    | Dump Threshold | {DUMP_THRESHOLD_PCT}% |
    | Recovery Bounce | {RECOVERY_BOUNCE_PCT}% |
    | RSI Oversold | <{RSI_OVERSOLD_THRESHOLD} |
    | Take Profit | {TAKE_PROFIT_2X}x / {TAKE_PROFIT_3X}x |
    | Stop Loss | {STOP_LOSS_PCT}% |
    | Max Positions | {MAX_OPEN_POSITIONS} |
    | Position Size | {MAX_POSITION_SOL} SOL |
    """)

# ── Load tracker data ────────────────────────────────────────────────────
tracker = Tracker()
summary = tracker.summary()

# ── Top metrics ──────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Open Positions", tracker.open_position_count())
col2.metric("Total Trades", summary["total_trades"])
col3.metric("Win Rate", f"{summary['win_rate']:.0f}%")
col4.metric("Total PnL (SOL)", f"{summary['total_pnl_sol']:+.4f}")
col5.metric("Avg PnL %", f"{summary['avg_pnl_pct']:+.1f}%")

st.divider()

# ── Open Positions ───────────────────────────────────────────────────────
st.subheader("Open Positions")

open_positions = tracker.get_open_positions()
if open_positions:
    # Fetch current prices
    mints = [p.mint_address for p in open_positions]
    prices = get_prices(mints)

    rows = []
    for p in open_positions:
        current = prices.get(p.mint_address, 0)
        pnl = ((current - p.entry_price) / p.entry_price * 100) if p.entry_price > 0 and current > 0 else 0
        tp2_price = p.entry_price * TAKE_PROFIT_2X
        tp3_price = p.entry_price * TAKE_PROFIT_3X
        sl_price = p.entry_price * (1 + STOP_LOSS_PCT / 100)
        rows.append({
            "Token": p.token_name,
            "Entry $": f"{p.entry_price:.8f}",
            "Current $": f"{current:.8f}" if current else "N/A",
            "PnL %": f"{pnl:+.1f}%",
            "Size (SOL)": p.size_sol,
            "TP 2x $": f"{tp2_price:.8f}",
            "TP 3x $": f"{tp3_price:.8f}",
            "SL $": f"{sl_price:.8f}",
            "Confidence": f"{p.confidence:.0%}",
            "Entry Time": p.entry_time[:19],
            "Mint": f"{p.mint_address[:8]}...",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No open positions")

st.divider()

# ── Trade History ────────────────────────────────────────────────────────
st.subheader("Trade History")

closed = tracker.get_closed_positions()
if closed:
    rows = []
    for p in closed:
        rows.append({
            "Token": p.token_name,
            "Entry $": f"{p.entry_price:.8f}",
            "Exit $": f"{p.exit_price:.8f}" if p.exit_price else "N/A",
            "PnL %": f"{p.pnl_pct:+.1f}%" if p.pnl_pct is not None else "N/A",
            "PnL SOL": f"{p.pnl_sol:+.4f}" if p.pnl_sol is not None else "N/A",
            "Exit Reason": p.exit_reason or "N/A",
            "Confidence": f"{p.confidence:.0%}",
            "Entry": p.entry_time[:19],
            "Exit": (p.exit_time[:19] if p.exit_time else "N/A"),
            "Signal": p.signal_reason[:60] + "..." if len(p.signal_reason) > 60 else p.signal_reason,
        })

    df = pd.DataFrame(rows)

    # Color PnL
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Summary chart
    if len(closed) > 1:
        pnl_data = pd.DataFrame({
            "Trade #": range(1, len(closed) + 1),
            "Cumulative PnL (SOL)": pd.Series([p.pnl_sol or 0 for p in closed]).cumsum(),
        })
        st.line_chart(pnl_data, x="Trade #", y="Cumulative PnL (SOL)")
else:
    st.info("No closed trades yet")

st.divider()

# ── Footer ───────────────────────────────────────────────────────────────
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | "
    f"Auto-refresh: re-run the page or use `st.rerun()` in a loop"
)
