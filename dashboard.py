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
SIGNALS_FILE = "signals_log.json"
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


# ── Trade duration + buy action engine ──────────────────────────────────────
def classify_trade_duration(h1, h6, h24, vol_momentum_score, liquidity):
    """Classify as SHORT (scalp 1-6h) or LONG (swing 6-48h)."""
    if h1 > 5 and vol_momentum_score >= 4:
        return "SHORT", "1-6h scalp — fast bounce with volume surge"
    if h24 < -40 and 0 < h1 < 5:
        return "LONG", "6-48h swing — deep dip, early recovery phase"
    if h6 < -30 and h1 > 2:
        return "LONG", "6-24h swing — significant dip still unwinding"
    if vol_momentum_score >= 5 and h1 > 3:
        return "SHORT", "2-8h scalp — momentum-driven recovery"
    if h24 < -25 and h1 < 3:
        return "LONG", "12-48h swing — gradual recovery expected"
    if liquidity > 100_000 and h1 > 2:
        return "SHORT", "2-6h scalp — high liquidity fast mover"
    return "LONG", "6-24h swing — standard recovery play"


def compute_buy_action(signal, sentiment_score, vol_momentum_score, h1,
                       recent_buy_ratio):
    """Return explicit BUY NOW / BUY ON DIP / WAIT / AVOID recommendation."""
    score = 0
    if signal == "STRONG DIP":
        score += 3
    elif signal == "BUY DIP":
        score += 2
    elif signal == "WATCH":
        score += 1
    if sentiment_score >= 5:
        score += 2
    elif sentiment_score >= 3:
        score += 1
    if vol_momentum_score >= 4:
        score += 2
    elif vol_momentum_score >= 2:
        score += 1
    if h1 > 5:
        score += 1
    if recent_buy_ratio > 0.60:
        score += 1

    if score >= 7:
        return "BUY NOW", "Strong setup — all indicators align"
    if score >= 5:
        return "BUY ON DIP", "Good setup — enter at buy zone low for better R/R"
    if score >= 3:
        return "WAIT", "Developing — monitor for stronger confirmation"
    return "AVOID", "Weak setup — insufficient recovery signals"


def buy_action_color(action):
    return {
        "BUY NOW": GREEN,
        "BUY ON DIP": BLUE,
        "WAIT": YELLOW,
        "AVOID": RED,
    }.get(action, "#666")


def duration_color(dur):
    return {"SHORT": ORANGE, "LONG": BLUE}.get(dur, "#666")


# ── Signal logging + 2x hit tracker ────────────────────────────────────────
def log_signals(results):
    """Persist non-SKIP signals for 2x ROI tracking."""
    signals = _load_json(SIGNALS_FILE)
    existing_keys = set()
    for s in signals:
        existing_keys.add((s.get("address", ""), s.get("signal_time", "")[:10]))

    now = datetime.now(timezone.utc).isoformat()
    added = 0

    for r in results:
        if r.get("signal") == "SKIP":
            continue
        key = (r["address"], now[:10])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        signals.append({
            "address": r["address"],
            "symbol": r["symbol"],
            "signal": r["signal"],
            "signal_price": r["price_usd"],
            "signal_time": now,
            "target_2x": r["price_usd"] * 2,
            "duration_class": r.get("duration_class", "LONG"),
            "buy_action": r.get("buy_action", "WAIT"),
            "buy_action_reason": r.get("buy_action_reason", ""),
            "hit_2x": False,
            "hit_2x_time": None,
            "hit_2x_price": None,
            "peak_price": r["price_usd"],
            "peak_roi_pct": 0.0,
            "checked_at": now,
        })
        added += 1

    if added:
        _save_json(SIGNALS_FILE, signals)
    return signals, added


def check_2x_hits():
    """Check open signals against live prices, mark 2x hits."""
    signals = _load_json(SIGNALS_FILE)
    if not signals:
        return signals, 0, 0

    updated = False
    new_hits = 0
    checked = 0

    for s in signals:
        if s.get("hit_2x"):
            continue
        target = s.get("target_2x", 0)
        if target <= 0:
            continue

        pairs = fetch_pair_data(s["address"])
        best = _best_solana_pair(pairs)
        if not best:
            continue
        checked += 1

        current = _safe_float(best, "priceUsd")
        entry = s.get("signal_price", 0)
        if entry > 0 and current > s.get("peak_price", 0):
            s["peak_price"] = current
            s["peak_roi_pct"] = round((current - entry) / entry * 100, 2)
            updated = True

        s["checked_at"] = datetime.now(timezone.utc).isoformat()

        if current >= target:
            s["hit_2x"] = True
            s["hit_2x_time"] = datetime.now(timezone.utc).isoformat()
            s["hit_2x_price"] = current
            new_hits += 1
            updated = True

    if updated:
        _save_json(SIGNALS_FILE, signals)
    return signals, new_hits, checked


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

tab_scanner, tab_watchlist, tab_tradelog, tab_scoreboard = st.tabs(
    ["Scanner", "Watchlist", "Trade Log", "Signal Scoreboard"]
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

            for r in results:
                if r["signal"] == "SKIP":
                    continue
                vmom = compute_volume_momentum(
                    r.get("vol_5m", 0), r.get("vol_h1", 0),
                    r.get("vol_h6", 0), r.get("volume_24h", 0),
                )
                sent = compute_sentiment(
                    r.get("txns", {}), r.get("boosts", 0),
                    r.get("pair_data", {}),
                )
                dur_class, dur_reason = classify_trade_duration(
                    r["h1_change"], r["h6_change"], r["h24_change"],
                    vmom["score"], r["liquidity"],
                )
                action, action_reason = compute_buy_action(
                    r["signal"], sent["score"], vmom["score"],
                    r["h1_change"], sent["recent_buy_ratio"],
                )
                r["duration_class"] = dur_class
                r["duration_reason"] = dur_reason
                r["buy_action"] = action
                r["buy_action_reason"] = action_reason

            _, sig_added = log_signals(results)
            if sig_added:
                st.toast(f"Logged {sig_added} new signal(s) to scoreboard")

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
                ba = r.get("buy_action", "WAIT")
                ba_clr = buy_action_color(ba)
                dc = r.get("duration_class", "LONG")
                dc_clr = duration_color(dc)

                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])

                with c1:
                    st.markdown(
                        f"**{r['symbol']}** · {r['name'][:30]}<br>"
                        f"<span class='signal-tag' style='background:{sig_bg}20;"
                        f"color:{sig_bg};border:1px solid {sig_bg}'>"
                        f"{r['signal']}</span> "
                        f"<span class='signal-tag' style='background:{ba_clr}20;"
                        f"color:{ba_clr};border:1px solid {ba_clr}'>"
                        f"{ba}</span> "
                        f"<span class='signal-tag' style='background:{dc_clr}20;"
                        f"color:{dc_clr};border:1px solid {dc_clr}'>"
                        f"{dc}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"`{r['address'][:24]}...` · "
                        f"{r.get('duration_reason', '')}"
                    )

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
                        ba_r = r.get("buy_action", "WAIT")
                        ba_r_clr = buy_action_color(ba_r)
                        st.markdown(
                            f"Action: <b style='color:{ba_r_clr};font-size:16px'>"
                            f"{ba_r}</b>",
                            unsafe_allow_html=True,
                        )
                        st.caption(r.get("buy_action_reason", ""))
                        dc_r = r.get("duration_class", "LONG")
                        dc_r_clr = duration_color(dc_r)
                        st.markdown(
                            f"Duration: <b style='color:{dc_r_clr}'>"
                            f"{dc_r}</b> · {r.get('duration_reason', '')}",
                            unsafe_allow_html=True,
                        )
                        if rec:
                            st.markdown(
                                f"**Buy Zone:** {fmt_price(rec['buy_low'])} — "
                                f"{fmt_price(rec['buy_high'])}"
                            )
                            st.markdown(
                                f"**Stop-Loss:** {fmt_price(rec['stop_loss'])} "
                                f"(-{rec['sl_pct']:.0f}%)"
                            )
                            st.markdown(
                                f"**Target 2x:** {fmt_price(rec['target_2x'])} · "
                                f"**3x:** {fmt_price(rec['target_3x'])}"
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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIGNAL SCOREBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scoreboard:
    st.markdown("### Signal Scoreboard — 2x ROI Tracker")
    st.caption(
        "Every buy signal is recorded here. The scanner checks live prices "
        "and marks signals that hit 2x ROI."
    )

    all_signals = _load_json(SIGNALS_FILE)

    sb_c1, sb_c2 = st.columns([1, 3])
    with sb_c1:
        check_clicked = st.button(
            "Check 2x Hits Now", type="primary", use_container_width=True,
        )
    with sb_c2:
        st.caption(
            "Fetches live prices for all open signals and marks any that hit 2x."
        )

    if check_clicked and all_signals:
        with st.spinner("Checking live prices..."):
            all_signals, new_hits, checked = check_2x_hits()
        if new_hits:
            st.success(f"New 2x hits: {new_hits} (checked {checked} signals)")
        else:
            st.info(f"No new 2x hits (checked {checked} open signals)")

    if all_signals:
        hits = [s for s in all_signals if s.get("hit_2x")]
        pending = [s for s in all_signals if not s.get("hit_2x")]

        total_signals = len(all_signals)
        total_hits = len(hits)
        hit_rate = (total_hits / total_signals * 100) if total_signals > 0 else 0

        short_signals = [s for s in all_signals if s.get("duration_class") == "SHORT"]
        long_signals = [s for s in all_signals if s.get("duration_class") != "SHORT"]
        short_hits = [s for s in short_signals if s.get("hit_2x")]
        long_hits = [s for s in long_signals if s.get("hit_2x")]

        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total Signals", total_signals)
        mc2.metric("2x Hits", total_hits)
        mc3.metric("Hit Rate", f"{hit_rate:.0f}%")
        mc4.metric(
            "SHORT hits",
            f"{len(short_hits)}/{len(short_signals)}"
            if short_signals else "0",
        )
        mc5.metric(
            "LONG hits",
            f"{len(long_hits)}/{len(long_signals)}"
            if long_signals else "0",
        )

        st.divider()

        # ── 2x Hit Log ──────────────────────────────────────────────────────
        if hits:
            st.markdown(
                f"#### 2x Hits ({len(hits)})"
            )
            hit_rows = []
            for s in sorted(hits, key=lambda x: x.get("hit_2x_time", ""),
                            reverse=True):
                entry_p = s.get("signal_price", 0)
                hit_p = s.get("hit_2x_price", 0)
                roi = ((hit_p - entry_p) / entry_p * 100) if entry_p > 0 else 0
                sig_time = s.get("signal_time", "")[:16]
                hit_time = (s.get("hit_2x_time") or "")[:16]
                hit_rows.append({
                    "Symbol": s.get("symbol", "?"),
                    "Signal": s.get("signal", "?"),
                    "Duration": s.get("duration_class", "?"),
                    "Action": s.get("buy_action", "?"),
                    "Entry Price": fmt_price(entry_p),
                    "2x Price": fmt_price(hit_p),
                    "ROI": f"{roi:+.0f}%",
                    "Signal Time": sig_time,
                    "Hit Time": hit_time,
                })

            hit_df = pd.DataFrame(hit_rows)
            st.dataframe(
                hit_df.style.apply(
                    lambda row: [f"color: {GREEN}"] * len(row), axis=1
                ),
                hide_index=True,
                height=min(400, 50 + len(hit_rows) * 38),
            )

        # ── Pending Signals ──────────────────────────────────────────────────
        if pending:
            st.markdown(f"#### Pending Signals ({len(pending)})")
            pend_rows = []
            for s in sorted(pending, key=lambda x: x.get("signal_time", ""),
                            reverse=True):
                entry_p = s.get("signal_price", 0)
                peak = s.get("peak_roi_pct", 0)
                target = s.get("target_2x", 0)
                progress = (
                    min(entry_p and (s.get("peak_price", entry_p)) / target, 1.0)
                    if target > 0 else 0
                )
                pend_rows.append({
                    "Symbol": s.get("symbol", "?"),
                    "Signal": s.get("signal", "?"),
                    "Duration": s.get("duration_class", "?"),
                    "Action": s.get("buy_action", "?"),
                    "Entry Price": fmt_price(entry_p),
                    "2x Target": fmt_price(target),
                    "Peak ROI": f"{peak:+.1f}%",
                    "Progress": f"{progress:.0%}",
                    "Signal Time": s.get("signal_time", "")[:16],
                    "Last Check": s.get("checked_at", "—")[:16],
                })

            pend_df = pd.DataFrame(pend_rows)

            def color_pending(row):
                peak_str = row["Peak ROI"]
                try:
                    val = float(peak_str.replace("%", "").replace("+", ""))
                    if val > 50:
                        return [f"color: {GREEN}"] * len(row)
                    if val > 0:
                        return [f"color: {BLUE}"] * len(row)
                    return [f"color: {RED}"] * len(row)
                except (ValueError, TypeError):
                    return [""] * len(row)

            st.dataframe(
                pend_df.style.apply(color_pending, axis=1),
                hide_index=True,
                height=min(500, 50 + len(pend_rows) * 38),
            )

        st.divider()

        # ── Breakdown by signal type ─────────────────────────────────────────
        st.markdown("#### Hit Rate by Signal Type")
        for sig_type in ("STRONG DIP", "BUY DIP", "WATCH"):
            typed = [s for s in all_signals if s.get("signal") == sig_type]
            typed_hits = [s for s in typed if s.get("hit_2x")]
            rate = (len(typed_hits) / len(typed) * 100) if typed else 0
            bar_clr = signal_color(sig_type)
            st.markdown(
                f"**{sig_type}**: {len(typed_hits)}/{len(typed)} "
                f"(<b style='color:{bar_clr}'>{rate:.0f}%</b>)",
                unsafe_allow_html=True,
            )

        st.markdown("#### Hit Rate by Duration")
        for dur_type in ("SHORT", "LONG"):
            typed = [s for s in all_signals
                     if s.get("duration_class", "LONG") == dur_type]
            typed_hits = [s for s in typed if s.get("hit_2x")]
            rate = (len(typed_hits) / len(typed) * 100) if typed else 0
            bar_clr = duration_color(dur_type)
            st.markdown(
                f"**{dur_type}**: {len(typed_hits)}/{len(typed)} "
                f"(<b style='color:{bar_clr}'>{rate:.0f}%</b>)",
                unsafe_allow_html=True,
            )

        st.markdown("#### Hit Rate by Buy Action")
        for act in ("BUY NOW", "BUY ON DIP", "WAIT", "AVOID"):
            typed = [s for s in all_signals if s.get("buy_action") == act]
            typed_hits = [s for s in typed if s.get("hit_2x")]
            rate = (len(typed_hits) / len(typed) * 100) if typed else 0
            bar_clr = buy_action_color(act)
            st.markdown(
                f"**{act}**: {len(typed_hits)}/{len(typed)} "
                f"(<b style='color:{bar_clr}'>{rate:.0f}%</b>)",
                unsafe_allow_html=True,
            )

        st.divider()

        if st.button("Clear Signal History", type="secondary"):
            _save_json(SIGNALS_FILE, [])
            st.success("Signal history cleared.")
            st.rerun()

    else:
        st.info(
            "No signals recorded yet. Run a scan in the Scanner tab — "
            "all non-SKIP signals are automatically logged here."
        )


# ── Footer ───────────────────────────────────────────────────────────────────
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
