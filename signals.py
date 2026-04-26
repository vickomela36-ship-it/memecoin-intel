#!/usr/bin/env python3
"""
signals.py — Memecoin buy/sell signal generator.

TWO MODES:
  1. NETWORK MODE (default): fetches live data from DexScreener.
     Run this on a machine where DexScreener is reachable (e.g. your laptop).
     Outputs a scored signal as JSON and, if NOTION_TOKEN is set, writes
     the result to the Memecoin Buy Signals Log database automatically.

  2. NOTION-POLL MODE (--poll): no market API needed.
     Reads the most recent unprocessed row from the Notion database.
     Use this on the server to check whether a new signal was logged remotely.

Usage:
    python3 signals.py                  # network mode, print JSON
    python3 signals.py --poll           # notion-poll mode, print JSON
    python3 signals.py --demo           # dry-run with synthetic data (for testing)

Environment variables (copy to config.py or export before running):
    NOTION_TOKEN          Notion integration secret (starts with ntn_...)
    NOTION_DB_ID          Notion database ID (from the DB URL)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
try:
    from config import NOTION_TOKEN, NOTION_DB_ID
except ImportError:
    NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    NOTION_DB_ID = os.getenv("NOTION_DB_ID", "5ee05dca-c8a4-463f-bf56-39a2eb08f364")

# ── DexScreener constants ────────────────────────────────────────────────────
DEXSCREENER_BOOSTS  = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS  = "https://api.dexscreener.com/latest/dex/tokens/{addr}"
BUY_SCORE_THRESHOLD = 70
MIN_LIQUIDITY_USD   = 50_000
MIN_VOLUME_24H_USD  = 100_000
DUMP_GUARD_1H       = -15.0
TOP_BOOST_LIMIT     = 25


# ── Helpers ──────────────────────────────────────────────────────────────────
def _http(url: str, method: str = "GET", data: bytes | None = None,
          headers: dict | None = None) -> dict:
    h = {"User-Agent": "memecoin-intel/1.0", "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


# ── Signal scoring (shared between modes) ───────────────────────────────────
def _score(pair: dict) -> tuple[int, str]:
    score   = 0
    reasons = []

    ch  = pair.get("priceChange") or {}
    vol = pair.get("volume")      or {}
    liq = pair.get("liquidity")   or {}
    txn = (pair.get("txns") or {}).get("h1") or {}

    h1    = float(ch.get("h1",  0) or 0)
    h6    = float(ch.get("h6",  0) or 0)
    v24   = float(vol.get("h24", 0) or 0)
    lusd  = float(liq.get("usd", 0) or 0)
    buys  = int(txn.get("buys",  0) or 0)
    sells = int(txn.get("sells", 0) or 0)

    if h1 > 10:
        score += 25; reasons.append(f"+{h1:.1f}% (1h)")
    elif h1 > 5:
        score += 15; reasons.append(f"+{h1:.1f}% (1h)")
    elif h1 > 0:
        score +=  5; reasons.append(f"+{h1:.1f}% (1h)")
    elif h1 < DUMP_GUARD_1H:
        score -= 20; reasons.append(f"{h1:.1f}% drop (1h)")

    if h6 > 20:
        score += 20; reasons.append(f"+{h6:.1f}% (6h)")
    elif h6 > 5:
        score += 10; reasons.append(f"+{h6:.1f}% (6h)")

    if v24 >= 1_000_000:
        score += 20; reasons.append(f"${v24/1e6:.1f}M vol")
    elif v24 >= 500_000:
        score += 15; reasons.append(f"${v24/1e3:.0f}K vol")
    elif v24 >= MIN_VOLUME_24H_USD:
        score +=  8; reasons.append(f"${v24/1e3:.0f}K vol")
    else:
        score -= 10; reasons.append("low volume")

    if lusd >= MIN_LIQUIDITY_USD:
        score += 15; reasons.append(f"${lusd/1e3:.0f}K liq")
    else:
        score -= 15; reasons.append("thin liquidity")

    total = buys + sells
    if total > 0:
        ratio = buys / total
        if ratio > 0.65:
            score += 20; reasons.append(f"{ratio*100:.0f}% buys (1h)")
        elif ratio > 0.50:
            score += 10; reasons.append(f"{ratio*100:.0f}% buys (1h)")
        elif ratio < 0.35:
            score -= 10; reasons.append(f"sell pressure {(1-ratio)*100:.0f}%")

    return max(0, min(100, score)), "; ".join(reasons)


# ── MODE 1: Live DexScreener ─────────────────────────────────────────────────
def signal_from_dexscreener() -> dict:
    entries = _http(DEXSCREENER_BOOSTS)
    if isinstance(entries, dict):
        entries = entries.get("pairs", [])

    best: dict | None = None
    best_score = -1

    for entry in entries[:TOP_BOOST_LIMIT]:
        addr = entry.get("tokenAddress", "")
        if not addr:
            continue
        try:
            pairs = _http(DEXSCREENER_TOKENS.format(addr=addr)).get("pairs") or []
        except Exception:
            continue
        if not pairs:
            continue

        pairs.sort(
            key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0),
            reverse=True,
        )
        pair = pairs[0]
        lusd = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
        v24  = float((pair.get("volume")    or {}).get("h24", 0) or 0)
        h1   = float((pair.get("priceChange") or {}).get("h1", 0) or 0)

        if lusd < MIN_LIQUIDITY_USD or v24 < MIN_VOLUME_24H_USD or h1 < DUMP_GUARD_1H:
            continue

        score, reason = _score(pair)
        if score > best_score:
            best_score = score
            base = pair.get("baseToken") or {}
            best = {
                "token":     f"{base.get('name','?')} ({base.get('symbol','?')})",
                "price":     float(pair.get("priceUsd", 0) or 0),
                "score":     score,
                "reason":    reason,
                "signal":    "buy now" if score >= BUY_SCORE_THRESHOLD else "hold",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source":    "dexscreener",
            }

    return best or {
        "token": "N/A", "price": 0.0, "score": 0,
        "reason": "No qualifying tokens found", "signal": "hold",
        "timestamp": datetime.now(timezone.utc).isoformat(), "source": "dexscreener",
    }


# ── MODE 2: Poll Notion for unprocessed buy signals ──────────────────────────
def signal_from_notion() -> dict:
    """
    Queries the Notion DB for the most recent 'buy now' row where Email Sent = false.
    Returns that signal (so the notifier can email+mark it), or a hold signal.
    """
    if not NOTION_TOKEN:
        return {"signal": "error", "error": "NOTION_TOKEN not set",
                "timestamp": datetime.now(timezone.utc).isoformat()}

    since = (datetime.now(timezone.utc) - timedelta(hours=2)).date().isoformat()
    payload = json.dumps({
        "filter": {
            "and": [
                {"property": "Email Sent", "checkbox": {"equals": False}},
                {"property": "Timestamp",  "date": {"on_or_after": since}},
            ]
        },
        "sorts": [{"property": "Timestamp", "direction": "descending"}],
        "page_size": 1,
    }).encode()

    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    try:
        resp = _http(url, method="POST", data=payload, headers=_notion_headers())
    except Exception as exc:
        return {"signal": "error", "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat()}

    results = resp.get("results", [])
    if not results:
        return {
            "token": "N/A", "price": 0.0, "score": 0,
            "reason": "No unprocessed buy signals in Notion",
            "signal": "hold",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "notion_poll",
        }

    row = results[0]
    props = row.get("properties", {})

    def text_val(p):
        v = props.get(p, {})
        for t in ["rich_text", "title"]:
            parts = v.get(t, [])
            if parts:
                return "".join(c.get("plain_text", "") for c in parts)
        return ""

    def num_val(p):
        return (props.get(p) or {}).get("number") or 0

    def date_val(p):
        return ((props.get(p) or {}).get("date") or {}).get("start") or ""

    signal_title = text_val("Signal") or ""

    return {
        "notion_page_id": row["id"],
        "token":     text_val("Token"),
        "price":     num_val("Price"),
        "score":     num_val("Score"),
        "reason":    text_val("Reason"),
        "signal":    "buy now" if "buy" in signal_title.lower() else signal_title.lower(),
        "timestamp": date_val("Timestamp") or datetime.now(timezone.utc).isoformat(),
        "source":    "notion_poll",
    }


# ── MODE 3: Demo (synthetic data for testing) ────────────────────────────────
def signal_demo() -> dict:
    return {
        "token":     "DEMO TOKEN (DEMO)",
        "price":     0.000042,
        "score":     82,
        "reason":    "+12.3% (1h); +31.5% (6h); $2.1M vol; $450K liq; 73% buys (1h)",
        "signal":    "buy now",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source":    "demo",
    }


# ── Write signal to Notion (used in network mode) ────────────────────────────
def log_to_notion(sig: dict) -> str | None:
    """Creates a new row in the Notion DB. Returns the page ID or None on error."""
    if not NOTION_TOKEN:
        return None
    payload = json.dumps({
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Signal":    {"title": [{"text": {"content": sig["signal"].title()}}]},
            "Token":     {"rich_text": [{"text": {"content": sig.get("token","")}}]},
            "Price":     {"number": sig.get("price", 0)},
            "Score":     {"number": sig.get("score", 0)},
            "Reason":    {"rich_text": [{"text": {"content": sig.get("reason","")}}]},
            "Email Sent":{"checkbox": False},
            "Timestamp": {"date": {"start": sig.get("timestamp","")[:10]}},
        },
    }).encode()
    try:
        resp = _http("https://api.notion.com/v1/pages", method="POST",
                     data=payload, headers=_notion_headers())
        return resp.get("id")
    except Exception as exc:
        print(f"[notion] write failed: {exc}", file=sys.stderr)
        return None


# ── Entry point ───────────────────────────────────────────────────────────────
def get_signal(mode: str = "network") -> dict:
    if mode == "demo":
        return signal_demo()
    if mode == "poll":
        return signal_from_notion()
    return signal_from_dexscreener()


if __name__ == "__main__":
    mode = "network"
    if "--poll" in sys.argv:
        mode = "poll"
    elif "--demo" in sys.argv:
        mode = "demo"

    sig = get_signal(mode)

    if mode == "network" and sig.get("signal") == "buy now":
        page_id = log_to_notion(sig)
        if page_id:
            sig["notion_page_id"] = page_id

    print(json.dumps(sig, indent=2))
    sys.exit(0 if sig.get("signal") == "buy now" else 1)
