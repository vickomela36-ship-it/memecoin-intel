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
DEXSCREENER_BOOSTS_TOP = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_BOOSTS_LATEST = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"

GREEN = "#00e676"
RED = "#ff1744"
YELLOW = "#ffd600"
BLUE = "#2979ff"
ORANGE = "#ff9100"

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
def _fetch_endpoint(url):
    """Fetch a DexScreener endpoint that returns a list of tokens."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


@st.cache_data(ttl=120)
def _fetch_search(query):
    """Search DexScreener pairs by query string."""
    try:
        r = requests.get(DEXSCREENER_SEARCH, params={"q": query}, timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def fetch_trending_tokens():
    """
    Combine multiple DexScreener endpoints to widen the source pool.
    Returns a deduplicated list of {tokenAddress, chainId} dicts.
    """
    pool = []
    seen = set()

    # 1. Top + latest boosts (richest signal — paid promotion)
    for url in (DEXSCREENER_BOOSTS_TOP, DEXSCREENER_BOOSTS_LATEST,
                DEXSCREENER_PROFILES):
        for tok in _fetch_endpoint(url):
            addr = tok.get("tokenAddress")
            chain = tok.get("chainId")
            if addr and addr not in seen and (not chain or chain == "solana"):
                seen.add(addr)
                pool.append({"tokenAddress": addr, "chainId": chain or "solana"})

    # 2. Add Solana trending pairs from search (catches non-boosted movers)
    for q in ("SOL", "PUMP", "MEME"):
        for pair in _fetch_search(q):
            if pair.get("chainId") != "solana":
                continue
            base = pair.get("baseToken") or {}
            addr = base.get("address")
            if addr and addr not in seen:
                seen.add(addr)
                pool.append({"tokenAddress": addr, "chainId": "solana"})

    if not pool:
        st.error("Failed to fetch any trending tokens from DexScreener.")
    return pool


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


def classify_signal(h1, h6, h24, strong_dump=-30.0, buy_dump=-25.0,
                    watch_dump=-20.0, recovery=2.0):
    """
    Classify dip recovery signal with tunable thresholds.
    All dump values are negative (e.g. -30 means dropped 30%).
    """
    recovering = h1 > recovery
    if h24 <= strong_dump and recovering:
        return "STRONG DIP"
    if h6 <= buy_dump and recovering:
        return "BUY DIP"
    if (h6 <= watch_dump or h24 <= buy_dump) and h1 > 0:
        return "WATCH"
    return "SKIP"


def scan_tokens(tokens, min_vol_5m=MIN_VOL_5M, min_liq=MIN_LIQUIDITY,
                strong_dump=-30.0, buy_dump=-25.0, watch_dump=-20.0,
                recovery=2.0):
    """Scan trending tokens for Solana dip recovery setups."""
    results = []
    seen = set()
    stats = {"total": 0, "no_pair": 0, "filtered_vol_liq": 0, "matched": 0}

    solana_tokens = [
        t for t in tokens
        if t.get("tokenAddress")
        and (not t.get("chainId") or t.get("chainId") == "solana")
    ]
    stats["total"] = len(solana_tokens)

    if not solana_tokens:
        return results, stats

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
            stats["no_pair"] += 1
            continue

        vol_5m = _safe_float(best, "volume", "m5")
        liquidity = _safe_float(best, "liquidity", "usd")

        if vol_5m < min_vol_5m or liquidity < min_liq:
            stats["filtered_vol_liq"] += 1
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

        vol_h1 = _safe_float(best, "volume", "h1")
        vol_h6 = _safe_float(best, "volume", "h6")

        txns = best.get("txns") or {}
        boosts = token.get("totalAmount") or token.get("amount") or 0
        try:
            boosts = int(boosts)
        except (ValueError, TypeError):
            boosts = 0

        signal = classify_signal(h1, h6, h24, strong_dump, buy_dump,
                                 watch_dump, recovery)
        if signal != "SKIP":
            stats["matched"] += 1

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
            "vol_h1": vol_h1,
            "vol_h6": vol_h6,
            "volume_24h": vol_24h,
            "liquidity": liquidity,
            "signal": signal,
            "target_2x": price_usd * 2,
            "pair_url": pair_url,
            "txns": txns,
            "boosts": boosts,
            "pair_data": best,
        })

        time.sleep(0.15)

    progress.empty()
    return results, stats


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


# ── Recommendations engine ──────────────────────────────────────────────────
def compute_recommendations(price, h1, h6, h24, fdv, signal):
    """Compute buy zone, sell targets, stop-loss, and mcap guidance."""
    if price <= 0:
        return None

    sl_pct = 0.20
    if signal == "STRONG DIP":
        sl_pct = 0.15
    elif signal == "BUY DIP":
        sl_pct = 0.18

    stop_loss = price * (1 - sl_pct)
    target_2x = price * 2
    target_3x = price * 3

    dip_depth = min(h6, h24)
    if dip_depth < -40:
        buy_low = price * 0.92
        buy_high = price * 1.02
    elif dip_depth < -25:
        buy_low = price * 0.95
        buy_high = price * 1.03
    else:
        buy_low = price * 0.97
        buy_high = price * 1.05

    if fdv > 0:
        mcap_target_2x = fdv * 2
        mcap_target_3x = fdv * 3
    else:
        mcap_target_2x = mcap_target_3x = 0

    if signal == "STRONG DIP":
        conviction = "HIGH"
    elif signal == "BUY DIP":
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    return {
        "buy_low": buy_low,
        "buy_high": buy_high,
        "stop_loss": stop_loss,
        "sl_pct": sl_pct * 100,
        "target_2x": target_2x,
        "target_3x": target_3x,
        "mcap_now": fdv,
        "mcap_2x": mcap_target_2x,
        "mcap_3x": mcap_target_3x,
        "conviction": conviction,
    }


def compute_volume_momentum(vol_m5, vol_h1, vol_h6, vol_24h):
    """Detect volume acceleration across timeframes."""
    indicators = []
    score = 0

    if vol_h1 > 0:
        m5_rate = vol_m5 * 12
        h1_accel = m5_rate / vol_h1 if vol_h1 > 0 else 0
        if h1_accel > 2.0:
            indicators.append(("5m vs 1h", h1_accel, "SURGING"))
            score += 3
        elif h1_accel > 1.3:
            indicators.append(("5m vs 1h", h1_accel, "RISING"))
            score += 2
        elif h1_accel > 0.8:
            indicators.append(("5m vs 1h", h1_accel, "STEADY"))
            score += 1
        else:
            indicators.append(("5m vs 1h", h1_accel, "FADING"))

    if vol_h6 > 0:
        h1_rate = vol_h1 * 6
        h6_accel = h1_rate / vol_h6 if vol_h6 > 0 else 0
        if h6_accel > 1.5:
            indicators.append(("1h vs 6h", h6_accel, "ACCELERATING"))
            score += 2
        elif h6_accel > 1.0:
            indicators.append(("1h vs 6h", h6_accel, "BUILDING"))
            score += 1
        else:
            indicators.append(("1h vs 6h", h6_accel, "DECLINING"))

    if vol_24h > 0:
        h6_rate = vol_h6 * 4
        h24_accel = h6_rate / vol_24h if vol_24h > 0 else 0
        if h24_accel > 1.5:
            indicators.append(("6h vs 24h", h24_accel, "STRONG UPTICK"))
            score += 2
        elif h24_accel > 1.0:
            indicators.append(("6h vs 24h", h24_accel, "INCREASING"))
            score += 1
        else:
            indicators.append(("6h vs 24h", h24_accel, "COOLING"))

    if score >= 6:
        overall = "SURGING"
    elif score >= 4:
        overall = "STRONG"
    elif score >= 2:
        overall = "MODERATE"
    else:
        overall = "WEAK"

    return {"indicators": indicators, "score": score, "overall": overall}


def compute_sentiment(txns, boosts, pair_data):
    """Aggregate on-chain sentiment from transaction counts and social signals."""
    signals = []
    score = 0

    if txns:
        for tf_label, tf_key in [("5m", "m5"), ("1h", "h1"), ("6h", "h6"), ("24h", "h24")]:
            tf = txns.get(tf_key, {})
            buys = int(tf.get("buys", 0) or 0)
            sells = int(tf.get("sells", 0) or 0)
            total = buys + sells
            if total > 0:
                buy_ratio = buys / total
                signals.append({
                    "tf": tf_label,
                    "buys": buys,
                    "sells": sells,
                    "ratio": buy_ratio,
                })
                if buy_ratio > 0.60:
                    score += 2
                elif buy_ratio > 0.50:
                    score += 1

    recent_buy_ratio = 0
    if signals:
        recent_buy_ratio = signals[0]["ratio"]

    if boosts and boosts > 0:
        score += min(boosts // 10, 3)

    has_website = False
    has_twitter = False
    has_telegram = False
    info = pair_data.get("info") or {}
    socials = info.get("socials") or []
    websites = info.get("websites") or []
    if websites:
        has_website = True
        score += 1
    for s in socials:
        stype = (s.get("type") or "").lower()
        if "twitter" in stype or "x.com" in stype:
            has_twitter = True
            score += 1
        if "telegram" in stype:
            has_telegram = True
            score += 1

    if score >= 8:
        overall = "VERY BULLISH"
    elif score >= 5:
        overall = "BULLISH"
    elif score >= 3:
        overall = "NEUTRAL"
    else:
        overall = "BEARISH"

    return {
        "txn_signals": signals,
        "recent_buy_ratio": recent_buy_ratio,
        "boosts": boosts or 0,
        "has_website": has_website,
        "has_twitter": has_twitter,
        "has_telegram": has_telegram,
        "score": score,
        "overall": overall,
    }


def sentiment_color(overall):
    return {
        "VERY BULLISH": GREEN,
        "BULLISH": BLUE,
        "NEUTRAL": YELLOW,
        "BEARISH": RED,
    }.get(overall, "#666")


def momentum_color(overall):
    return {
        "SURGING": GREEN,
        "STRONG": BLUE,
        "MODERATE": YELLOW,
        "WEAK": RED,
    }.get(overall, "#666")


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
        "Sources: DexScreener Boosts (top + latest) + Token Profiles + Search"
    )

    # ── Filter presets ──────────────────────────────────────────────────────
    preset = st.radio(
        "Strictness preset",
        ["Loose (more results)", "Normal", "Strict (best setups only)"],
        index=0,
        horizontal=True,
    )

    if preset == "Loose (more results)":
        d_strong, d_buy, d_watch, d_rec = -20.0, -15.0, -10.0, 0.0
        d_vol, d_liq = 200, 2_000
    elif preset == "Normal":
        d_strong, d_buy, d_watch, d_rec = -25.0, -20.0, -15.0, 1.0
        d_vol, d_liq = 500, 3_000
    else:  # Strict
        d_strong, d_buy, d_watch, d_rec = -30.0, -25.0, -20.0, 2.0
        d_vol, d_liq = 1_000, 5_000

    with st.expander("Advanced filters", expanded=False):
        c_a, c_b = st.columns(2)
        with c_a:
            d_strong = st.slider(
                "STRONG DIP — 24h drop ≤", -60.0, -10.0, d_strong, step=1.0,
                help="Token must have dropped this much in 24h to qualify as STRONG DIP",
            )
            d_buy = st.slider(
                "BUY DIP — 6h drop ≤", -50.0, -5.0, d_buy, step=1.0,
                help="Token must have dropped this much in 6h to qualify as BUY DIP",
            )
            d_watch = st.slider(
                "WATCH — 6h drop ≤", -40.0, -5.0, d_watch, step=1.0,
            )
            d_rec = st.slider(
                "Recovery threshold — 1h change >", -2.0, 10.0, d_rec, step=0.5,
                help="Token must be bouncing this much in the last hour. Lower = more results.",
            )
        with c_b:
            d_vol = st.number_input(
                "Min 5m volume ($)", 0, 100_000, d_vol, step=100,
            )
            d_liq = st.number_input(
                "Min liquidity ($)", 0, 1_000_000, d_liq, step=1_000,
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
            results, stats = scan_tokens(
                trending,
                min_vol_5m=d_vol, min_liq=d_liq,
                strong_dump=d_strong, buy_dump=d_buy,
                watch_dump=d_watch, recovery=d_rec,
            )
            st.session_state["scan_results"] = results
            st.session_state["scan_stats"] = stats
            st.session_state["scan_time"] = datetime.now(timezone.utc).strftime(
                "%H:%M:%S UTC"
            )
        else:
            st.warning("No trending tokens returned from DexScreener.")

    results = st.session_state.get("scan_results", [])
    stats = st.session_state.get("scan_stats", {})
    scan_time = st.session_state.get("scan_time", "")

    # Show breakdown so user knows where filtering happened
    if stats:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tokens fetched", stats.get("total", 0))
        s2.metric("No Solana pair", stats.get("no_pair", 0))
        s3.metric("Below vol/liq", stats.get("filtered_vol_liq", 0))
        s4.metric("Matched signal", stats.get("matched", 0))

    if results:
        filtered = [r for r in results if r["signal"] in show_filter]
        rank = {"STRONG DIP": 0, "BUY DIP": 1, "WATCH": 2, "SKIP": 3}
        filtered.sort(key=lambda r: (rank.get(r["signal"], 99), -r["h1_change"]))

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

                # ── Expandable detail: Recommendations + Sentiment + Volume ──
                with st.expander(
                    f"Details: {r['symbol']} — Recommendations · Sentiment · Volume",
                    expanded=False,
                ):
                    det1, det2, det3 = st.columns(3)

                    # ── Recommendations ──────────────────────────────────
                    rec = compute_recommendations(
                        r["price_usd"], r["h1_change"], r["h6_change"],
                        r["h24_change"], r["fdv"], r["signal"],
                    )
                    with det1:
                        st.markdown("##### Trade Recommendation")
                        if rec:
                            conv_clr = {
                                "HIGH": GREEN, "MEDIUM": BLUE, "LOW": YELLOW,
                            }.get(rec["conviction"], "#666")
                            st.markdown(
                                f"Conviction: <b style='color:{conv_clr}'>"
                                f"{rec['conviction']}</b>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"**Buy Zone:** {fmt_price(rec['buy_low'])} — "
                                f"{fmt_price(rec['buy_high'])}"
                            )
                            st.markdown(
                                f"**Stop-Loss:** {fmt_price(rec['stop_loss'])} "
                                f"(-{rec['sl_pct']:.0f}%)"
                            )
                            st.markdown(
                                f"**Target 2x:** {fmt_price(rec['target_2x'])}"
                            )
                            st.markdown(
                                f"**Target 3x:** {fmt_price(rec['target_3x'])}"
                            )
                            if rec["mcap_now"] > 0:
                                st.caption(
                                    f"MCap now: {fmt_usd(rec['mcap_now'])} · "
                                    f"2x: {fmt_usd(rec['mcap_2x'])} · "
                                    f"3x: {fmt_usd(rec['mcap_3x'])}"
                                )

                    # ── Sentiment ─────────────────────────────────────────
                    sent = compute_sentiment(
                        r.get("txns", {}), r.get("boosts", 0),
                        r.get("pair_data", {}),
                    )
                    with det2:
                        st.markdown("##### Sentiment")
                        s_clr = sentiment_color(sent["overall"])
                        st.markdown(
                            f"Overall: <b style='color:{s_clr}'>"
                            f"{sent['overall']}</b> "
                            f"(score {sent['score']})",
                            unsafe_allow_html=True,
                        )

                        if sent["txn_signals"]:
                            for ts in sent["txn_signals"]:
                                br = ts["ratio"]
                                bar_clr = GREEN if br > 0.55 else (
                                    YELLOW if br > 0.45 else RED
                                )
                                st.markdown(
                                    f"{ts['tf']}: "
                                    f"<b style='color:{GREEN}'>{ts['buys']}B</b>"
                                    f" / "
                                    f"<b style='color:{RED}'>{ts['sells']}S</b>"
                                    f" · Buy ratio "
                                    f"<b style='color:{bar_clr}'>"
                                    f"{br:.0%}</b>",
                                    unsafe_allow_html=True,
                                )

                        social_parts = []
                        if sent["has_website"]:
                            social_parts.append("Website")
                        if sent["has_twitter"]:
                            social_parts.append("Twitter/X")
                        if sent["has_telegram"]:
                            social_parts.append("Telegram")
                        if social_parts:
                            st.caption(
                                f"Socials: {', '.join(social_parts)}"
                            )
                        if sent["boosts"] > 0:
                            st.caption(
                                f"DexScreener boosts: {sent['boosts']}"
                            )

                    # ── Volume Momentum ───────────────────────────────────
                    vmom = compute_volume_momentum(
                        r.get("vol_5m", 0), r.get("vol_h1", 0),
                        r.get("vol_h6", 0), r.get("volume_24h", 0),
                    )
                    with det3:
                        st.markdown("##### Volume Momentum")
                        m_clr = momentum_color(vmom["overall"])
                        st.markdown(
                            f"Flow: <b style='color:{m_clr}'>"
                            f"{vmom['overall']}</b> "
                            f"(score {vmom['score']}/7)",
                            unsafe_allow_html=True,
                        )
                        for ind in vmom["indicators"]:
                            i_clr = {
                                "SURGING": GREEN, "RISING": BLUE,
                                "ACCELERATING": GREEN, "BUILDING": BLUE,
                                "STRONG UPTICK": GREEN, "INCREASING": BLUE,
                                "STEADY": YELLOW, "FADING": RED,
                                "DECLINING": RED, "COOLING": ORANGE,
                            }.get(ind[2], "#666")
                            st.markdown(
                                f"{ind[0]}: **{ind[1]:.1f}x** — "
                                f"<b style='color:{i_clr}'>{ind[2]}</b>",
                                unsafe_allow_html=True,
                            )
                        st.caption(
                            f"Vol 5m: {fmt_usd(r.get('vol_5m', 0))} · "
                            f"1h: {fmt_usd(r.get('vol_h1', 0))} · "
                            f"6h: {fmt_usd(r.get('vol_h6', 0))} · "
                            f"24h: {fmt_usd(r.get('volume_24h', 0))}"
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

    # Normalise old-format trades (seed_data.py used different keys)
    for t in trades:
        if "token_name" in t and "symbol" not in t:
            t["symbol"] = t["token_name"]
        if "mint_address" in t and "address" not in t:
            t["address"] = t["mint_address"]
        if "entry_time" in t and "opened_at" not in t:
            t["opened_at"] = t["entry_time"]
        if "exit_time" in t and "closed_at" not in t:
            t["closed_at"] = t["exit_time"]
        if "exit_reason" in t and "notes" not in t:
            t["notes"] = t.get("signal_reason", t.get("exit_reason", ""))

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
