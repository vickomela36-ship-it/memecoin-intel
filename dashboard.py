"""
Visual dashboard — swing recovery scanner.
Run: streamlit run dashboard.py
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timezone, timedelta

from tracker import Tracker, Position
from config import (
    TAKE_PROFIT_2X, TAKE_PROFIT_3X, STOP_LOSS_PCT,
    MIN_TOKEN_AGE_HOURS, MIN_MARKET_CAP_USD, MIN_24H_VOLUME_USD,
    MAX_OPEN_POSITIONS, MAX_POSITION_SOL,
    DUMP_THRESHOLD_PCT, RECOVERY_BOUNCE_PCT, RSI_OVERSOLD_THRESHOLD,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Memecoin Swing Scanner",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme colours ─────────────────────────────────────────────────────────────
GREEN  = "#00e676"
RED    = "#ff1744"
YELLOW = "#ffd600"
BLUE   = "#2979ff"
BG     = "#0e1117"
CARD   = "#1a1d23"

st.markdown("""
<style>
  .metric-card {
    background: #1a1d23;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 6px;
  }
  .metric-label { color: #8b95a5; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
  .metric-value { color: #ffffff; font-size: 28px; font-weight: 700; margin-top: 4px; }
  .metric-delta { font-size: 13px; margin-top: 2px; }
  .positive { color: #00e676; }
  .negative { color: #ff1744; }
  .neutral  { color: #ffd600; }
  .signal-buy  { background:#003300; border-left:4px solid #00e676; padding:12px 16px; border-radius:6px; margin:4px 0; }
  .signal-sell { background:#330000; border-left:4px solid #ff1744; padding:12px 16px; border-radius:6px; margin:4px 0; }
  .signal-watch{ background:#1a1400; border-left:4px solid #ffd600; padding:12px 16px; border-radius:6px; margin:4px 0; }
  .badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
  .badge-win  { background:#003300; color:#00e676; }
  .badge-loss { background:#330000; color:#ff1744; }
  .badge-open { background:#001a33; color:#2979ff; }
  section[data-testid="stSidebar"] { background:#111418; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _pct_color(v: float) -> str:
    if v > 0:  return "positive"
    if v < 0:  return "negative"
    return "neutral"

def _fmt_price(p: float) -> str:
    if p == 0: return "N/A"
    if p < 0.000001: return f"${p:.10f}"
    if p < 0.001:    return f"${p:.8f}"
    if p < 1:        return f"${p:.6f}"
    return f"${p:,.4f}"

def _hours_since(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        diff = datetime.now(timezone.utc) - dt
        h = diff.total_seconds() / 3600
        if h < 1:   return f"{int(diff.total_seconds()/60)}m ago"
        if h < 24:  return f"{h:.1f}h ago"
        return f"{h/24:.1f}d ago"
    except Exception:
        return "?"

def _live_price(mint: str) -> float | None:
    try:
        from jupiter_client import get_prices
        p = get_prices([mint])
        return p.get(mint)
    except Exception:
        return None

def _load_signals_log() -> list[dict]:
    """Load any signals logged by the scanner (signals_log.json)."""
    try:
        with open("signals_log.json") as f:
            return json.load(f)
    except Exception:
        return []


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Strategy Config")
    auto_refresh = st.toggle("Auto-refresh (30s)", value=False)
    st.divider()

    st.markdown("**Entry filters**")
    st.markdown(f"""
    - Min age: **{MIN_TOKEN_AGE_HOURS}h**
    - Min market cap: **${MIN_MARKET_CAP_USD/1e6:.0f}M**
    - Min 24h vol: **${MIN_24H_VOLUME_USD/1e3:.0f}K**
    """)
    st.markdown("**Dump detection**")
    st.markdown(f"""
    - Dump ≥ **{abs(DUMP_THRESHOLD_PCT)}%** from high
    - Volume spike ≥ **2x** normal
    """)
    st.markdown("**Entry conditions**")
    st.markdown(f"""
    - Bounce ≥ **{RECOVERY_BOUNCE_PCT}%** off bottom
    - RSI < **{RSI_OVERSOLD_THRESHOLD}** (oversold)
    - Buy vol > **55%** of total
    """)
    st.divider()
    st.markdown("**Exit levels**")
    col_a, col_b = st.columns(2)
    col_a.success(f"TP1  {TAKE_PROFIT_2X}x")
    col_a.success(f"TP2  {TAKE_PROFIT_3X}x")
    col_b.error(f"SL  {STOP_LOSS_PCT}%")
    st.divider()
    st.caption(f"Max {MAX_OPEN_POSITIONS} positions @ {MAX_POSITION_SOL} SOL each")


# ── Load data ─────────────────────────────────────────────────────────────────
tracker  = Tracker()
summary  = tracker.summary()
open_pos = tracker.get_open_positions()
closed   = tracker.get_closed_positions()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# Memecoin Swing Recovery Scanner")
st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)

def kpi(col, label, value, cls=""):
    col.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value {cls}">{value}</div>
    </div>""", unsafe_allow_html=True)

total_pnl_sol = summary["total_pnl_sol"]
kpi(k1, "Open Positions",  f"{tracker.open_position_count()} / {MAX_OPEN_POSITIONS}")
kpi(k2, "Total Trades",    str(summary["total_trades"]))
kpi(k3, "Win Rate",        f"{summary['win_rate']:.0f}%",
    "positive" if summary["win_rate"] >= 50 else "negative")
kpi(k4, "Total PnL (SOL)", f"{total_pnl_sol:+.3f}",
    "positive" if total_pnl_sol >= 0 else "negative")
kpi(k5, "Best Trade",      f"{summary['best_trade_pct']:+.0f}%", "positive")
kpi(k6, "Worst Trade",     f"{summary['worst_trade_pct']:+.0f}%", "negative")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — OPEN POSITIONS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("## Open Positions")

if not open_pos:
    st.info("No open positions — scanner is looking for setups.")
else:
    for pos in open_pos:
        live = _live_price(pos.mint_address)
        current = live if live else pos.entry_price
        pnl_pct = (current - pos.entry_price) / pos.entry_price * 100

        tp2 = pos.entry_price * TAKE_PROFIT_2X
        tp3 = pos.entry_price * TAKE_PROFIT_3X
        sl  = pos.entry_price * (1 + STOP_LOSS_PCT / 100)

        # Progress toward TP/SL
        total_range = tp2 - sl
        progress_val = min(max((current - sl) / total_range, 0.0), 1.0) if total_range > 0 else 0.5

        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 4])

            c1.markdown(f"### {pos.token_name}")
            c1.caption(f"Entered {_hours_since(pos.entry_time)}")

            c2.metric("Entry", _fmt_price(pos.entry_price))
            c3.metric("Current", _fmt_price(current),
                      delta=f"{pnl_pct:+.1f}%",
                      delta_color="normal" if pnl_pct >= 0 else "inverse")
            c4.metric("Size", f"{pos.size_sol} SOL")

            with c5:
                st.markdown("**Price levels**")
                # Gauge chart showing SL / current / TP2 / TP3
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=pnl_pct,
                    number={"suffix": "%", "font": {"color": GREEN if pnl_pct >= 0 else RED}},
                    gauge={
                        "axis": {"range": [STOP_LOSS_PCT - 5, 220], "tickcolor": "#8b95a5"},
                        "bar": {"color": GREEN if pnl_pct >= 0 else RED},
                        "bgcolor": CARD,
                        "bordercolor": "#2a2d33",
                        "steps": [
                            {"range": [STOP_LOSS_PCT - 5, STOP_LOSS_PCT], "color": "#330000"},
                            {"range": [STOP_LOSS_PCT, 0],  "color": "#1a0a00"},
                            {"range": [0, 100],   "color": "#001a00"},
                            {"range": [100, 200], "color": "#003300"},
                            {"range": [200, 220], "color": "#004d00"},
                        ],
                        "threshold": {
                            "line": {"color": YELLOW, "width": 3},
                            "thickness": 0.8,
                            "value": pnl_pct,
                        },
                    },
                    title={"text": "PnL %", "font": {"color": "#8b95a5", "size": 12}},
                ))
                fig_gauge.update_layout(
                    height=130, margin=dict(l=10, r=10, t=20, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", font_color="#ffffff",
                )
                st.plotly_chart(fig_gauge, width="stretch", key=f"gauge_{pos.mint_address}")

            # Level bar: SL ──── Entry ──── TP2 ──── TP3
            levels_cols = st.columns(4)
            sl_cls  = "negative" if current <= sl else ""
            tp2_cls = "positive" if current >= tp2 else "neutral"
            tp3_cls = "positive" if current >= tp3 else "neutral"

            levels_cols[0].markdown(
                f"<span class='badge badge-loss'>SL {STOP_LOSS_PCT}%</span>&nbsp;"
                f"<b class='{sl_cls}'>{_fmt_price(sl)}</b>", unsafe_allow_html=True)
            levels_cols[1].markdown(
                f"<span class='badge badge-open'>ENTRY</span>&nbsp;"
                f"<b>{_fmt_price(pos.entry_price)}</b>", unsafe_allow_html=True)
            levels_cols[2].markdown(
                f"<span class='badge badge-win'>TP1 2x</span>&nbsp;"
                f"<b class='{tp2_cls}'>{_fmt_price(tp2)}</b>", unsafe_allow_html=True)
            levels_cols[3].markdown(
                f"<span class='badge badge-win'>TP2 3x</span>&nbsp;"
                f"<b class='{tp3_cls}'>{_fmt_price(tp3)}</b>", unsafe_allow_html=True)

            # Progress bar
            st.progress(progress_val,
                text=f"SL {'◀' if current <= sl else '   '} {_fmt_price(sl)} ──── "
                     f"{_fmt_price(pos.entry_price)} ──── "
                     f"{_fmt_price(tp2)} {'◀' if current >= tp2 else '   '} TP1")

            # Signal breakdown
            with st.expander("Signal details"):
                st.caption(pos.signal_reason)
                conf_pct = int(pos.confidence * 100)
                st.markdown(f"**Confidence: {conf_pct}%**")
                st.progress(pos.confidence, text=f"{conf_pct}% confidence")

            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — EARNINGS TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("## Earnings Tracker")

if not closed:
    st.info("No completed trades yet. Run the scanner to start building history.")
else:
    tab1, tab2, tab3 = st.tabs(["Cumulative PnL", "Trade Breakdown", "Win/Loss Analysis"])

    # ── Cumulative PnL chart ─────────────────────────────────────────────────
    with tab1:
        pnl_values = [p.pnl_sol or 0 for p in closed]
        cum_pnl    = []
        running    = 0.0
        for v in pnl_values:
            running += v
            cum_pnl.append(round(running, 5))

        trade_labels = [f"{p.token_name} ({p.exit_reason})" for p in closed]
        colors_line  = [GREEN if v >= 0 else RED for v in cum_pnl]

        fig_pnl = go.Figure()

        # Shaded area
        fig_pnl.add_trace(go.Scatter(
            x=list(range(1, len(closed) + 1)),
            y=cum_pnl,
            fill="tozeroy",
            fillcolor="rgba(0,230,118,0.08)" if cum_pnl[-1] >= 0 else "rgba(255,23,68,0.08)",
            line=dict(color=GREEN if cum_pnl[-1] >= 0 else RED, width=2.5),
            mode="lines+markers",
            marker=dict(
                size=9,
                color=[GREEN if v >= 0 else RED for v in pnl_values],
                line=dict(color="#0e1117", width=2),
            ),
            text=trade_labels,
            hovertemplate="<b>Trade #%{x}</b><br>%{text}<br>Cumulative PnL: %{y:.4f} SOL<extra></extra>",
            name="Cumulative PnL",
        ))

        # Zero line
        fig_pnl.add_hline(y=0, line_dash="dash", line_color="#444", line_width=1)

        # Annotate last point
        fig_pnl.add_annotation(
            x=len(closed), y=cum_pnl[-1],
            text=f"{cum_pnl[-1]:+.4f} SOL",
            showarrow=True, arrowhead=2,
            font=dict(color=GREEN if cum_pnl[-1] >= 0 else RED, size=13),
            bgcolor=CARD, bordercolor=GREEN if cum_pnl[-1] >= 0 else RED,
        )

        fig_pnl.update_layout(
            title="Cumulative PnL (SOL)",
            xaxis_title="Trade #",
            yaxis_title="SOL",
            paper_bgcolor=BG, plot_bgcolor=BG,
            font_color="#ffffff",
            height=380,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="#1f2229", tickcolor="#444"),
            yaxis=dict(gridcolor="#1f2229", tickcolor="#444", zeroline=False),
            hovermode="x unified",
        )
        st.plotly_chart(fig_pnl, width="stretch")

        # Per-trade bars
        fig_bars = go.Figure(go.Bar(
            x=list(range(1, len(closed) + 1)),
            y=[p.pnl_pct or 0 for p in closed],
            marker_color=[GREEN if (p.pnl_pct or 0) >= 0 else RED for p in closed],
            text=[f"{p.token_name}" for p in closed],
            textposition="outside",
            hovertemplate="<b>%{text}</b><br>PnL: %{y:+.1f}%<extra></extra>",
        ))
        fig_bars.add_hline(y=0, line_dash="dash", line_color="#444", line_width=1)
        fig_bars.add_hline(y=100, line_dash="dot", line_color=GREEN, line_width=1,
                           annotation_text="2x TP", annotation_font_color=GREEN)
        fig_bars.add_hline(y=200, line_dash="dot", line_color=BLUE, line_width=1,
                           annotation_text="3x TP", annotation_font_color=BLUE)
        fig_bars.add_hline(y=STOP_LOSS_PCT, line_dash="dot", line_color=RED, line_width=1,
                           annotation_text="Stop Loss", annotation_font_color=RED)
        fig_bars.update_layout(
            title="Per-Trade PnL %",
            xaxis_title="Trade #", yaxis_title="PnL %",
            paper_bgcolor=BG, plot_bgcolor=BG, font_color="#ffffff",
            height=300, margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="#1f2229"),
            yaxis=dict(gridcolor="#1f2229"),
        )
        st.plotly_chart(fig_bars, width="stretch")

    # ── Trade breakdown table ────────────────────────────────────────────────
    with tab2:
        rows = []
        for i, p in enumerate(closed, 1):
            pnl_pct = p.pnl_pct or 0
            badge = "WIN" if pnl_pct > 0 else "LOSS"
            rows.append({
                "#":          i,
                "Token":      p.token_name,
                "Entry":      _fmt_price(p.entry_price),
                "Exit":       _fmt_price(p.exit_price or 0),
                "PnL %":      f"{pnl_pct:+.1f}%",
                "PnL SOL":    f"{p.pnl_sol:+.4f}" if p.pnl_sol else "N/A",
                "Result":     badge,
                "Reason":     p.exit_reason or "N/A",
                "Confidence": f"{p.confidence:.0%}",
                "Held":       _hours_since(p.entry_time),
            })

        df = pd.DataFrame(rows)

        def color_row(row):
            color = "color: #00e676" if row["Result"] == "WIN" else "color: #ff1744"
            return [color if col in ("PnL %", "PnL SOL", "Result") else "" for col in row.index]

        st.dataframe(
            df.style.apply(color_row, axis=1),
            width="stretch",
            hide_index=True,
            height=min(400, 50 + len(rows) * 38),
        )

    # ── Win/loss analysis ────────────────────────────────────────────────────
    with tab3:
        wins   = [p for p in closed if (p.pnl_pct or 0) > 0]
        losses = [p for p in closed if (p.pnl_pct or 0) <= 0]

        col_w, col_l, col_r = st.columns(3)

        # Donut
        fig_donut = go.Figure(go.Pie(
            labels=["Wins", "Losses"],
            values=[len(wins), len(losses)],
            hole=0.6,
            marker_colors=[GREEN, RED],
            textinfo="label+percent",
            hovertemplate="%{label}: %{value} trades (%{percent})<extra></extra>",
        ))
        fig_donut.add_annotation(
            text=f"{summary['win_rate']:.0f}%<br>Win rate",
            x=0.5, y=0.5, font_size=16, showarrow=False,
            font=dict(color="#ffffff"),
        )
        fig_donut.update_layout(
            paper_bgcolor=BG, font_color="#ffffff",
            height=250, margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
        )
        col_w.plotly_chart(fig_donut, width="stretch")

        # Exit reason breakdown
        reason_counts: dict[str, int] = {}
        for p in closed:
            r = p.exit_reason or "UNKNOWN"
            reason_counts[r] = reason_counts.get(r, 0) + 1

        fig_reasons = go.Figure(go.Bar(
            x=list(reason_counts.keys()),
            y=list(reason_counts.values()),
            marker_color=[
                GREEN if "PROFIT" in k else RED if "LOSS" in k else YELLOW
                for k in reason_counts.keys()
            ],
            text=list(reason_counts.values()),
            textposition="outside",
        ))
        fig_reasons.update_layout(
            title="Exit Reasons",
            paper_bgcolor=BG, plot_bgcolor=BG, font_color="#ffffff",
            height=250, margin=dict(l=0, r=0, t=40, b=0),
            xaxis=dict(gridcolor="#1f2229"),
            yaxis=dict(gridcolor="#1f2229"),
        )
        col_l.plotly_chart(fig_reasons, width="stretch")

        # Confidence vs PnL scatter
        if len(closed) >= 3:
            fig_scatter = go.Figure(go.Scatter(
                x=[p.confidence * 100 for p in closed],
                y=[p.pnl_pct or 0 for p in closed],
                mode="markers+text",
                text=[p.token_name for p in closed],
                textposition="top center",
                marker=dict(
                    size=12,
                    color=[p.pnl_pct or 0 for p in closed],
                    colorscale=[[0, RED], [0.5, YELLOW], [1, GREEN]],
                    cmin=-25, cmax=200,
                    showscale=True,
                    colorbar=dict(title="PnL %", tickfont=dict(color="#8b95a5")),
                    line=dict(color="#0e1117", width=1.5),
                ),
                hovertemplate="<b>%{text}</b><br>Confidence: %{x:.0f}%<br>PnL: %{y:+.1f}%<extra></extra>",
            ))
            fig_scatter.add_hline(y=0, line_dash="dash", line_color="#444", line_width=1)
            fig_scatter.update_layout(
                title="Signal Confidence vs PnL",
                xaxis_title="Confidence %", yaxis_title="PnL %",
                paper_bgcolor=BG, plot_bgcolor=BG, font_color="#ffffff",
                height=250, margin=dict(l=0, r=0, t=40, b=0),
                xaxis=dict(gridcolor="#1f2229"),
                yaxis=dict(gridcolor="#1f2229"),
            )
            col_r.plotly_chart(fig_scatter, width="stretch")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — TRADE SIGNAL GUIDE
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("## When to Trade — Signal Guide")

guide_col1, guide_col2 = st.columns(2)

with guide_col1:
    st.markdown("### BUY signal checklist")
    st.markdown("""
    <div class="signal-buy">
      <b>✅ ALL of these must be true:</b><br><br>
      &nbsp;&nbsp;🔴 Token dumped <b>≥30%</b> from recent high (6h window)<br>
      &nbsp;&nbsp;📈 Volume spiked <b>≥2x</b> normal during the dump<br>
      &nbsp;&nbsp;🔄 Price bounced <b>≥5%</b> off the local bottom<br>
      &nbsp;&nbsp;📊 RSI below <b>35</b> (oversold zone)<br>
      &nbsp;&nbsp;💚 Buy volume &gt; <b>55%</b> of total volume<br>
      &nbsp;&nbsp;🏦 Market cap &gt; <b>$2M</b><br>
      &nbsp;&nbsp;⏱️ Token age &gt; <b>24 hours</b><br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### SELL / Exit levels")
    st.markdown(f"""
    <div class="signal-sell">
      <b>Exit when price hits any of these:</b><br><br>
      &nbsp;&nbsp;🟢 <b>Take Profit 1</b> — price = 2× entry (100% gain) → sell 50–75%<br>
      &nbsp;&nbsp;🟢 <b>Take Profit 2</b> — price = 3× entry (200% gain) → sell remainder<br>
      &nbsp;&nbsp;🔴 <b>Stop Loss</b> — price drops {abs(STOP_LOSS_PCT)}% below entry → exit all<br>
    </div>
    """, unsafe_allow_html=True)

with guide_col2:
    st.markdown("### Reading confidence score")
    fig_conf = go.Figure(go.Indicator(
        mode="gauge+number",
        value=72,
        number={"suffix": "%", "font": {"size": 36, "color": GREEN}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#8b95a5"},
            "bar": {"color": GREEN, "thickness": 0.25},
            "bgcolor": CARD,
            "bordercolor": "#2a2d33",
            "steps": [
                {"range": [0,  40],  "color": "#330000"},
                {"range": [40, 60],  "color": "#1a1400"},
                {"range": [60, 80],  "color": "#002200"},
                {"range": [80, 100], "color": "#004400"},
            ],
            "threshold": {"line": {"color": YELLOW, "width": 4}, "thickness": 0.9, "value": 72},
        },
        title={"text": "Example: 72% confidence", "font": {"color": "#8b95a5"}},
    ))
    fig_conf.update_layout(
        paper_bgcolor=BG, font_color="#ffffff",
        height=220, margin=dict(l=20, r=20, t=20, b=0),
    )
    st.plotly_chart(fig_conf, width="stretch")

    st.markdown("""
    <div class="signal-watch">
      <b>Confidence zones:</b><br><br>
      &nbsp;&nbsp;🔴 <b>0–40%</b> — Skip. Signal too weak.<br>
      &nbsp;&nbsp;🟡 <b>40–60%</b> — Watch only. Half size at most.<br>
      &nbsp;&nbsp;🟢 <b>60–80%</b> — Good setup. Normal position size.<br>
      &nbsp;&nbsp;💎 <b>80–100%</b> — Strong setup. Max position size.<br>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — HOW TO USE
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("How to use this scanner"):
    st.markdown(f"""
    **Step 1 — Start the scanner**
    ```bash
    python scanner.py
    ```
    The scanner runs every {60}s, finds recovery setups, and logs signals to `trades.json`.

    **Step 2 — Watch for signals**
    When the scanner prints `>> SIGNAL: RECOVERY_ENTRY`, check:
    - Confidence ≥ 60% before entering
    - Verify the token on [Birdeye](https://birdeye.so) or [DexScreener](https://dexscreener.com/solana)
    - Double-check liquidity (can you actually buy/sell without massive slippage?)

    **Step 3 — Enter on Jupiter**
    - Go to [jup.ag](https://jup.ag) and swap SOL → token
    - Set slippage to 3–5% for memecoins
    - Use max **{MAX_POSITION_SOL} SOL** per trade

    **Step 4 — Set exit alerts**
    - Note your entry price
    - TP1 = entry × 2.0 → sell 50–75% of position
    - TP2 = entry × 3.0 → sell the rest
    - SL  = entry × {1 + STOP_LOSS_PCT/100:.2f} → exit all immediately

    **Step 5 — Log your trade**
    The scanner auto-logs paper trades. For real trades, use `tracker.py` directly
    or add a manual trade entry to `trades.json`.
    """)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()

st.caption(f"Memecoin Swing Scanner · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
