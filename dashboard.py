"""
Memecoin Swing Recovery Dashboard — v2
Run: streamlit run dashboard.py

Multi-stage scanning pipeline:
  1. Discover tokens from DexScreener (free, no key)
  2. Safety gate via rugcheck.xyz + Helius
  3. Technical analysis via Birdeye OHLCV
  4. Composite confidence scoring (0-100, A/B/C/D/F grades)

Tabs: Scanner (BUY NOW + WATCH), Watchlist, Trade Log, Signal Scoreboard
"""

import json
import os
import time
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from config import (
    DEXSCREENER_BOOSTS_TOP, DEXSCREENER_BOOSTS_LATEST,
    DEXSCREENER_PROFILES, DEXSCREENER_SEARCH, DEXSCREENER_TOKEN,
    SEARCH_QUERIES,
    WATCHLIST_FILE, TRADES_FILE, SIGNALS_FILE,
    GRADE_A_MIN, GRADE_B_MIN,
)
from token_filter import check_token_safety, SafetyResult
from technical_analysis import run_ta, TAResult
from confidence_scorer import compute_confidence, compute_entry_exit, ConfidenceScore

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN = "#00e676"
RED = "#ff1744"
YELLOW = "#ffd600"
BLUE = "#2979ff"
ORANGE = "#ff9100"
PURPLE = "#e040fb"
GREY = "#9e9e9e"

GRADE_COLORS = {"A": GREEN, "B": BLUE, "C": YELLOW, "D": ORANGE, "F": RED}

# ── Persistence ──────────────────────────────────────────────────────────────
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


# ── DexScreener helpers ──────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def _fetch_endpoint(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


@st.cache_data(ttl=120)
def _fetch_search(query):
    try:
        r = requests.get(DEXSCREENER_SEARCH, params={"q": query}, timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def fetch_trending_tokens():
    """Combine DexScreener endpoints for a broad token pool."""
    pool = []
    seen = set()

    for url in (DEXSCREENER_BOOSTS_TOP, DEXSCREENER_BOOSTS_LATEST,
                DEXSCREENER_PROFILES):
        for tok in _fetch_endpoint(url):
            addr = tok.get("tokenAddress")
            chain = tok.get("chainId")
            if addr and addr not in seen and (not chain or chain == "solana"):
                seen.add(addr)
                pool.append({
                    "tokenAddress": addr,
                    "chainId": chain or "solana",
                    "boosts": tok.get("totalAmount") or tok.get("amount") or 0,
                })

    for q in SEARCH_QUERIES:
        for pair in _fetch_search(q):
            if pair.get("chainId") != "solana":
                continue
            base = pair.get("baseToken") or {}
            addr = base.get("address")
            if addr and addr not in seen:
                seen.add(addr)
                pool.append({
                    "tokenAddress": addr,
                    "chainId": "solana",
                    "boosts": 0,
                })

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
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{address}", timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def _safe_float(obj, *keys, default=0.0):
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
    sol = [p for p in pairs if p.get("chainId") == "solana"]
    return max(sol, key=lambda p: _safe_float(p, "volume", "h24")) if sol else None


# ── Formatting ───────────────────────────────────────────────────────────────
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


# ── Signal logging + 2x tracker ─────────────────────────────────────────────
def log_signals(results):
    signals = _load_json(SIGNALS_FILE)
    existing_keys = {(s.get("address", ""), s.get("signal_time", "")[:10])
                     for s in signals}
    now = datetime.now(timezone.utc).isoformat()
    added = 0

    for r in results:
        if r.get("grade") in ("D", "F"):
            continue
        key = (r["address"], now[:10])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        signals.append({
            "address": r["address"],
            "symbol": r["symbol"],
            "grade": r["grade"],
            "confidence": r["confidence"],
            "signal_price": r["price_usd"],
            "signal_time": now,
            "target_2x": r["price_usd"] * 2,
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


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-STAGE SCAN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
def run_full_scan():
    """
    Stage 1: DexScreener discovery → pre-filter (Solana, basic volume/dip)
    Stage 2: Safety gate (rugcheck + Helius)
    Stage 3: Technical analysis (Birdeye OHLCV)
    Stage 4: Confidence scoring + grading
    """
    stats = {
        "discovered": 0,
        "pre_filtered": 0,
        "safety_passed": 0,
        "safety_failed": 0,
        "ta_analyzed": 0,
        "grade_a": 0,
        "grade_b": 0,
        "grade_c": 0,
        "grade_d": 0,
    }

    # ── Stage 1: Discover ────────────────────────────────────────────────
    stage_text = st.empty()
    stage_text.markdown("**Stage 1/4:** Fetching tokens from DexScreener...")
    tokens = fetch_trending_tokens()
    stats["discovered"] = len(tokens)

    if not tokens:
        stage_text.error("No tokens found from DexScreener.")
        return [], stats

    # ── Pre-filter: get pair data, keep Solana with dip pattern ──────────
    stage_text.markdown(
        f"**Stage 1/4:** Pre-filtering {len(tokens)} tokens..."
    )
    progress = st.progress(0)
    candidates = []

    for i, tok in enumerate(tokens):
        progress.progress((i + 1) / len(tokens))
        addr = tok["tokenAddress"]
        pairs = fetch_pair_data(addr)
        best = _best_solana_pair(pairs)
        if not best:
            continue

        h1 = _safe_float(best, "priceChange", "h1")
        h6 = _safe_float(best, "priceChange", "h6")
        h24 = _safe_float(best, "priceChange", "h24")
        vol_24h = _safe_float(best, "volume", "h24")
        liq = _safe_float(best, "liquidity", "usd")

        has_dip = h6 < -5 or h24 < -8
        has_recovery = h1 > -2
        has_volume = vol_24h > 30_000

        if not (has_dip and has_volume):
            continue

        base = best.get("baseToken") or {}
        candidates.append({
            "address": addr,
            "symbol": base.get("symbol", "?"),
            "name": base.get("name", "?"),
            "pair_data": best,
            "boosts": tok.get("boosts", 0),
            "h1": h1, "h6": h6, "h24": h24,
            "price_usd": _safe_float(best, "priceUsd"),
            "fdv": _safe_float(best, "fdv"),
            "vol_5m": _safe_float(best, "volume", "m5"),
            "vol_h1": _safe_float(best, "volume", "h1"),
            "vol_h6": _safe_float(best, "volume", "h6"),
            "vol_24h": vol_24h,
            "liquidity": liq,
            "txns": best.get("txns") or {},
            "pair_url": best.get("url", ""),
        })
        time.sleep(0.1)

    progress.empty()
    stats["pre_filtered"] = len(candidates)

    if not candidates:
        stage_text.info("No tokens passed pre-filtering (need dip + recovery + volume).")
        return [], stats

    # ── Stage 2: Safety gate ─────────────────────────────────────────────
    stage_text.markdown(
        f"**Stage 2/4:** Running safety checks on {len(candidates)} tokens "
        "(rugcheck + Helius)..."
    )
    progress = st.progress(0)
    safe_tokens = []

    for i, c in enumerate(candidates):
        progress.progress((i + 1) / len(candidates))
        safety = check_token_safety(c["address"], c["pair_data"])
        c["safety"] = safety

        if safety.passed:
            stats["safety_passed"] += 1
            safe_tokens.append(c)
        else:
            stats["safety_failed"] += 1

        time.sleep(0.3)

    progress.empty()

    if not safe_tokens:
        stage_text.info(
            f"No tokens passed safety ({stats['safety_failed']} blocked). "
            "This means mint/freeze authority or rug risk flagged every candidate."
        )
        return [], stats

    # ── Stage 3: Technical analysis ──────────────────────────────────────
    stage_text.markdown(
        f"**Stage 3/4:** Running TA on {len(safe_tokens)} tokens (Birdeye OHLCV)..."
    )
    progress = st.progress(0)

    for i, c in enumerate(safe_tokens):
        progress.progress((i + 1) / len(safe_tokens))
        ta = run_ta(c["address"], c["price_usd"])
        c["ta"] = ta
        stats["ta_analyzed"] += 1
        time.sleep(0.5)

    progress.empty()

    # ── Stage 4: Confidence scoring ──────────────────────────────────────
    stage_text.markdown("**Stage 4/4:** Scoring and grading...")
    results = []

    for c in safe_tokens:
        boosts = c.get("boosts", 0)
        try:
            boosts = int(boosts)
        except (ValueError, TypeError):
            boosts = 0

        cs = compute_confidence(
            c["safety"], c["ta"], c["pair_data"],
            txns=c["txns"], boosts=boosts,
            current_price=c["price_usd"],
        )
        entry_exit = compute_entry_exit(c["price_usd"], c["ta"], cs)

        results.append({
            "address": c["address"],
            "symbol": c["symbol"],
            "name": c["name"],
            "price_usd": c["price_usd"],
            "fdv": c["fdv"],
            "h1": c["h1"],
            "h6": c["h6"],
            "h24": c["h24"],
            "vol_5m": c["vol_5m"],
            "vol_h1": c["vol_h1"],
            "vol_h6": c["vol_h6"],
            "vol_24h": c["vol_24h"],
            "liquidity": c["liquidity"],
            "pair_url": c["pair_url"],
            "txns": c["txns"],
            "boosts": boosts,
            "pair_data": c["pair_data"],
            # Scoring
            "confidence": cs.total,
            "grade": cs.grade,
            "cs": cs,
            "entry_exit": entry_exit,
            "safety": c["safety"],
            "ta": c["ta"],
        })

    results.sort(key=lambda r: -r["confidence"])

    for r in results:
        g = r["grade"]
        if g == "A":
            stats["grade_a"] += 1
        elif g == "B":
            stats["grade_b"] += 1
        elif g == "C":
            stats["grade_c"] += 1
        else:
            stats["grade_d"] += 1

    stage_text.empty()
    return results, stats


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Memecoin Swing Scanner v2", layout="wide")
st.markdown(
    "<style>"
    ".signal-tag{display:inline-block;padding:4px 12px;border-radius:16px;"
    "font-weight:700;font-size:13px;letter-spacing:.5px}"
    ".grade-badge{display:inline-block;padding:6px 16px;border-radius:20px;"
    "font-weight:900;font-size:18px;letter-spacing:1px}"
    ".positive{color:#00e676}.negative{color:#ff1744}"
    ".score-bar{height:8px;border-radius:4px;margin:2px 0}"
    "</style>",
    unsafe_allow_html=True,
)

st.markdown("# Memecoin Swing Recovery Scanner v2")
st.caption(
    "Multi-stage pipeline: DexScreener discovery → Rugcheck safety → "
    "Birdeye TA → Confidence scoring"
)

tab_scanner, tab_watchlist, tab_tradelog, tab_scoreboard = st.tabs(
    ["Scanner", "Watchlist", "Trade Log", "Signal Scoreboard"]
)


# ── Token card renderer (must be defined before tabs call it) ────────────────
def _render_token_card(r, compact=False):
    """Render a single token card with all metrics."""
    cs = r["cs"]
    ta = r["ta"]
    safety = r["safety"]
    ee = r["entry_exit"]
    g_clr = GRADE_COLORS.get(r["grade"], GREY)

    c1, c2, c3, c4 = st.columns([3, 2, 2, 4])

    with c1:
        st.markdown(
            f"<span class='grade-badge' style='background:{g_clr}20;"
            f"color:{g_clr};border:2px solid {g_clr}'>"
            f"{r['grade']}</span> "
            f"**{r['symbol']}** · {r['name'][:25]}",
            unsafe_allow_html=True,
        )
        st.caption(f"`{r['address'][:28]}...`")

    with c2:
        st.metric("Price", fmt_price(r["price_usd"]))
        if ta.ath > 0:
            st.caption(
                f"ATH: {fmt_price(ta.ath)} · "
                f"Retrace: {ta.retracement_from_ath_pct:.0f}%"
            )

    with c3:
        st.metric(
            f"Score {cs.total:.0f}/100",
            f"{r['grade']}-Grade",
        )
        h1c = "positive" if r["h1"] >= 0 else "negative"
        h6c = "positive" if r["h6"] >= 0 else "negative"
        h24c = "positive" if r["h24"] >= 0 else "negative"
        st.markdown(
            f"1h: <b class='{h1c}'>{r['h1']:+.1f}%</b> · "
            f"6h: <b class='{h6c}'>{r['h6']:+.1f}%</b> · "
            f"24h: <b class='{h24c}'>{r['h24']:+.1f}%</b>",
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(f"*{cs.summary}*")
        if cs.strengths:
            st.caption(" · ".join(cs.strengths[:3]))

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("Add to Watchlist", key=f"add_{r['address']}",
                         use_container_width=True):
                wl = _load_json(WATCHLIST_FILE)
                if not any(w["address"] == r["address"] for w in wl):
                    wl.append({
                        "address": r["address"],
                        "symbol": r["symbol"],
                        "name": r["name"],
                        "entry_price": r["price_usd"],
                        "target_2x": r["price_usd"] * 2,
                        "grade": r["grade"],
                        "confidence": cs.total,
                        "pair_url": r["pair_url"],
                        "added_at": datetime.now(timezone.utc).isoformat(),
                    })
                    _save_json(WATCHLIST_FILE, wl)
                    st.success(f"Added {r['symbol']}")
                else:
                    st.info("Already in watchlist")
        with btn_c2:
            if r.get("pair_url"):
                st.link_button("DexScreener", r["pair_url"],
                               use_container_width=True)

    if compact:
        st.divider()
        return

    with st.expander(
        f"Full Analysis: {r['symbol']} — Entry/Exit · TA · Safety · Score Breakdown"
    ):
        d1, d2, d3 = st.columns(3)

        with d1:
            st.markdown("##### Entry & Exit Levels")
            if ee:
                st.markdown(
                    f"**Entry Zone:** {fmt_price(ee.get('entry_low', 0))} — "
                    f"{fmt_price(ee.get('entry_high', 0))}"
                )
                sl = ee.get("stop_loss", 0)
                st.markdown(
                    f"**Stop-Loss:** {fmt_price(sl)} "
                    f"(-{ee.get('stop_loss_pct', 0)}%)"
                )
                st.markdown(f"**Target 2x:** {fmt_price(ee.get('target_2x', 0))}")
                st.markdown(f"**Target 3x:** {fmt_price(ee.get('target_3x', 0))}")
                if ee.get("nearest_support"):
                    st.caption(f"Support: {fmt_price(ee['nearest_support'])}")
                if ee.get("nearest_resistance"):
                    st.caption(f"Resistance: {fmt_price(ee['nearest_resistance'])}")

            st.markdown("---")
            st.markdown("##### Market Stats")
            st.caption(
                f"MCap: {fmt_usd(r['fdv'])} · Liq: {fmt_usd(r['liquidity'])}\n\n"
                f"Vol 5m: {fmt_usd(r['vol_5m'])} · 1h: {fmt_usd(r['vol_h1'])} · "
                f"24h: {fmt_usd(r['vol_24h'])}"
            )

        with d2:
            st.markdown("##### Technical Analysis")
            if ta.available:
                st.markdown(
                    f"**Fibonacci:** Near {ta.nearest_fib_level} level "
                    f"({ta.fib_proximity_pct:.1f}% away)"
                )
                if ta.fib_levels:
                    fib_parts = []
                    for lvl in (0.236, 0.382, 0.5, 0.618, 0.786):
                        p = ta.fib_levels.get(lvl)
                        if p:
                            fib_parts.append(f"{lvl}: {fmt_price(p)}")
                    st.caption(" · ".join(fib_parts))

                rsi_clr = GREEN if ta.rsi_signal == "OVERSOLD_BOUNCING" else (
                    BLUE if ta.rsi_signal == "OVERSOLD" else YELLOW
                )
                st.markdown(
                    f"**RSI:** 1m={ta.rsi_1m:.0f} · 5m={ta.rsi_5m:.0f} — "
                    f"<b style='color:{rsi_clr}'>{ta.rsi_signal}</b>",
                    unsafe_allow_html=True,
                )

                vwap_clr = GREEN if ta.vwap_reclaim else (
                    BLUE if ta.price_vs_vwap_pct > 0 else RED
                )
                vwap_txt = "RECLAIMING" if ta.vwap_reclaim else (
                    f"{'Above' if ta.price_vs_vwap_pct > 0 else 'Below'} "
                    f"({ta.price_vs_vwap_pct:+.1f}%)"
                )
                st.markdown(
                    f"**VWAP:** {fmt_price(ta.vwap)} — "
                    f"<b style='color:{vwap_clr}'>{vwap_txt}</b>",
                    unsafe_allow_html=True,
                )

                vt_clr = GREEN if ta.volume_trend == "STRONG_RECOVERY" else (
                    BLUE if ta.volume_trend == "HEALTHY" else RED
                )
                st.markdown(
                    f"**Volume Profile:** "
                    f"<b style='color:{vt_clr}'>{ta.volume_trend}</b> "
                    f"({ta.volume_recovery_ratio:.1f}x recovery vs dump)",
                    unsafe_allow_html=True,
                )

                ms_clr = GREEN if ta.momentum_signal == "STRONG_REVERSAL" else (
                    BLUE if ta.momentum_signal == "WEAK_REVERSAL" else RED
                )
                st.markdown(
                    f"**Momentum:** "
                    f"<b style='color:{ms_clr}'>{ta.momentum_signal}</b> "
                    f"({ta.momentum_shift:.2f}x)",
                    unsafe_allow_html=True,
                )

                if ta.support_levels:
                    st.caption(
                        "Support: " +
                        " · ".join(fmt_price(s) for s in ta.support_levels)
                    )
                if ta.resistance_levels:
                    st.caption(
                        "Resistance: " +
                        " · ".join(fmt_price(r_lvl) for r_lvl in ta.resistance_levels)
                    )
            else:
                st.caption(
                    "Birdeye OHLCV unavailable — TA scores use defaults. "
                    "Ensure BIRDEYE_API_KEY is set."
                )

        with d3:
            st.markdown("##### Safety Checks")
            for reason in safety.pass_reasons:
                st.markdown(f"<span style='color:{GREEN}'>✓</span> {reason}",
                            unsafe_allow_html=True)
            for reason in safety.fail_reasons:
                st.markdown(f"<span style='color:{RED}'>✗</span> {reason}",
                            unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("##### Confidence Breakdown")
            components = [
                ("Fib proximity", cs.fib_score, 20),
                ("RSI reversal", cs.rsi_score, 15),
                ("Volume recovery", cs.volume_score, 20),
                ("Sentiment", cs.sentiment_score, 15),
                ("Holders", cs.holder_score, 10),
                ("VWAP", cs.vwap_score, 10),
                ("Momentum", cs.pattern_score, 10),
            ]
            for label, score, weight in components:
                bar_clr = GREEN if score >= 70 else (BLUE if score >= 50 else (
                    YELLOW if score >= 30 else RED
                ))
                st.markdown(
                    f"{label} ({weight}%): **{score:.0f}**/100 "
                    f"<span style='color:{bar_clr}'>{'█' * int(score / 10)}"
                    f"{'░' * (10 - int(score / 10))}</span>",
                    unsafe_allow_html=True,
                )

            if cs.weaknesses:
                st.caption("Weaknesses: " + " · ".join(cs.weaknesses[:3]))

    st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scanner:
    scan_clicked = st.button("Run Full Scan", type="primary", use_container_width=True)
    st.caption(
        "Scans DexScreener trending → filters for Solana dip recoveries → "
        "safety checks → technical analysis → grades A through F"
    )

    if scan_clicked:
        results, stats = run_full_scan()

        _, sig_added = log_signals(results)
        if sig_added:
            st.toast(f"Logged {sig_added} new signal(s) to scoreboard")

        st.session_state["scan_results"] = results
        st.session_state["scan_stats"] = stats
        st.session_state["scan_time"] = datetime.now(timezone.utc).strftime(
            "%H:%M:%S UTC"
        )

    results = st.session_state.get("scan_results", [])
    stats = st.session_state.get("scan_stats", {})
    scan_time = st.session_state.get("scan_time", "")

    if stats:
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Discovered", stats.get("discovered", 0))
        s2.metric("Pre-filtered", stats.get("pre_filtered", 0))
        s3.metric("Safety passed", stats.get("safety_passed", 0))
        s4.metric("Safety blocked", stats.get("safety_failed", 0))
        s5.metric("Grade A", stats.get("grade_a", 0))
        s6.metric("Grade B", stats.get("grade_b", 0))

    if results:
        grade_a = [r for r in results if r["grade"] == "A"]
        grade_b = [r for r in results if r["grade"] == "B"]
        grade_c = [r for r in results if r["grade"] == "C"]

        # ── BUY NOW section (A-grade) ────────────────────────────────────
        if grade_a:
            st.markdown(
                f"## BUY NOW — A-Grade Tokens ({len(grade_a)})",
            )
            st.caption(
                f"Confidence {GRADE_A_MIN}+ | Strong setups with aligned indicators | "
                f"Scanned at {scan_time}"
            )
            for r in grade_a:
                _render_token_card(r)
        else:
            st.info(
                f"No A-grade tokens found this scan ({scan_time}). "
                "A-grade requires strong fib alignment, oversold RSI bouncing, "
                "and healthy volume recovery."
            )

        st.divider()

        # ── WATCH LIST section (B-grade) ─────────────────────────────────
        if grade_b:
            st.markdown(
                f"## WATCH LIST — B-Grade Tokens ({len(grade_b)})",
            )
            st.caption("Approaching good entries — monitor for upgrade to A-grade")
            for r in grade_b:
                _render_token_card(r)
        else:
            st.info("No B-grade tokens this scan.")

        # ── C-grade (collapsed) ──────────────────────────────────────────
        if grade_c:
            with st.expander(f"C-Grade tokens ({len(grade_c)}) — lower confidence"):
                for r in grade_c:
                    _render_token_card(r, compact=True)

    elif not scan_clicked:
        st.info(
            "Click **Run Full Scan** to discover, filter, analyze, and grade tokens."
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
                        "h1": h1, "h6": h6, "h24": h24,
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
                grade = item.get("grade", "?")
                g_clr = GRADE_COLORS.get(grade, GREY)
                st.markdown(
                    f"<span class='grade-badge' style='background:{g_clr}20;"
                    f"color:{g_clr};border:1px solid {g_clr}'>{grade}</span> "
                    f"**{item['symbol']}**",
                    unsafe_allow_html=True,
                )

            with c2:
                st.metric("Entry", fmt_price(entry))

            with c3:
                st.metric(
                    "Current", fmt_price(current_price),
                    delta=f"{change_pct:+.1f}%",
                    delta_color="normal" if change_pct >= 0 else "inverse",
                )

            with c4:
                st.markdown(f"**2x Target:** {fmt_price(target)}")
                st.progress(progress_pct, text=f"{progress_pct:.0%} to 2x")
                st.caption(f"1h: {h1:+.1f}% · 6h: {h6:+.1f}% · 24h: {h24:+.1f}%")

            with c5:
                if pair_url:
                    st.link_button("DexScreener", pair_url,
                                   key=f"wl_dex_{item['address']}_{i}",
                                   use_container_width=True)
                if st.button("Remove", key=f"rm_{item['address']}_{i}",
                             use_container_width=True):
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

    with st.expander("Log a new trade", expanded=False):
        with st.form("trade_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                t_symbol = st.text_input("Token symbol", placeholder="e.g. BONK")
                t_address = st.text_input("Token address", placeholder="mint address")
                t_entry_price = st.number_input(
                    "Entry price (USD)", min_value=0.0, format="%.12f", value=0.0,
                )
            with fc2:
                t_size_sol = st.number_input(
                    "Position size (SOL)", min_value=0.0, value=1.0, step=0.5,
                )
                t_side = st.selectbox("Side", ["BUY", "SELL"])
                t_notes = st.text_input("Notes", placeholder="e.g. Grade A signal")

            submitted = st.form_submit_button("Log Trade", type="primary")
            if submitted and t_symbol and t_entry_price > 0:
                trades.append({
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
                })
                _save_json(TRADES_FILE, trades)
                st.success(
                    f"Logged {t_side} {t_symbol.upper()} @ {fmt_price(t_entry_price)}"
                )
                st.rerun()

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
                "Exit price (USD)", min_value=0.0, format="%.12f",
                value=0.0, key="close_price",
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
                                / t["entry_price"] * 100
                            )
                            t["pnl_sol"] = t["size_sol"] * t["pnl_pct"] / 100
                        break
                _save_json(TRADES_FILE, trades)
                st.success(f"Closed {target_trade['symbol']}!")
                st.rerun()

    st.divider()

    if trades:
        st.markdown("#### Trade History")
        rows = []
        for t in reversed(trades):
            pnl_pct = t.get("pnl_pct")
            pnl_sol = t.get("pnl_sol")
            rows.append({
                "Symbol": t.get("symbol", "?"),
                "Side": t.get("side", "BUY"),
                "Entry": fmt_price(t.get("entry_price", 0)),
                "Exit": fmt_price(t["exit_price"]) if t.get("exit_price") else "—",
                "Size SOL": t.get("size_sol", 0),
                "PnL %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
                "PnL SOL": f"{pnl_sol:+.4f}" if pnl_sol is not None else "—",
                "Status": t.get("status", "OPEN"),
                "Notes": t.get("notes", ""),
                "Opened": t.get("opened_at", "—")[:16],
            })

        df = pd.DataFrame(rows)

        def color_status(row):
            if row["Status"] == "OPEN":
                return [f"color: {BLUE}"] * len(row)
            if row["Status"] == "CLOSED" and row["PnL SOL"] != "—":
                try:
                    clr = GREEN if float(row["PnL SOL"]) > 0 else RED
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
        st.info("No trades logged yet.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIGNAL SCOREBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scoreboard:
    st.markdown("### Signal Scoreboard — 2x ROI Tracker")
    st.caption(
        "Every A/B/C-grade signal is logged. Live price checks track 2x hits."
    )

    all_signals = _load_json(SIGNALS_FILE)

    sb_c1, sb_c2 = st.columns([1, 3])
    with sb_c1:
        check_clicked = st.button(
            "Check 2x Hits Now", type="primary", use_container_width=True,
        )
    with sb_c2:
        st.caption("Fetches live prices for all open signals and marks 2x hits.")

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

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Signals", total_signals)
        mc2.metric("2x Hits", total_hits)
        mc3.metric("Hit Rate", f"{hit_rate:.0f}%")

        st.divider()

        if hits:
            st.markdown(f"#### 2x Hits ({len(hits)})")
            hit_rows = []
            for s in sorted(hits, key=lambda x: x.get("hit_2x_time", ""),
                            reverse=True):
                entry_p = s.get("signal_price", 0)
                hit_p = s.get("hit_2x_price", 0)
                roi = ((hit_p - entry_p) / entry_p * 100) if entry_p > 0 else 0
                hit_rows.append({
                    "Symbol": s.get("symbol", "?"),
                    "Grade": s.get("grade", "?"),
                    "Confidence": s.get("confidence", 0),
                    "Entry": fmt_price(entry_p),
                    "2x Price": fmt_price(hit_p),
                    "ROI": f"{roi:+.0f}%",
                    "Signal Time": s.get("signal_time", "")[:16],
                    "Hit Time": (s.get("hit_2x_time") or "")[:16],
                })
            st.dataframe(
                pd.DataFrame(hit_rows).style.apply(
                    lambda row: [f"color: {GREEN}"] * len(row), axis=1
                ),
                hide_index=True,
                height=min(400, 50 + len(hit_rows) * 38),
            )

        if pending:
            st.markdown(f"#### Pending Signals ({len(pending)})")
            pend_rows = []
            for s in sorted(pending, key=lambda x: x.get("signal_time", ""),
                            reverse=True):
                entry_p = s.get("signal_price", 0)
                peak = s.get("peak_roi_pct", 0)
                target = s.get("target_2x", 0)
                progress = (
                    min((s.get("peak_price", entry_p)) / target, 1.0)
                    if target > 0 and entry_p > 0 else 0
                )
                pend_rows.append({
                    "Symbol": s.get("symbol", "?"),
                    "Grade": s.get("grade", "?"),
                    "Confidence": s.get("confidence", 0),
                    "Entry": fmt_price(entry_p),
                    "Target": fmt_price(target),
                    "Peak ROI": f"{peak:+.1f}%",
                    "Progress": f"{progress:.0%}",
                    "Signal Time": s.get("signal_time", "")[:16],
                })

            def color_pending(row):
                try:
                    val = float(row["Peak ROI"].replace("%", "").replace("+", ""))
                    clr = GREEN if val > 50 else (BLUE if val > 0 else RED)
                    return [f"color: {clr}"] * len(row)
                except (ValueError, TypeError):
                    return [""] * len(row)

            st.dataframe(
                pd.DataFrame(pend_rows).style.apply(color_pending, axis=1),
                hide_index=True,
                height=min(500, 50 + len(pend_rows) * 38),
            )

        st.divider()

        st.markdown("#### Hit Rate by Grade")
        for grade in ("A", "B", "C"):
            typed = [s for s in all_signals if s.get("grade") == grade]
            typed_hits = [s for s in typed if s.get("hit_2x")]
            rate = (len(typed_hits) / len(typed) * 100) if typed else 0
            g_clr = GRADE_COLORS.get(grade, GREY)
            st.markdown(
                f"**Grade {grade}**: {len(typed_hits)}/{len(typed)} "
                f"(<b style='color:{g_clr}'>{rate:.0f}%</b>)",
                unsafe_allow_html=True,
            )

        st.divider()
        if st.button("Clear Signal History", type="secondary"):
            _save_json(SIGNALS_FILE, [])
            st.success("Signal history cleared.")
            st.rerun()

    else:
        st.info(
            "No signals recorded yet. Run a scan — all A/B/C-grade signals "
            "are automatically logged here."
        )


# ── Footer ───────────────────────────────────────────────────────────────────
st.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
