"""
Memecoin Swing Recovery Dashboard
Run: streamlit run dashboard.py

Three tabs:
  1. Scanner  — fetch trending tokens from DexScreener, flag dip recoveries
  2. Watchlist — track saved tokens with live prices
  3. Trade Log — log entries/exits and track PnL

No API keys needed — DexScreener is free.
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

GREEN = "#00e676"
RED = "#ff1744"
YELLOW = "#ffd600"
BLUE = "#2979ff"

MIN_VOL_5M = 1_000
MIN_LIQUIDITY = 5_000


# ── Persistence helpers ──────────────────────────────────────────────────────
def _load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── DexScreener API ─────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def fetch_trending_tokens():
    try:
        r = requests.get(DEXSCREENER_BOOSTS, timeout=15)
        r.raise_for_status()
        tokens = r.json()
        return tokens if isinstance(tokens, list) else []
    except Exception as e:
        st.error(f"Failed to fetch trending tokens: {e}")
        return []


@st.cache_data(ttl=60)
def fetch_pair_data(address):
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{address}", timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def fetch_pair_data_live(address):
    """Uncached version for watchlist refresh."""
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{address}", timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def _safe_float(obj, *keys, default=0.0):
    """Safely drill into nested dicts and return a float."""
    val = obj
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _best_solana_pair(pairs):
    """Pick highest-24h-volume Solana pair from a list of pairs."""
    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol_pairs:
        return None
    return max(sol_pairs, key=lambda p: _safe_float(p, "volume", "h24"))


def classify_signal(h1, h6, h24):
    recovering = h1 > 2.0
    if h24 <= -30 and recovering:
        return "STRONG DIP"
    if h6 <= -25 and recovering:
        return "BUY DIP"
    if (h6 <= -20 or h24 <= -25) and h1 > 0:
        return "WATCH"
    return "SKIP"


def scan_tokens(tokens):
    """Scan trending tokens for Solana dip recovery setups."""
    results = []
    seen = set()

    solana_tokens = [
        t for t in tokens
        if t.get("tokenAddress")
        and (not t.get("chainId") or t.get("chainId") == "solana")
    ]

    if not solana_tokens:
        return results

    progress = st.progress(0, text="Scanning tokens...")
    total = len(solana_tokens)

    for i, token in enumerate(solana_tokens):
        address = token["tokenAddress"]
        if address in seen:
            continue
        seen.add(address)

        progress.progress((i + 1) / total, text=f"Scanning {i+1}/{total}...")

        pairs = fetch_pair_data(address)
        best = _best_solana_pair(pairs)
        if not best:
            continue

        vol_5m = _safe_float(best, "volume", "m5")
        liquidity = _safe_float(best, "liquidity", "usd")

        if vol_5m < MIN_VOL_5M or liquidity < MIN_LIQUIDITY:
            continue

        h1 = _safe_float(best, "priceChange", "h1")
        h6 = _safe_float(best, "priceChange", "h6")
        h24 = _safe_float(best, "priceChange", "h24")
        price_usd = _safe_float(best, "priceUsd")
        fdv = _safe_float(best, "fdv")
        vol_24h = _safe_float(best, "volume", "h24")

        base = best.get("baseToken") or {}
        name = base.get("name", "?")
        symbol = base.get("symbol", "?")
        pair_url = best.get("url", "")

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
            "vol_5m": vol_5m,
            "volume_24h": vol_24h,
            "liquidity": liquidity,
            "signal": signal,
            "target_2x": price_usd * 2,
            "pair_url": pair_url,
        })

        time.sleep(0.2)

    progress.empty()
    return results


# ── Formatting helpers ───────────────────────────────────────────────────────
def fmt_price(p):
    if not p or p == 0:
        return "$0"
    if p < 0.0000001:
        return f"${p:.12f}"
    if p < 0.00001:
        return f"${p:.10f}"
    if p < 0.001:
        return f"${p:.8f}"
    if p < 1:
        return f"${p:.6f}"
    return f"${p:,.4f}"


def fmt_usd(v):
    if v >= 1_000_000:
        return f"${v / 1e6:.1f}M"
    if v >= 1_000:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def signal_color(sig):
    return {"STRONG DIP": GREEN, "BUY DIP": BLUE, "WATCH": YELLOW}.get(sig, "#666")


# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Memecoin Swing Scanner", layout="wide")
st.markdown(
    "<style>"
    ".signal-tag{display:inline-block;padding:4px 12px;border-radius:16px;"
    "font-weight:700;font-size:13px;letter-spacing:.5px}"
    ".positive{color:#00e676}.negative{color:#ff1744}"
    "</style>",
    unsafe_allow_html=True,
)

st.markdown("# Memecoin Swing Recovery Scanner")

tab_scanner, tab_watchlist, tab_tradelog = st.tabs(
    ["Scanner", "Watchlist", "Trade Log"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scanner:
    st.markdown("### Scan trending tokens for dip recoveries")
    st.caption(
        "DexScreener Boosted Tokens → Solana only → "
        f"Vol(5m) > ${MIN_VOL_5M:,} · Liq > ${MIN_LIQUIDITY:,}"
    )

    col_btn, col_filter = st.columns([1, 3])
    with col_btn:
        scan_clicked = st.button(
            "Scan Now", type="primary", use_container_width=True
        )
    with col_filter:
        show_filter = st.multiselect(
            "Show signals",
            ["STRONG DIP", "BUY DIP", "WATCH"],
            default=["STRONG DIP", "BUY DIP", "WATCH"],
        )

    if scan_clicked:
        trending = fetch_trending_tokens()
        if trending:
            results = scan_tokens(trending)
            st.session_state["scan_results"] = results
            st.session_state["scan_time"] = datetime.now(timezone.utc).strftime(
                "%H:%M:%S UTC"
            )
        else:
            st.warning("No trending tokens returned from DexScreener.")

    results = st.session_state.get("scan_results", [])
    scan_time = st.session_state.get("scan_time", "")

    if results:
        filtered = [r for r in results if r["signal"] in show_filter]
        rank = {"STRONG DIP": 0, "BUY DIP": 1, "WATCH": 2}
        filtered.sort(key=lambda r: rank.get(r["signal"], 99))

        st.caption(
            f"Found {len(filtered)} signal(s) out of "
            f"{len(results)} tokens scanned — {scan_time}"
        )

        if not filtered:
            st.info("No tokens match the selected signal filters.")
        else:
            for r in filtered:
                sig_bg = signal_color(r["signal"])

                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])

                with c1:
                    st.markdown(
                        f"**{r['symbol']}** · {r['name'][:30]}<br>"
                        f"<span class='signal-tag' style='background:{sig_bg}20;"
                        f"color:{sig_bg};border:1px solid {sig_bg}'>"
                        f"{r['signal']}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"`{r['address'][:24]}...`")

                with c2:
                    st.metric("Price", fmt_price(r["price_usd"]))
                    st.caption(f"2x Target: {fmt_price(r['target_2x'])}")

                with c3:
                    st.metric(
                        "1h Change",
                        f"{r['h1_change']:+.1f}%",
                        delta=f"{r['h1_change']:+.1f}%",
                        delta_color="normal" if r["h1_change"] >= 0 else "inverse",
                    )
                    h6c = "positive" if r["h6_change"] >= 0 else "negative"
                    h24c = "positive" if r["h24_change"] >= 0 else "negative"
                    st.markdown(
                        f"6h: <b class='{h6c}'>{r['h6_change']:+.1f}%</b> · "
                        f"24h: <b class='{h24c}'>{r['h24_change']:+.1f}%</b>",
                        unsafe_allow_html=True,
                    )

                with c4:
                    st.metric("MCap", fmt_usd(r["fdv"]))
                    st.caption(
                        f"Vol 5m: {fmt_usd(r['vol_5m'])} · "
                        f"Liq: {fmt_usd(r['liquidity'])}"
                    )

                with c5:
                    if st.button(
                        "Add to Watchlist",
                        key=f"add_{r['address']}",
                        use_container_width=True,
                    ):
                        wl = _load_json(WATCHLIST_FILE)
                        if not any(w["address"] == r["address"] for w in wl):
                            wl.append(
                                {
                                    "address": r["address"],
                                    "symbol": r["symbol"],
                                    "name": r["name"],
                                    "entry_price": r["price_usd"],
                                    "target_2x": r["target_2x"],
                                    "signal": r["signal"],
                                    "pair_url": r["pair_url"],
                                    "added_at": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                }
                            )
                            _save_json(WATCHLIST_FILE, wl)
                            st.success(f"Added {r['symbol']} to watchlist!")
                        else:
                            st.info(f"{r['symbol']} already in watchlist")

                    if r.get("pair_url"):
                        st.link_button(
                            "DexScreener",
                            r["pair_url"],
                            use_container_width=True,
                        )

                st.divider()

    elif not scan_clicked:
        st.info(
            "Click **Scan Now** to fetch trending tokens and find dip recovery setups."
        )


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
            current_price = item["entry_price"]
            h1 = h6 = h24 = 0.0
            pair_url = item.get("pair_url", "")

            cache_key = f"wl_live_{item['address']}"

            if refresh:
                pairs = fetch_pair_data_live(item["address"])
                best = _best_solana_pair(pairs)
                if best:
                    current_price = _safe_float(best, "priceUsd")
                    h1 = _safe_float(best, "priceChange", "h1")
                    h6 = _safe_float(best, "priceChange", "h6")
                    h24 = _safe_float(best, "priceChange", "h24")
                    if not pair_url:
                        pair_url = best.get("url", "")
                    st.session_state[cache_key] = {
                        "price": current_price,
                        "h1": h1,
                        "h6": h6,
                        "h24": h24,
                        "pair_url": pair_url,
                    }
            elif cache_key in st.session_state:
                cached = st.session_state[cache_key]
                current_price = cached.get("price", item["entry_price"])
                h1 = cached.get("h1", 0)
                h6 = cached.get("h6", 0)
                h24 = cached.get("h24", 0)
                pair_url = cached.get("pair_url", pair_url)

            entry = item["entry_price"]
            change_pct = ((current_price - entry) / entry * 100) if entry > 0 else 0
            target = item.get("target_2x", entry * 2)
            progress_pct = (
                min(max(current_price / target, 0), 1.0) if target > 0 else 0
            )

            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 2])

            with c1:
                sig = item.get("signal", "WATCH")
                sc = signal_color(sig)
                st.markdown(
                    f"**{item['symbol']}**<br>"
                    f"<span class='signal-tag' style='background:{sc}20;"
                    f"color:{sc};border:1px solid {sc}'>{sig}</span>",
                    unsafe_allow_html=True,
                )

            with c2:
                st.metric("Entry", fmt_price(entry))

            with c3:
                st.metric(
                    "Current",
                    fmt_price(current_price),
                    delta=f"{change_pct:+.1f}%",
                    delta_color="normal" if change_pct >= 0 else "inverse",
                )

            with c4:
                st.markdown(f"**2x Target:** {fmt_price(target)}")
                st.progress(progress_pct, text=f"{progress_pct:.0%} to 2x")
                st.caption(
                    f"1h: {h1:+.1f}% · 6h: {h6:+.1f}% · 24h: {h24:+.1f}%"
                )

            with c5:
                if pair_url:
                    st.link_button(
                        "DexScreener",
                        pair_url,
                        key=f"wl_dex_{item['address']}_{i}",
                        use_container_width=True,
                    )
                if st.button(
                    "Remove",
                    key=f"rm_{item['address']}_{i}",
                    use_container_width=True,
                ):
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
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in trades if t.get("status") == "CLOSED"]

    realised_pnl = sum(_safe_float(t, "pnl_sol") for t in closed_trades)
    wins = [t for t in closed_trades if _safe_float(t, "pnl_sol") > 0]
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Trades", len(trades))
    m2.metric("Open", len(open_trades))
    m3.metric("Win Rate", f"{win_rate:.0f}%")
    m4.metric("Realised PnL", f"{realised_pnl:+.4f} SOL")

    st.divider()

    # ── Log new trade ────────────────────────────────────────────────────────
    with st.expander("Log a new trade", expanded=False):
        with st.form("trade_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                t_symbol = st.text_input(
                    "Token symbol", placeholder="e.g. BONK"
                )
                t_address = st.text_input(
                    "Token address", placeholder="mint address"
                )
                t_entry_price = st.number_input(
                    "Entry price (USD)",
                    min_value=0.0,
                    format="%.12f",
                    value=0.0,
                )
            with fc2:
                t_size_sol = st.number_input(
                    "Position size (SOL)",
                    min_value=0.0,
                    value=1.0,
                    step=0.5,
                )
                t_side = st.selectbox("Side", ["BUY", "SELL"])
                t_notes = st.text_input(
                    "Notes", placeholder="e.g. STRONG DIP signal"
                )

            submitted = st.form_submit_button("Log Trade", type="primary")
            if submitted and t_symbol and t_entry_price > 0:
                trades.append(
                    {
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
                )
                _save_json(TRADES_FILE, trades)
                st.success(
                    f"Logged {t_side} {t_symbol.upper()} @ {fmt_price(t_entry_price)}"
                )
                st.rerun()

    # ── Close a trade ────────────────────────────────────────────────────────
    if open_trades:
        with st.expander("Close an open trade"):
            labels = [
                f"{t['symbol']} — {fmt_price(t['entry_price'])} "
                f"({t.get('opened_at', '?')[:10]})"
                for t in open_trades
            ]
            sel = st.selectbox(
                "Select trade to close",
                range(len(labels)),
                format_func=lambda idx: labels[idx],
            )
            close_price = st.number_input(
                "Exit price (USD)",
                min_value=0.0,
                format="%.12f",
                value=0.0,
                key="close_price",
            )
            if st.button("Close Trade", type="primary"):
                target_trade = open_trades[sel]
                for t in trades:
                    if (
                        t.get("symbol") == target_trade["symbol"]
                        and t.get("opened_at") == target_trade.get("opened_at")
                        and t.get("status") == "OPEN"
                    ):
                        t["status"] = "CLOSED"
                        t["exit_price"] = close_price
                        t["closed_at"] = datetime.now(timezone.utc).isoformat()
                        if t["entry_price"] > 0:
                            t["pnl_pct"] = (
                                (close_price - t["entry_price"])
                                / t["entry_price"]
                                * 100
                            )
                            t["pnl_sol"] = t["size_sol"] * t["pnl_pct"] / 100
                        break
                _save_json(TRADES_FILE, trades)
                st.success(f"Closed {target_trade['symbol']}!")
                st.rerun()

    st.divider()

    # ── Trade history table ──────────────────────────────────────────────────
    if trades:
        st.markdown("#### Trade History")
        rows = []
        for t in reversed(trades):
            pnl_pct = t.get("pnl_pct")
            pnl_sol = t.get("pnl_sol")
            rows.append(
                {
                    "Symbol": t.get("symbol", "?"),
                    "Side": t.get("side", "BUY"),
                    "Entry": fmt_price(t.get("entry_price", 0)),
                    "Exit": (
                        fmt_price(t["exit_price"]) if t.get("exit_price") else "—"
                    ),
                    "Size SOL": t.get("size_sol", 0),
                    "PnL %": (
                        f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—"
                    ),
                    "PnL SOL": (
                        f"{pnl_sol:+.4f}" if pnl_sol is not None else "—"
                    ),
                    "Status": t.get("status", "OPEN"),
                    "Notes": t.get("notes", ""),
                    "Opened": t.get("opened_at", "—")[:16],
                }
            )

        df = pd.DataFrame(rows)

        def color_status(row):
            status = row["Status"]
            pnl_str = row["PnL SOL"]
            if status == "OPEN":
                return [f"color: {BLUE}"] * len(row)
            if status == "CLOSED" and pnl_str != "—":
                try:
                    pnl_val = float(pnl_str)
                    clr = GREEN if pnl_val > 0 else RED
                    return [f"color: {clr}"] * len(row)
                except (ValueError, TypeError):
                    pass
            return [""] * len(row)

        st.dataframe(
            df.style.apply(color_status, axis=1),
            hide_index=True,
            height=min(500, 50 + len(rows) * 38),
        )
    else:
        st.info("No trades logged yet. Use the form above to log your first trade.")

# ── Footer ───────────────────────────────────────────────────────────────────
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
