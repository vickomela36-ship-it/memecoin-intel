"""
Memecoin Intel Dashboard — v2
Run: streamlit run dashboard.py

Sections:
  1. Memecoin Swing Scanner (Scanner, Watchlist, Trade Log, Signal Scoreboard)
  2. Crypto Prediction Plays (BTC, ETH, SOL, DOGE daily signals + Polymarket edge)
  3. World Cup & Football Value Plays (ELO predictions + odds comparison)
"""

import json
import os
import time
import math
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    DEXSCREENER_BOOSTS_TOP, DEXSCREENER_BOOSTS_LATEST,
    DEXSCREENER_PROFILES, DEXSCREENER_SEARCH, DEXSCREENER_TOKEN,
    SEARCH_QUERIES,
    WATCHLIST_FILE, TRADES_FILE, SIGNALS_FILE, DEGEN_SIGNALS_FILE,
    CRYPTO_PREDICTIONS_FILE,
    GRADE_A_MIN, GRADE_B_MIN,
    CRYPTO_CACHE_SECONDS, CRYPTO_STALE_SECONDS,
)
from token_filter import check_token_safety, SafetyResult
from technical_analysis import run_ta, TAResult
from confidence_scorer import (
    compute_confidence, compute_entry_exit, compute_moonshot,
    ConfidenceScore, MoonshotScore,
)
from crypto_predictions import (
    get_all_predictions, get_prediction_history, log_prediction,
    CryptoPrediction, SignalDetail, PredictionMarketEdge,
)
from football_predictions import (
    get_match_predictions, get_available_competitions,
    MatchPrediction,
)

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN = "#00e676"
RED = "#ff1744"
YELLOW = "#ffd600"
BLUE = "#2979ff"
ORANGE = "#ff9100"
PURPLE = "#e040fb"
GREY = "#9e9e9e"

GRADE_COLORS = {"A": GREEN, "B": BLUE, "C": YELLOW, "D": ORANGE, "F": RED}
MOON_COLORS = {
    "100x MOONSHOT": PURPLE,
    "10x RUNNER": GREEN,
    "5x POTENTIAL": BLUE,
    "3x POSSIBLE": YELLOW,
    "LOW POTENTIAL": GREY,
}
RISK_COLORS = {
    "EXTREME": RED,
    "VERY HIGH": ORANGE,
    "HIGH": YELLOW,
    "MODERATE": BLUE,
}

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
def _fetch_pair_batch(addresses_key):
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{addresses_key}", timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def fetch_pair_data_batch(address_list):
    batches = []
    for i in range(0, len(address_list), 30):
        batch = address_list[i:i + 30]
        batches.append(",".join(batch))

    all_pairs = {}
    for key in batches:
        for pair in _fetch_pair_batch(key):
            base = pair.get("baseToken") or {}
            addr = base.get("address")
            if addr:
                if addr not in all_pairs:
                    all_pairs[addr] = []
                all_pairs[addr].append(pair)
    return all_pairs


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


# ── Degen signal logging + 5x/10x tracker ─────────────────────────────────
def log_degen_signals(degen_results):
    signals = _load_json(DEGEN_SIGNALS_FILE)
    existing_keys = {(s.get("address", ""), s.get("signal_time", "")[:10])
                     for s in signals}
    now = datetime.now(timezone.utc).isoformat()
    added = 0

    for r in degen_results:
        moon = r.get("moonshot")
        if not moon or moon.total < 40:
            continue
        key = (r["address"], now[:10])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        signals.append({
            "address": r["address"],
            "symbol": r["symbol"],
            "tier": moon.tier,
            "multiplier_target": moon.multiplier_target,
            "moon_score": moon.total,
            "risk_level": moon.risk_level,
            "signal_price": r["price_usd"],
            "fdv_at_signal": r["fdv"],
            "signal_time": now,
            "target_5x": r["price_usd"] * 5,
            "target_10x": r["price_usd"] * 10,
            "target_100x": r["price_usd"] * 100,
            "hit_5x": False,
            "hit_5x_time": None,
            "hit_10x": False,
            "hit_10x_time": None,
            "hit_100x": False,
            "hit_100x_time": None,
            "peak_price": r["price_usd"],
            "peak_roi_pct": 0.0,
            "peak_multiplier": 1.0,
            "checked_at": now,
        })
        added += 1

    if added:
        _save_json(DEGEN_SIGNALS_FILE, signals)
    return signals, added


def check_degen_hits():
    signals = _load_json(DEGEN_SIGNALS_FILE)
    if not signals:
        return signals, 0, 0

    updated = False
    new_hits = 0
    checked = 0

    for s in signals:
        if s.get("hit_100x"):
            continue

        pairs = fetch_pair_data(s["address"])
        best = _best_solana_pair(pairs)
        if not best:
            continue
        checked += 1

        current = _safe_float(best, "priceUsd")
        entry = s.get("signal_price", 0)
        if entry <= 0:
            continue

        if current > s.get("peak_price", 0):
            s["peak_price"] = current
            s["peak_roi_pct"] = round((current - entry) / entry * 100, 2)
            s["peak_multiplier"] = round(current / entry, 2)
            updated = True

        s["checked_at"] = datetime.now(timezone.utc).isoformat()

        if not s.get("hit_5x") and current >= s.get("target_5x", 0):
            s["hit_5x"] = True
            s["hit_5x_time"] = datetime.now(timezone.utc).isoformat()
            new_hits += 1
            updated = True

        if not s.get("hit_10x") and current >= s.get("target_10x", 0):
            s["hit_10x"] = True
            s["hit_10x_time"] = datetime.now(timezone.utc).isoformat()
            new_hits += 1
            updated = True

        if not s.get("hit_100x") and current >= s.get("target_100x", 0):
            s["hit_100x"] = True
            s["hit_100x_time"] = datetime.now(timezone.utc).isoformat()
            new_hits += 1
            updated = True

    if updated:
        _save_json(DEGEN_SIGNALS_FILE, signals)
    return signals, new_hits, checked


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-STAGE SCAN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
def run_full_scan():
    stats = {
        "discovered": 0, "pre_filtered": 0,
        "safety_passed": 0, "safety_failed": 0, "ta_analyzed": 0,
        "grade_a": 0, "grade_b": 0, "grade_c": 0, "grade_d": 0,
    }

    stage_text = st.empty()
    stage_text.markdown("**Stage 1/4:** Fetching tokens from DexScreener...")
    tokens = fetch_trending_tokens()
    stats["discovered"] = len(tokens)

    if not tokens:
        stage_text.error("No tokens found from DexScreener.")
        return [], [], stats

    stage_text.markdown(f"**Stage 1/4:** Pre-filtering {len(tokens)} tokens...")
    addr_list = [tok["tokenAddress"] for tok in tokens]
    boosts_map = {tok["tokenAddress"]: tok.get("boosts", 0) for tok in tokens}
    all_pairs = fetch_pair_data_batch(addr_list)

    candidates = []
    for addr, pairs in all_pairs.items():
        best = _best_solana_pair(pairs)
        if not best:
            continue

        h1 = _safe_float(best, "priceChange", "h1")
        h6 = _safe_float(best, "priceChange", "h6")
        h24 = _safe_float(best, "priceChange", "h24")
        vol_24h = _safe_float(best, "volume", "h24")
        liq = _safe_float(best, "liquidity", "usd")

        has_dip = h6 < -5 or h24 < -8
        has_volume = vol_24h > 30_000

        if not (has_dip and has_volume):
            continue

        base = best.get("baseToken") or {}
        candidates.append({
            "address": addr,
            "symbol": base.get("symbol", "?"),
            "name": base.get("name", "?"),
            "pair_data": best,
            "boosts": boosts_map.get(addr, 0),
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

    stats["pre_filtered"] = len(candidates)

    if not candidates:
        stage_text.info("No tokens passed pre-filtering.")
        return [], [], stats

    # ── Stage 2: Safety gate (parallel) ─────────────────────────────────
    stage_text.markdown(
        f"**Stage 2/4:** Safety checks on {len(candidates)} tokens..."
    )
    progress = st.progress(0)
    safe_tokens = []
    risky_tokens = []

    def _run_safety(c):
        return c, check_token_safety(c["address"], c["pair_data"])

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_run_safety, c) for c in candidates]
        safety_results = []
        for fut in as_completed(futures):
            safety_results.append(fut.result())
            progress.progress(len(safety_results) / len(candidates))

    for c, safety in safety_results:
        c["safety"] = safety
        if safety.passed:
            stats["safety_passed"] += 1
            safe_tokens.append(c)
        else:
            stats["safety_failed"] += 1
            risky_tokens.append(c)

    progress.empty()

    # ── Stage 3: Technical analysis (parallel) ──────────────────────────
    risky_tokens.sort(key=lambda c: min(c["h6"], c["h24"]))
    degen_candidates = risky_tokens[:20]
    ta_pool = safe_tokens + degen_candidates

    if ta_pool:
        stage_text.markdown(
            f"**Stage 3/4:** TA on {len(ta_pool)} tokens (Birdeye OHLCV)..."
        )
        progress = st.progress(0)

        def _run_ta(c):
            return c, run_ta(c["address"], c["price_usd"])

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(_run_ta, c) for c in ta_pool]
            ta_results = []
            for fut in as_completed(futures):
                ta_results.append(fut.result())
                progress.progress(len(ta_results) / len(ta_pool))

        for c, ta in ta_results:
            c["ta"] = ta
            stats["ta_analyzed"] += 1

        progress.empty()

    # ── Stage 4: Confidence scoring ──────────────────────────────────────
    stage_text.markdown("**Stage 4/4:** Scoring and grading...")
    results = []
    degen_results = []

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
        moon = compute_moonshot(
            c["price_usd"], c["fdv"], c["h1"], c["h6"], c["h24"],
            c["vol_5m"], c["vol_h1"], c["vol_24h"], c["liquidity"],
            c["txns"], c["ta"], c["safety"],
        )

        entry = {
            "address": c["address"], "symbol": c["symbol"], "name": c["name"],
            "price_usd": c["price_usd"], "fdv": c["fdv"],
            "h1": c["h1"], "h6": c["h6"], "h24": c["h24"],
            "vol_5m": c["vol_5m"], "vol_h1": c["vol_h1"],
            "vol_h6": c["vol_h6"], "vol_24h": c["vol_24h"],
            "liquidity": c["liquidity"], "pair_url": c["pair_url"],
            "txns": c["txns"], "boosts": boosts, "pair_data": c["pair_data"],
            "confidence": cs.total, "grade": cs.grade,
            "cs": cs, "entry_exit": entry_exit,
            "safety": c["safety"], "ta": c["ta"], "moonshot": moon,
        }
        results.append(entry)
        if moon.total >= 40:
            degen_results.append(entry)

    for c in degen_candidates:
        boosts = c.get("boosts", 0)
        try:
            boosts = int(boosts)
        except (ValueError, TypeError):
            boosts = 0

        moon = compute_moonshot(
            c["price_usd"], c["fdv"], c["h1"], c["h6"], c["h24"],
            c["vol_5m"], c["vol_h1"], c["vol_24h"], c["liquidity"],
            c["txns"], c["ta"], c["safety"],
        )

        if moon.total >= 40:
            entry_exit = compute_entry_exit(
                c["price_usd"], c["ta"],
                ConfidenceScore(safety_passed=False),
            )
            degen_results.append({
                "address": c["address"], "symbol": c["symbol"], "name": c["name"],
                "price_usd": c["price_usd"], "fdv": c["fdv"],
                "h1": c["h1"], "h6": c["h6"], "h24": c["h24"],
                "vol_5m": c["vol_5m"], "vol_h1": c["vol_h1"],
                "vol_h6": c["vol_h6"], "vol_24h": c["vol_24h"],
                "liquidity": c["liquidity"], "pair_url": c["pair_url"],
                "txns": c["txns"], "boosts": boosts, "pair_data": c["pair_data"],
                "confidence": 0, "grade": "F",
                "cs": ConfidenceScore(safety_passed=False),
                "entry_exit": entry_exit,
                "safety": c["safety"], "ta": c["ta"], "moonshot": moon,
            })

    results.sort(key=lambda r: -r["confidence"])
    degen_results.sort(key=lambda r: -r["moonshot"].total)

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

    stats["degen_plays"] = len(degen_results)
    stage_text.empty()
    return results, degen_results, stats


# ═══════════════════════════════════════════════════════════════════════════════
# RENDER HELPERS (defined before any UI code calls them)
# ═══════════════════════════════════════════════════════════════════════════════
def _render_token_card(r, compact=False):
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
        st.metric(f"Score {cs.total:.0f}/100", f"{r['grade']}-Grade")
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
                        "address": r["address"], "symbol": r["symbol"],
                        "name": r["name"], "entry_price": r["price_usd"],
                        "target_2x": r["price_usd"] * 2, "grade": r["grade"],
                        "confidence": cs.total, "pair_url": r["pair_url"],
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

    with st.expander(f"Full Analysis: {r['symbol']}"):
        d1, d2, d3 = st.columns(3)

        with d1:
            st.markdown("##### Entry & Exit Levels")
            if ee:
                st.markdown(
                    f"**Entry Zone:** {fmt_price(ee.get('entry_low', 0))} — "
                    f"{fmt_price(ee.get('entry_high', 0))}")
                st.markdown(
                    f"**Stop-Loss:** {fmt_price(ee.get('stop_loss', 0))} "
                    f"(-{ee.get('stop_loss_pct', 0)}%)")
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
                f"24h: {fmt_usd(r['vol_24h'])}")

        with d2:
            st.markdown("##### Technical Analysis")
            if ta.available:
                st.markdown(
                    f"**Fibonacci:** Near {ta.nearest_fib_level} level "
                    f"({ta.fib_proximity_pct:.1f}% away)")
                rsi_clr = GREEN if ta.rsi_signal == "OVERSOLD_BOUNCING" else (
                    BLUE if ta.rsi_signal == "OVERSOLD" else YELLOW)
                st.markdown(
                    f"**RSI:** 1m={ta.rsi_1m:.0f} · 5m={ta.rsi_5m:.0f} — "
                    f"<b style='color:{rsi_clr}'>{ta.rsi_signal}</b>",
                    unsafe_allow_html=True)
                vwap_clr = GREEN if ta.vwap_reclaim else (
                    BLUE if ta.price_vs_vwap_pct > 0 else RED)
                vwap_txt = "RECLAIMING" if ta.vwap_reclaim else (
                    f"{'Above' if ta.price_vs_vwap_pct > 0 else 'Below'} "
                    f"({ta.price_vs_vwap_pct:+.1f}%)")
                st.markdown(
                    f"**VWAP:** {fmt_price(ta.vwap)} — "
                    f"<b style='color:{vwap_clr}'>{vwap_txt}</b>",
                    unsafe_allow_html=True)
                vt_clr = GREEN if ta.volume_trend == "STRONG_RECOVERY" else (
                    BLUE if ta.volume_trend == "HEALTHY" else RED)
                st.markdown(
                    f"**Volume:** <b style='color:{vt_clr}'>{ta.volume_trend}</b> "
                    f"({ta.volume_recovery_ratio:.1f}x)",
                    unsafe_allow_html=True)
                ms_clr = GREEN if ta.momentum_signal == "STRONG_REVERSAL" else (
                    BLUE if ta.momentum_signal == "WEAK_REVERSAL" else RED)
                st.markdown(
                    f"**Momentum:** <b style='color:{ms_clr}'>{ta.momentum_signal}</b>",
                    unsafe_allow_html=True)
            else:
                st.caption("Birdeye OHLCV unavailable — using defaults.")

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
                ("Fib", cs.fib_score, 20), ("RSI", cs.rsi_score, 15),
                ("Volume", cs.volume_score, 20), ("Sentiment", cs.sentiment_score, 15),
                ("Holders", cs.holder_score, 10), ("VWAP", cs.vwap_score, 10),
                ("Momentum", cs.pattern_score, 10),
            ]
            for label, score, weight in components:
                bar_clr = GREEN if score >= 70 else (
                    BLUE if score >= 50 else (YELLOW if score >= 30 else RED))
                st.markdown(
                    f"{label} ({weight}%): **{score:.0f}** "
                    f"<span style='color:{bar_clr}'>{'█' * int(score / 10)}"
                    f"{'░' * (10 - int(score / 10))}</span>",
                    unsafe_allow_html=True)

    st.divider()


def _render_degen_card(r):
    moon = r["moonshot"]
    ee = r["entry_exit"]
    safety = r["safety"]
    m_clr = MOON_COLORS.get(moon.tier, GREY)
    r_clr = RISK_COLORS.get(moon.risk_level, RED)

    c1, c2, c3, c4 = st.columns([3, 2, 2, 4])

    with c1:
        st.markdown(
            f"<span class='grade-badge' style='background:{m_clr}20;"
            f"color:{m_clr};border:2px solid {m_clr}'>"
            f"{moon.multiplier_target}</span> "
            f"**{r['symbol']}** · {r['name'][:25]}",
            unsafe_allow_html=True)
        st.markdown(
            f"<span class='signal-tag' style='background:{r_clr}20;"
            f"color:{r_clr};border:1px solid {r_clr}'>"
            f"RISK: {moon.risk_level}</span>",
            unsafe_allow_html=True)
        st.caption(f"`{r['address'][:28]}...`")

    with c2:
        st.metric("Price", fmt_price(r["price_usd"]))
        st.caption(f"MCap: {fmt_usd(r['fdv'])}")

    with c3:
        st.metric(f"Moon Score {moon.total:.0f}/100", moon.tier)
        h1c = "positive" if r["h1"] >= 0 else "negative"
        h24c = "positive" if r["h24"] >= 0 else "negative"
        st.markdown(
            f"1h: <b class='{h1c}'>{r['h1']:+.1f}%</b> · "
            f"24h: <b class='{h24c}'>{r['h24']:+.1f}%</b>",
            unsafe_allow_html=True)

    with c4:
        if moon.reasons:
            st.markdown("**Why:** " + " · ".join(moon.reasons[:3]))
        if moon.warnings:
            st.markdown(
                f"<span style='color:{RED}'>⚠ "
                + " · ".join(moon.warnings[:2]) + "</span>",
                unsafe_allow_html=True)
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("Add to Watchlist", key=f"degen_{r['address']}",
                         use_container_width=True):
                wl = _load_json(WATCHLIST_FILE)
                if not any(w["address"] == r["address"] for w in wl):
                    wl.append({
                        "address": r["address"], "symbol": r["symbol"],
                        "name": r["name"], "entry_price": r["price_usd"],
                        "target_2x": r["price_usd"] * 2,
                        "grade": f"DEGEN-{moon.multiplier_target}",
                        "confidence": moon.total, "pair_url": r["pair_url"],
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

    with st.expander(f"Degen Analysis: {r['symbol']}"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown("##### Profit Targets")
            if ee:
                st.markdown(f"**Entry:** {fmt_price(ee.get('entry_low', 0))} — "
                            f"{fmt_price(ee.get('entry_high', 0))}")
                st.markdown(f"**5x:** {fmt_price(ee.get('target_5x', 0))}")
                st.markdown(f"**10x:** {fmt_price(ee.get('target_10x', 0))}")
                st.markdown(f"**100x:** {fmt_price(ee.get('target_100x', 0))}")
            st.markdown("---")
            st.caption(
                f"MCap now: {fmt_usd(r['fdv'])}\n\n"
                f"5x MCap: {fmt_usd(r['fdv'] * 5)}\n\n"
                f"10x MCap: {fmt_usd(r['fdv'] * 10)}")
        with d2:
            st.markdown("##### Moonshot Breakdown")
            components = [
                ("Dip depth", moon.dip_depth_score, 30),
                ("Micro-cap", moon.mcap_score, 25),
                ("Vol spike", moon.volume_spike_score, 20),
                ("Volatility", moon.volatility_score, 10),
                ("Momentum", moon.momentum_score, 10),
                ("Buy pressure", moon.buy_pressure_score, 5),
            ]
            for label, score, weight in components:
                bar_clr = GREEN if score >= 70 else (
                    BLUE if score >= 50 else (YELLOW if score >= 30 else RED))
                st.markdown(
                    f"{label} ({weight}%): **{score:.0f}** "
                    f"<span style='color:{bar_clr}'>{'█' * int(score / 10)}"
                    f"{'░' * (10 - int(score / 10))}</span>",
                    unsafe_allow_html=True)
        with d3:
            st.markdown("##### Risk Factors")
            for w in moon.warnings:
                st.markdown(f"<span style='color:{RED}'>⚠</span> {w}",
                            unsafe_allow_html=True)
            st.markdown("---")
            st.caption(
                f"Liq: {fmt_usd(r['liquidity'])} · Vol 24h: {fmt_usd(r['vol_24h'])}")

    st.divider()


def _render_crypto_gauge(score):
    if score >= 20:
        color = GREEN
    elif score <= -20:
        color = RED
    else:
        color = YELLOW

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "", "font": {"size": 36}},
        gauge={
            "axis": {"range": [-100, 100], "tickwidth": 1},
            "bar": {"color": color},
            "bgcolor": "#1a1a2e",
            "steps": [
                {"range": [-100, -60], "color": "#4a0000"},
                {"range": [-60, -20], "color": "#6a2020"},
                {"range": [-20, 20], "color": "#3a3a20"},
                {"range": [20, 60], "color": "#206a20"},
                {"range": [60, 100], "color": "#004a00"},
            ],
        },
    ))
    fig.update_layout(
        height=200, margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font={"color": "white"},
    )
    return fig


def _render_crypto_card(pred):
    dir_clr = GREEN if pred.direction == "BULLISH" else (
        RED if pred.direction == "BEARISH" else YELLOW)

    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown(
            f"### {pred.asset} "
            f"<span style='color:{dir_clr}'>{pred.direction}</span>",
            unsafe_allow_html=True)
        st.markdown(
            f"**Confidence:** {pred.confidence} · "
            f"**Score:** {pred.composite_score:+.0f}")
        st.plotly_chart(_render_crypto_gauge(pred.composite_score),
                        use_container_width=True, key=f"gauge_{pred.asset}")

    with c2:
        # The Play
        edge = pred.prediction_market_edge
        if edge and edge.edge_pct and abs(edge.edge_pct) > 10:
            play_clr = GREEN if edge.edge_pct > 0 else RED
            st.markdown(
                f"<div style='padding:12px;border-radius:8px;border:2px solid {play_clr};"
                f"background:{play_clr}15'>"
                f"<b>THE PLAY</b><br>{pred.suggested_play}"
                f"</div>",
                unsafe_allow_html=True)
            if edge.market_question:
                st.caption(
                    f"Market: {edge.market_question} · "
                    f"Market odds: {edge.market_odds:.0%} · "
                    f"Model: {edge.model_implied:.0%} · "
                    f"Edge: {edge.edge_pct:+.0f}%")
                if edge.market_url:
                    st.link_button("View on Polymarket", edge.market_url)
        else:
            st.info(
                f"**NO PLAY** — Model agrees with market pricing. "
                f"{pred.suggested_play}")

        # Signal breakdown
        with st.expander("Signal Breakdown"):
            if pred.signals:
                for sig in pred.signals:
                    s_clr = GREEN if sig.signal == "BULLISH" else (
                        RED if sig.signal == "BEARISH" else GREY)
                    bar_val = int((sig.raw_score + 100) / 200 * 10)
                    st.markdown(
                        f"**{sig.name}** ({sig.weight:.0%}): "
                        f"{sig.value} → "
                        f"<b style='color:{s_clr}'>{sig.signal}</b> "
                        f"({sig.raw_score:+.0f}) "
                        f"<span style='color:{s_clr}'>{'█' * max(bar_val, 0)}"
                        f"{'░' * max(10 - bar_val, 0)}</span>",
                        unsafe_allow_html=True)

    if pred.is_stale:
        st.warning("Data is >12 hours old. Refresh recommended.")
    st.caption(f"Updated: {pred.updated_at[:19]}Z")
    st.divider()


def _render_match_card(m):
    c1, c2, c3 = st.columns([3, 4, 3])

    with c1:
        st.markdown(f"### {m.home_team}")
        st.caption(f"ELO: {m.home_elo:.0f}")
        st.metric("Win %", f"{m.home_win_prob:.0%}")
        if m.best_home_odds > 0:
            st.caption(f"Best odds: {m.best_home_odds:.2f} ({m.best_home_bookmaker})")

    with c2:
        st.markdown(f"### vs")
        st.caption(f"{m.utc_date[:16]}Z · {m.competition}")
        st.metric("Draw %", f"{m.draw_prob:.0%}")
        if m.best_draw_odds > 0:
            st.caption(f"Best odds: {m.best_draw_odds:.2f} ({m.best_draw_bookmaker})")

        if m.home_score is not None and m.away_score is not None:
            st.markdown(f"**Score: {m.home_score} - {m.away_score}**")

    with c3:
        st.markdown(f"### {m.away_team}")
        st.caption(f"ELO: {m.away_elo:.0f}")
        st.metric("Win %", f"{m.away_win_prob:.0%}")
        if m.best_away_odds > 0:
            st.caption(f"Best odds: {m.best_away_odds:.2f} ({m.best_away_bookmaker})")

    # Value bets
    if m.value_bets:
        for vb in m.value_bets:
            edge = vb.get("edge", 0) * 100
            conf = vb.get("confidence", "Low")
            vb_clr = GREEN if conf == "High" else (BLUE if conf == "Medium" else YELLOW)
            outcome_label = {
                "home": m.home_team, "draw": "Draw", "away": m.away_team
            }.get(vb.get("outcome", ""), vb.get("outcome", ""))
            st.markdown(
                f"<div style='padding:8px;border-radius:6px;border:1px solid {vb_clr};"
                f"background:{vb_clr}15'>"
                f"<b>VALUE BET:</b> {outcome_label} @ {vb.get('decimal_odds', 0):.2f} "
                f"({vb.get('bookmaker', '?')}) — "
                f"Edge: {edge:+.1f}% · Kelly: {vb.get('kelly_fraction', 0):.1%} · "
                f"Confidence: {conf}"
                f"</div>",
                unsafe_allow_html=True)

    # Odds comparison table
    if m.all_bookmaker_odds:
        with st.expander("Odds Comparison"):
            rows = []
            for bk in m.all_bookmaker_odds:
                rows.append({
                    "Bookmaker": bk.get("bookmaker", "?"),
                    "Home": f"{bk.get('home', 0):.2f}",
                    "Draw": f"{bk.get('draw', 0):.2f}",
                    "Away": f"{bk.get('away', 0):.2f}",
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Memecoin Intel Platform", layout="wide")
st.markdown(
    "<style>"
    ".signal-tag{display:inline-block;padding:4px 12px;border-radius:16px;"
    "font-weight:700;font-size:13px;letter-spacing:.5px}"
    ".grade-badge{display:inline-block;padding:6px 16px;border-radius:20px;"
    "font-weight:900;font-size:18px;letter-spacing:1px}"
    ".positive{color:#00e676}.negative{color:#ff1744}"
    "</style>",
    unsafe_allow_html=True,
)

# ── Sidebar navigation ──────────────────────────────────────────────────────
page = st.sidebar.radio(
    "Navigate",
    ["Memecoin Scanner", "Crypto Predictions", "Football Value Plays"],
    index=0,
)
st.sidebar.markdown("---")
st.sidebar.caption(
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: MEMECOIN SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
if page == "Memecoin Scanner":
    st.markdown("# Memecoin Swing Recovery Scanner")
    st.caption(
        "DexScreener discovery → Rugcheck safety → Birdeye TA → Confidence scoring"
    )

    tab_scanner, tab_watchlist, tab_tradelog, tab_scoreboard = st.tabs(
        ["Scanner", "Watchlist", "Trade Log", "Signal Scoreboard"]
    )

    # ── TAB: Scanner ─────────────────────────────────────────────────────
    with tab_scanner:
        scan_clicked = st.button("Run Full Scan", type="primary",
                                 use_container_width=True)

        if scan_clicked:
            results, degen_results, stats = run_full_scan()
            _, sig_added = log_signals(results)
            _, degen_added = log_degen_signals(degen_results)
            if sig_added or degen_added:
                parts = []
                if sig_added:
                    parts.append(f"{sig_added} signal(s)")
                if degen_added:
                    parts.append(f"{degen_added} degen play(s)")
                st.toast(f"Logged {' + '.join(parts)} to scoreboard")

            st.session_state["scan_results"] = results
            st.session_state["degen_results"] = degen_results
            st.session_state["scan_stats"] = stats
            st.session_state["scan_time"] = datetime.now(timezone.utc).strftime(
                "%H:%M:%S UTC")

        results = st.session_state.get("scan_results", [])
        degen_results = st.session_state.get("degen_results", [])
        stats = st.session_state.get("scan_stats", {})
        scan_time = st.session_state.get("scan_time", "")

        if stats:
            s1, s2, s3, s4, s5, s6, s7 = st.columns(7)
            s1.metric("Discovered", stats.get("discovered", 0))
            s2.metric("Pre-filtered", stats.get("pre_filtered", 0))
            s3.metric("Safety OK", stats.get("safety_passed", 0))
            s4.metric("Blocked", stats.get("safety_failed", 0))
            s5.metric("Grade A", stats.get("grade_a", 0))
            s6.metric("Grade B", stats.get("grade_b", 0))
            s7.metric("Degen", stats.get("degen_plays", 0))

        if results or degen_results:
            grade_a = [r for r in results if r["grade"] == "A"]
            grade_b = [r for r in results if r["grade"] == "B"]
            grade_c = [r for r in results if r["grade"] == "C"]

            if grade_a:
                st.markdown(f"## BUY NOW — A-Grade ({len(grade_a)})")
                st.caption(f"Confidence {GRADE_A_MIN}+ | Scanned at {scan_time}")
                for r in grade_a:
                    _render_token_card(r)
            else:
                st.info(f"No A-grade tokens this scan ({scan_time}).")

            st.divider()

            if grade_b:
                st.markdown(f"## WATCH LIST — B-Grade ({len(grade_b)})")
                for r in grade_b:
                    _render_token_card(r)
            else:
                st.info("No B-grade tokens this scan.")

            if grade_c:
                with st.expander(f"C-Grade tokens ({len(grade_c)})"):
                    for r in grade_c:
                        _render_token_card(r, compact=True)

            st.divider()

            if degen_results:
                st.markdown(
                    f"## DEGEN PLAYS — High Risk / High Reward ({len(degen_results)})")
                st.caption(
                    "Includes tokens that FAILED safety checks. "
                    "Only bet what you can afford to lose.")
                for r in degen_results:
                    _render_degen_card(r)
            else:
                st.info("No degen plays found this scan.")

        elif not scan_clicked:
            st.info("Click **Run Full Scan** to start.")

    # ── TAB: Watchlist ───────────────────────────────────────────────────
    with tab_watchlist:
        st.markdown("### Watchlist")
        watchlist = _load_json(WATCHLIST_FILE)

        if not watchlist:
            st.info("Empty. Use Scanner to add tokens.")
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
                        st.session_state[cache_key] = {
                            "price": current_price,
                            "h1": h1, "h6": h6, "h24": h24,
                        }
                elif cache_key in st.session_state:
                    cached = st.session_state[cache_key]
                    current_price = cached.get("price", item["entry_price"])
                    h1 = cached.get("h1", 0)
                    h6 = cached.get("h6", 0)
                    h24 = cached.get("h24", 0)

                entry = item["entry_price"]
                change_pct = ((current_price - entry) / entry * 100) if entry > 0 else 0
                target = item.get("target_2x", entry * 2)
                progress_pct = (
                    min(max(current_price / target, 0), 1.0) if target > 0 else 0)

                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 2])
                with c1:
                    grade = item.get("grade", "?")
                    g_clr = GRADE_COLORS.get(grade, GREY)
                    st.markdown(
                        f"<span class='grade-badge' style='background:{g_clr}20;"
                        f"color:{g_clr};border:1px solid {g_clr}'>{grade}</span> "
                        f"**{item['symbol']}**",
                        unsafe_allow_html=True)
                with c2:
                    st.metric("Entry", fmt_price(entry))
                with c3:
                    st.metric("Current", fmt_price(current_price),
                              delta=f"{change_pct:+.1f}%",
                              delta_color="normal" if change_pct >= 0 else "inverse")
                with c4:
                    st.markdown(f"**2x Target:** {fmt_price(target)}")
                    st.progress(progress_pct, text=f"{progress_pct:.0%} to 2x")
                with c5:
                    if pair_url:
                        st.link_button("DexScreener", pair_url,
                                       key=f"wl_dex_{i}",
                                       use_container_width=True)
                    if st.button("Remove", key=f"rm_{i}",
                                 use_container_width=True):
                        to_remove.append(i)
                st.divider()

            if to_remove:
                watchlist = [w for j, w in enumerate(watchlist)
                             if j not in to_remove]
                _save_json(WATCHLIST_FILE, watchlist)
                st.rerun()

    # ── TAB: Trade Log ───────────────────────────────────────────────────
    with tab_tradelog:
        st.markdown("### Trade Log")
        trades = _load_json(TRADES_FILE)

        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        closed_trades = [t for t in trades if t.get("status") == "CLOSED"]

        realised_pnl = sum(_safe_float(t, "pnl_sol") for t in closed_trades)
        wins = [t for t in closed_trades if _safe_float(t, "pnl_sol") > 0]
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(trades))
        m2.metric("Open", len(open_trades))
        m3.metric("Win Rate", f"{win_rate:.0f}%")
        m4.metric("PnL", f"{realised_pnl:+.4f} SOL")

        with st.expander("Log a new trade", expanded=False):
            with st.form("trade_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                with fc1:
                    t_symbol = st.text_input("Symbol", placeholder="e.g. BONK")
                    t_address = st.text_input("Address")
                    t_entry_price = st.number_input(
                        "Entry price (USD)", min_value=0.0, format="%.12f")
                with fc2:
                    t_size_sol = st.number_input(
                        "Size (SOL)", min_value=0.0, value=1.0, step=0.5)
                    t_side = st.selectbox("Side", ["BUY", "SELL"])
                    t_notes = st.text_input("Notes")

                if st.form_submit_button("Log Trade", type="primary"):
                    if t_symbol and t_entry_price > 0:
                        trades.append({
                            "symbol": t_symbol.upper(),
                            "address": t_address,
                            "side": t_side,
                            "entry_price": t_entry_price,
                            "size_sol": t_size_sol,
                            "status": "OPEN",
                            "exit_price": None, "pnl_pct": None, "pnl_sol": None,
                            "notes": t_notes,
                            "opened_at": datetime.now(timezone.utc).isoformat(),
                            "closed_at": None,
                        })
                        _save_json(TRADES_FILE, trades)
                        st.success(f"Logged {t_side} {t_symbol.upper()}")
                        st.rerun()

        if trades:
            st.markdown("#### History")
            rows = []
            for t in reversed(trades):
                pnl_pct = t.get("pnl_pct")
                pnl_sol = t.get("pnl_sol")
                rows.append({
                    "Symbol": t.get("symbol", "?"),
                    "Side": t.get("side", "BUY"),
                    "Entry": fmt_price(t.get("entry_price", 0)),
                    "Exit": fmt_price(t["exit_price"]) if t.get("exit_price") else "—",
                    "Size": t.get("size_sol", 0),
                    "PnL %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
                    "PnL SOL": f"{pnl_sol:+.4f}" if pnl_sol is not None else "—",
                    "Status": t.get("status", "OPEN"),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True,
                         height=min(500, 50 + len(rows) * 38))

    # ── TAB: Signal Scoreboard ───────────────────────────────────────────
    with tab_scoreboard:
        st.markdown("### Signal Scoreboard — 2x ROI Tracker")
        all_signals = _load_json(SIGNALS_FILE)

        if st.button("Check 2x Hits Now", type="primary"):
            if all_signals:
                with st.spinner("Checking..."):
                    all_signals, new_hits, checked = check_2x_hits()
                if new_hits:
                    st.success(f"New 2x hits: {new_hits}")
                else:
                    st.info(f"No new hits (checked {checked})")

        if all_signals:
            hits = [s for s in all_signals if s.get("hit_2x")]
            pending = [s for s in all_signals if not s.get("hit_2x")]
            total = len(all_signals)
            hit_rate = (len(hits) / total * 100) if total > 0 else 0

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Total Signals", total)
            mc2.metric("2x Hits", len(hits))
            mc3.metric("Hit Rate", f"{hit_rate:.0f}%")

            if hits:
                st.markdown(f"#### 2x Hits ({len(hits)})")
                hit_rows = [{
                    "Symbol": s.get("symbol"), "Grade": s.get("grade"),
                    "Entry": fmt_price(s.get("signal_price", 0)),
                    "Hit Price": fmt_price(s.get("hit_2x_price", 0)),
                    "Signal Time": s.get("signal_time", "")[:16],
                } for s in hits]
                st.dataframe(pd.DataFrame(hit_rows), hide_index=True)

            if pending:
                st.markdown(f"#### Pending ({len(pending)})")
                pend_rows = [{
                    "Symbol": s.get("symbol"), "Grade": s.get("grade"),
                    "Entry": fmt_price(s.get("signal_price", 0)),
                    "Peak ROI": f"{s.get('peak_roi_pct', 0):+.1f}%",
                    "Signal Time": s.get("signal_time", "")[:16],
                } for s in pending]
                st.dataframe(pd.DataFrame(pend_rows), hide_index=True)

            st.markdown("#### Hit Rate by Grade")
            for grade in ("A", "B", "C"):
                typed = [s for s in all_signals if s.get("grade") == grade]
                typed_hits = [s for s in typed if s.get("hit_2x")]
                rate = (len(typed_hits) / len(typed) * 100) if typed else 0
                g_clr = GRADE_COLORS.get(grade, GREY)
                st.markdown(
                    f"**Grade {grade}**: {len(typed_hits)}/{len(typed)} "
                    f"(<b style='color:{g_clr}'>{rate:.0f}%</b>)",
                    unsafe_allow_html=True)

            if st.button("Clear Signal History"):
                _save_json(SIGNALS_FILE, [])
                st.rerun()
        else:
            st.info("No signals yet. Run a scan first.")

        # ── Degen Scoreboard ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Degen Plays Scoreboard — 5x/10x/100x Tracker")

        degen_signals = _load_json(DEGEN_SIGNALS_FILE)

        if st.button("Check Degen Hits", type="primary"):
            if degen_signals:
                with st.spinner("Checking..."):
                    degen_signals, d_hits, d_checked = check_degen_hits()
                if d_hits:
                    st.success(f"New milestone hits: {d_hits}")
                else:
                    st.info(f"No new hits (checked {d_checked})")

        if degen_signals:
            d_5x = [s for s in degen_signals if s.get("hit_5x")]
            d_10x = [s for s in degen_signals if s.get("hit_10x")]
            d_100x = [s for s in degen_signals if s.get("hit_100x")]

            dm1, dm2, dm3, dm4 = st.columns(4)
            dm1.metric("Total Plays", len(degen_signals))
            dm2.metric("5x Hits", len(d_5x))
            dm3.metric("10x Hits", len(d_10x))
            dm4.metric("100x Hits", len(d_100x))

            if d_5x:
                st.markdown(f"#### Milestone Hits")
                hit_rows = [{
                    "Symbol": s.get("symbol"), "Tier": s.get("tier"),
                    "Entry": fmt_price(s.get("signal_price", 0)),
                    "Peak Multi": f"{s.get('peak_multiplier', 1):.1f}x",
                } for s in d_5x]
                st.dataframe(pd.DataFrame(hit_rows), hide_index=True)

            if st.button("Clear Degen History"):
                _save_json(DEGEN_SIGNALS_FILE, [])
                st.rerun()
        else:
            st.info("No degen plays recorded yet.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: CRYPTO PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Crypto Predictions":
    st.markdown("# Crypto Prediction Plays")
    st.caption(
        "Aggregates RSI, MA crossovers, MACD, volume, Fear & Greed, funding rates, "
        "TVL, and prediction market odds into a composite directional score. "
        "Compares model probability vs Polymarket to find mispriced bets."
    )

    refresh_crypto = st.button("Refresh Predictions", type="primary",
                               use_container_width=True)

    if refresh_crypto:
        with st.spinner("Fetching data from CoinGecko, Binance, DeFiLlama, Polymarket..."):
            predictions = get_all_predictions()
            st.session_state["crypto_predictions"] = predictions
            for pred in predictions:
                log_prediction(pred)
            st.toast(f"Updated predictions for {len(predictions)} assets")

    predictions = st.session_state.get("crypto_predictions", [])

    if predictions:
        # Summary metrics
        bullish = [p for p in predictions if p.direction == "BULLISH"]
        bearish = [p for p in predictions if p.direction == "BEARISH"]
        plays = [p for p in predictions
                 if p.prediction_market_edge and abs(p.prediction_market_edge.edge_pct or 0) > 10]

        pm1, pm2, pm3, pm4 = st.columns(4)
        pm1.metric("Assets Tracked", len(predictions))
        pm2.metric("Bullish", len(bullish))
        pm3.metric("Bearish", len(bearish))
        pm4.metric("Active Plays", len(plays))

        st.divider()

        for pred in predictions:
            _render_crypto_card(pred)

        # Historical accuracy
        st.markdown("---")
        st.markdown("### Historical Accuracy")
        history = get_prediction_history()
        if history:
            st.caption(f"{len(history)} predictions logged. "
                       "Accuracy tracking requires time for predictions to resolve.")
            hist_rows = [{
                "Asset": h.get("asset", "?"),
                "Score": f"{h.get('composite_score', 0):+.0f}",
                "Direction": h.get("direction", "?"),
                "Confidence": h.get("confidence", "?"),
                "Time": h.get("updated_at", "")[:16],
            } for h in history[-20:]]
            st.dataframe(pd.DataFrame(hist_rows), hide_index=True)
        else:
            st.info("No prediction history yet. Refresh to generate first predictions.")

    else:
        st.info(
            "Click **Refresh Predictions** to fetch live data and generate "
            "directional signals for BTC, ETH, SOL, and DOGE."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3: FOOTBALL VALUE PLAYS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Football Value Plays":
    st.markdown("# World Cup & Football — Value Plays")
    st.caption(
        "ELO-based match predictions compared against bookmaker odds. "
        "Finds value bets where model probability diverges from market pricing."
    )

    comp_col, btn_col = st.columns([2, 1])
    with comp_col:
        competition = st.selectbox(
            "Competition",
            ["WC", "CL", "PL", "BL1", "SA", "FL1", "PD", "EC"],
            format_func=lambda x: {
                "WC": "FIFA World Cup", "CL": "Champions League",
                "PL": "Premier League", "BL1": "Bundesliga",
                "SA": "Serie A", "FL1": "Ligue 1",
                "PD": "La Liga", "EC": "European Championship",
            }.get(x, x),
        )
    with btn_col:
        refresh_football = st.button("Refresh Matches", type="primary",
                                     use_container_width=True)

    if refresh_football:
        with st.spinner("Fetching fixtures and odds..."):
            matches = get_match_predictions(competition)
            st.session_state["football_matches"] = matches
            st.session_state["football_comp"] = competition
            st.toast(f"Found {len(matches)} matches")

    matches = st.session_state.get("football_matches", [])

    if matches:
        value_matches = [m for m in matches if m.value_bets]
        scheduled = [m for m in matches if m.status in ("SCHEDULED", "TIMED")]
        finished = [m for m in matches if m.status == "FINISHED"]

        fm1, fm2, fm3 = st.columns(3)
        fm1.metric("Total Matches", len(matches))
        fm2.metric("Value Bets Found", sum(len(m.value_bets) for m in matches))
        fm3.metric("Upcoming", len(scheduled))

        st.divider()

        # Value bets section
        if value_matches:
            st.markdown(f"## Value Bets ({len(value_matches)} matches)")
            st.caption("Matches where model probability significantly exceeds market odds.")
            for m in value_matches:
                _render_match_card(m)

        # Upcoming matches
        if scheduled:
            st.markdown(f"## Upcoming Matches ({len(scheduled)})")
            for m in scheduled[:20]:
                _render_match_card(m)

        # Recent results
        if finished:
            with st.expander(f"Recent Results ({len(finished)})"):
                for m in finished[:10]:
                    _render_match_card(m)
    else:
        st.info(
            "Click **Refresh Matches** to fetch fixtures, odds, and predictions. "
            "Make sure FOOTBALL_DATA_API_KEY and ODDS_API_KEY are configured."
        )


# ── Footer ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.caption("Memecoin Intel Platform v2")
