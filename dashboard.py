"""
Memecoin Swing Recovery Dashboard
Run: streamlit run dashboard.py

Three tabs:
  1. Scanner  — fetch trending tokens from DexScreener, flag dip recoveries
  2. Watchlist — track saved tokens with live prices
  3. Trade Log — log entries/exits and track PnL
"""

import json
import os
import time
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
WATCHLIST_FILE = "watchlist.json"
TRADES_FILE = "trades.json"
DEXSCREENER_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"

GREEN  = "#00e676"
RED    = "#ff1744"
YELLOW = "#ffd600"
BLUE   = "#2979ff"


# ── Persistence helpers ───────────────────────────────────────────────────────
def _load_json(path: str) -> list:
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _save_json(path: str, data: list):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── DexScreener API ──────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def fetch_trending_tokens() -> list[dict]:
    """Fetch top boosted tokens from DexScreener."""
    try:
        r = requests.get(DEXSCREENER_BOOSTS, timeout=15)
        r.raise_for_status()
        tokens = r.json()
        if isinstance(tokens, list):
            return tokens
        return []
    except Exception as e:
        st.error(f"Failed to fetch trending tokens: {e}")
        return []


@st.cache_data(ttl=60)
def fetch_pair_data(address: str) -> list[dict]:
    """Fetch pair data for a token address from DexScreener."""
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{address}", timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("pairs") or []
    except Exception as e:
        st.warning(f"Pair fetch failed for {address[:8]}...: {e}")
        return []


def fetch_live_price(address: str) -> dict | None:
    """Fetch current price and changes for a token."""
    pairs = fetch_pair_data(address)
    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol_pairs:
        return None
    best = max(sol_pairs, key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0))
    return best


def get_solana_pairs_for_scan(tokens: list[dict]) -> list[dict]:
    """
    For each trending token, fetch pair data and extract the best
    Solana pair with price change info.
    """
    results = []
    seen_addresses = set()

    progress = st.progress(0, text="Scanning tokens...")
    total = len(tokens)

    for i, token in enumerate(tokens):
        address = token.get("tokenAddress", "")
        chain = token.get("chainId", "")

        if not address or address in seen_addresses:
            continue
        if chain and chain != "solana":
            continue

        seen_addresses.add(address)
        progress.progress((i + 1) / total, text=f"Scanning {i+1}/{total}...")

        pairs = fetch_pair_data(address)
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]

        if not sol_pairs:
            continue

        # Pick the pair with highest 24h volume
        best = max(sol_pairs, key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0))

        price_change = best.get("priceChange", {})
        h1  = float(price_change.get("h1", 0) or 0)
        h6  = float(price_change.get("h6", 0) or 0)
        h24 = float(price_change.get("h24", 0) or 0)

        price_usd = float(best.get("priceUsd", 0) or 0)
        fdv = float(best.get("fdv", 0) or 0)
        vol_24h = float(best.get("volume", {}).get("h24", 0) or 0)
        liquidity = float(best.get("liquidity", {}).get("usd", 0) or 0)

        base_info = best.get("baseToken", {})
        name = base_info.get("name", "?")
        symbol = base_info.get("symbol", "?")

        pair_url = best.get("url", "")

        # Determine signal
        signal = classify_signal(h1, h6, h24)

        results.append({
            "address": address,
            "name": name,
            "symbol": symbol,
            "price_usd": price_usd,
            "h1_change": h1,
            "h6_change": h6,
            "h24_change": h24,
            "fdv": fdv,
            "volume_24h": vol_24h,
            "liquidity": liquidity,
            "signal": signal,
            "target_2x": price_usd * 2,
            "pair_url": pair_url,
        })

        time.sleep(0.25)

    progress.empty()
    return results


def classify_signal(h1: float, h6: float, h24: float) -> str:
    """
    Classify the dip-recovery signal strength.
    - STRONG DIP: down 30%+ in 24h, recovering (1h > 2%)
    - BUY DIP: down 25%+ in 6h, recovering (1h > 2%)
    - WATCH: down 20%+ in 6h or 25%+ in 24h, some recovery
    - SKIP: doesn't meet criteria
    """
    recovering = h1 > 2.0

    if h24 <= -30 and recovering:
        return "STRONG DIP"
    if h6 <= -25 and recovering:
        return "BUY DIP"
    if (h6 <= -20 or h24 <= -25) and h1 > 0:
        return "WATCH"
    return "SKIP"


# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_price(p: float) -> str:
    if p == 0: return "$0"
    if p < 0.0000001: return f"${p:.12f}"
    if p < 0.00001:   return f"${p:.10f}"
    if p < 0.001:     return f"${p:.8f}"
    if p < 1:         return f"${p:.6f}"
    return f"${p:,.4f}"


def fmt_usd(v: float) -> str:
    if v >= 1_000_000: return f"${v/1e6:.1f}M"
    if v >= 1_000:     return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def signal_color(sig: str) -> str:
    return {"STRONG DIP": GREEN, "BUY DIP": BLUE, "WATCH": YELLOW}.get(sig, "#666")


# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Memecoin Swing Scanner", layout="wide")
st.markdown("""
<style>
  .signal-tag { display:inline-block; padding:4px 12px; border-radius:16px;
                font-weight:700; font-size:13px; letter-spacing:0.5px; }
  .card { background:#1a1d23; border-radius:10px; padding:16px 20px; margin:6px 0; }
  .positive { color:#00e676; }
  .negative { color:#ff1744; }
</style>
""", unsafe_allow_html=True)

st.markdown("# Memecoin Swing Recovery Scanner")

tab_scanner, tab_watchlist, tab_tradelog = st.tabs(["Scanner", "Watchlist", "Trade Log"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scanner:
    st.markdown("### Scan trending tokens for dip recoveries")
    st.caption("Source: DexScreener Boosted Tokens → Solana pairs only")

    col_btn, col_filter = st.columns([1, 3])
    with col_btn:
        scan_clicked = st.button("Scan Now", type="primary", use_container_width=True)
    with col_filter:
        show_filter = st.multiselect(
            "Show signals",
            ["STRONG DIP", "BUY DIP", "WATCH"],
            default=["STRONG DIP", "BUY DIP", "WATCH"],
        )

    if scan_clicked:
        trending = fetch_trending_tokens()
        if trending:
            results = get_solana_pairs_for_scan(trending)
            st.session_state["scan_results"] = results
            st.session_state["scan_time"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        else:
            st.warning("No trending tokens returned from DexScreener.")

    results = st.session_state.get("scan_results", [])
    scan_time = st.session_state.get("scan_time", "")

    if results:
        filtered = [r for r in results if r["signal"] in show_filter]
        # Sort: STRONG DIP first, then BUY DIP, then WATCH
        rank = {"STRONG DIP": 0, "BUY DIP": 1, "WATCH": 2}
        filtered.sort(key=lambda r: rank.get(r["signal"], 99))

        st.caption(f"Found {len(filtered)} signals out of {len(results)} tokens scanned — {scan_time}")

        if not filtered:
            st.info("No tokens match the selected signal filters.")
        else:
            for r in filtered:
                sig_bg = signal_color(r["signal"])
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])

                    with c1:
                        st.markdown(
                            f"**{r['symbol']}** · {r['name'][:30]}"
                            f"<br><span class='signal-tag' style='background:{sig_bg}20;"
                            f"color:{sig_bg};border:1px solid {sig_bg}'>"
                            f"{r['signal']}</span>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"{r['address'][:20]}...")

                    with c2:
                        st.metric("Price", fmt_price(r["price_usd"]))
                        st.caption(f"2x Target: {fmt_price(r['target_2x'])}")

                    with c3:
                        delta_color = "normal" if r["h1_change"] >= 0 else "inverse"
                        st.metric("1h", f"{r['h1_change']:+.1f}%", delta_color=delta_color)
                        h6_cls = "positive" if r["h6_change"] >= 0 else "negative"
                        h24_cls = "positive" if r["h24_change"] >= 0 else "negative"
                        st.markdown(
                            f"6h: <b class='{h6_cls}'>{r['h6_change']:+.1f}%</b> · "
                            f"24h: <b class='{h24_cls}'>{r['h24_change']:+.1f}%</b>",
                            unsafe_allow_html=True,
                        )

                    with c4:
                        st.metric("MCap", fmt_usd(r["fdv"]))
                        st.caption(f"Vol: {fmt_usd(r['volume_24h'])} · Liq: {fmt_usd(r['liquidity'])}")

                    with c5:
                        # Add to watchlist button
                        btn_key = f"add_{r['address']}"
                        if st.button("Add to Watchlist", key=btn_key, use_container_width=True):
                            wl = _load_json(WATCHLIST_FILE)
                            exists = any(w["address"] == r["address"] for w in wl)
                            if not exists:
                                wl.append({
                                    "address": r["address"],
                                    "symbol": r["symbol"],
                                    "name": r["name"],
                                    "entry_price": r["price_usd"],
                                    "target_2x": r["target_2x"],
                                    "signal": r["signal"],
                                    "added_at": datetime.now(timezone.utc).isoformat(),
                                })
                                _save_json(WATCHLIST_FILE, wl)
                                st.success(f"Added {r['symbol']} to watchlist!")
                            else:
                                st.info(f"{r['symbol']} already in watchlist")

                        if r.get("pair_url"):
                            st.link_button("DexScreener", r["pair_url"], use_container_width=True)

                    st.divider()
    elif not scan_clicked:
        st.info("Click **Scan Now** to fetch trending tokens and find dip recovery setups.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_watchlist:
    st.markdown("### Watchlist — track your picks")

    watchlist = _load_json(WATCHLIST_FILE)

    if not watchlist:
        st.info("Watchlist is empty. Use the Scanner tab to add tokens.")
    else:
        refresh = st.button("Refresh Prices", type="primary")

        to_remove = []

        for i, item in enumerate(watchlist):
            live_data = None
            current_price = item["entry_price"]
            h1 = h6 = h24 = 0.0

            if refresh or f"wl_live_{item['address']}" not in st.session_state:
                live_data = fetch_live_price(item["address"])
                if live_data:
                    current_price = float(live_data.get("priceUsd", 0) or 0)
                    pc = live_data.get("priceChange", {})
                    h1  = float(pc.get("h1", 0) or 0)
                    h6  = float(pc.get("h6", 0) or 0)
                    h24 = float(pc.get("h24", 0) or 0)
                    st.session_state[f"wl_live_{item['address']}"] = {
                        "price": current_price, "h1": h1, "h6": h6, "h24": h24,
                    }
            else:
                cached = st.session_state.get(f"wl_live_{item['address']}", {})
                current_price = cached.get("price", item["entry_price"])
                h1  = cached.get("h1", 0)
                h6  = cached.get("h6", 0)
                h24 = cached.get("h24", 0)

            entry = item["entry_price"]
            change_since_entry = ((current_price - entry) / entry * 100) if entry > 0 else 0
            target = item.get("target_2x", entry * 2)
            progress_to_target = min(max(current_price / target, 0), 1.0) if target > 0 else 0

            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 1])

                with c1:
                    sig = item.get("signal", "WATCH")
                    sc = signal_color(sig)
                    st.markdown(
                        f"**{item['symbol']}**"
                        f"<br><span class='signal-tag' style='background:{sc}20;"
                        f"color:{sc};border:1px solid {sc}'>{sig}</span>",
                        unsafe_allow_html=True,
                    )

                with c2:
                    st.metric("Entry", fmt_price(entry))

                with c3:
                    chg_cls = "positive" if change_since_entry >= 0 else "negative"
                    st.metric(
                        "Current",
                        fmt_price(current_price),
                        delta=f"{change_since_entry:+.1f}%",
                        delta_color="normal" if change_since_entry >= 0 else "inverse",
                    )

                with c4:
                    st.markdown(f"**2x Target:** {fmt_price(target)}")
                    st.progress(progress_to_target,
                                text=f"{progress_to_target:.0%} to 2x")
                    st.caption(
                        f"1h: {h1:+.1f}% · 6h: {h6:+.1f}% · 24h: {h24:+.1f}%"
                    )

                with c5:
                    if st.button("Remove", key=f"rm_{item['address']}_{i}", use_container_width=True):
                        to_remove.append(i)

            st.divider()

        if to_remove:
            watchlist = [w for j, w in enumerate(watchlist) if j not in to_remove]
            _save_json(WATCHLIST_FILE, watchlist)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRADE LOG
# ═══════════════════════════════════════════════════════════════════════════════
with tab_tradelog:
    st.markdown("### Trade Log")

    trades = _load_json(TRADES_FILE)

    # ── Summary metrics ──────────────────────────────────────────────────────
    total_trades = len(trades)
    open_trades  = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]

    realised_pnl = sum(t.get("pnl_sol", 0) or 0 for t in closed_trades)
    wins  = [t for t in closed_trades if (t.get("pnl_sol", 0) or 0) > 0]
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Trades", total_trades)
    m2.metric("Open", len(open_trades))
    m3.metric("Win Rate", f"{win_rate:.0f}%")
    pnl_color = "normal" if realised_pnl >= 0 else "inverse"
    m4.metric("Realised PnL", f"{realised_pnl:+.4f} SOL", delta_color=pnl_color)

    st.divider()

    # ── Log new trade form ───────────────────────────────────────────────────
    with st.expander("Log a new trade", expanded=False):
        with st.form("trade_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                t_symbol = st.text_input("Token symbol", placeholder="e.g. BONK")
                t_address = st.text_input("Token address", placeholder="mint address")
                t_entry_price = st.number_input("Entry price (USD)", min_value=0.0,
                                                format="%.12f", value=0.0)
            with fc2:
                t_size_sol = st.number_input("Position size (SOL)", min_value=0.0,
                                             value=1.0, step=0.5)
                t_side = st.selectbox("Side", ["BUY", "SELL"])
                t_notes = st.text_input("Notes", placeholder="e.g. STRONG DIP signal")

            submitted = st.form_submit_button("Log Trade", type="primary")
            if submitted and t_symbol and t_entry_price > 0:
                new_trade = {
                    "symbol": t_symbol.upper(),
                    "address": t_address,
                    "side": t_side,
                    "entry_price": t_entry_price,
                    "size_sol": t_size_sol,
                    "status": "OPEN",
                    "exit_price": None,
                    "pnl_pct": None,
                    "pnl_sol": None,
                    "notes": t_notes,
                    "opened_at": datetime.now(timezone.utc).isoformat(),
                    "closed_at": None,
                }
                trades.append(new_trade)
                _save_json(TRADES_FILE, trades)
                st.success(f"Logged {t_side} {t_symbol} @ {fmt_price(t_entry_price)}")
                st.rerun()

    # ── Close trade form ─────────────────────────────────────────────────────
    if open_trades:
        with st.expander("Close an open trade"):
            open_labels = [
                f"{t['symbol']} — entered {fmt_price(t['entry_price'])} ({t.get('opened_at', '?')[:10]})"
                for t in open_trades
            ]
            selected_idx = st.selectbox("Select trade to close", range(len(open_labels)),
                                        format_func=lambda i: open_labels[i])
            close_price = st.number_input("Exit price (USD)", min_value=0.0,
                                          format="%.12f", value=0.0, key="close_price")
            if st.button("Close Trade", type="primary"):
                trade_to_close = open_trades[selected_idx]
                # Find it in the main list
                for t in trades:
                    if (t.get("symbol") == trade_to_close["symbol"]
                            and t.get("opened_at") == trade_to_close.get("opened_at")
                            and t.get("status") == "OPEN"):
                        t["status"] = "CLOSED"
                        t["exit_price"] = close_price
                        t["closed_at"] = datetime.now(timezone.utc).isoformat()
                        if t["entry_price"] > 0:
                            t["pnl_pct"] = (close_price - t["entry_price"]) / t["entry_price"] * 100
                            t["pnl_sol"] = t["size_sol"] * t["pnl_pct"] / 100
                        break
                _save_json(TRADES_FILE, trades)
                st.success(f"Closed {trade_to_close['symbol']}!")
                st.rerun()

    st.divider()

    # ── Trade history table ──────────────────────────────────────────────────
    if trades:
        st.markdown("#### Trade History")
        rows = []
        for t in reversed(trades):
            pnl_pct = t.get("pnl_pct")
            pnl_sol = t.get("pnl_sol")
            rows.append({
                "Symbol": t["symbol"],
                "Side": t.get("side", "BUY"),
                "Entry": fmt_price(t["entry_price"]),
                "Exit": fmt_price(t["exit_price"]) if t.get("exit_price") else "—",
                "Size (SOL)": t.get("size_sol", 0),
                "PnL %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
                "PnL SOL": f"{pnl_sol:+.4f}" if pnl_sol is not None else "—",
                "Status": t.get("status", "OPEN"),
                "Notes": t.get("notes", ""),
                "Opened": (t.get("opened_at", "")[:16] or "—"),
            })

        df = pd.DataFrame(rows)

        def color_status(row):
            if row["Status"] == "CLOSED":
                pnl = row.get("PnL SOL", "—")
                if pnl != "—" and float(pnl) > 0:
                    return ["color: #00e676"] * len(row)
                elif pnl != "—":
                    return ["color: #ff1744"] * len(row)
            elif row["Status"] == "OPEN":
                return ["color: #2979ff"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(color_status, axis=1),
            hide_index=True,
            height=min(500, 50 + len(rows) * 38),
        )
    else:
        st.info("No trades logged yet. Use the form above to log your first trade.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
