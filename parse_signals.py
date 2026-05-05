"""
Reads check_signals.py JSON from stdin and prints structured event lines.
BUY_NOW|symbol|token|price_usd|change_1h|change_6h|change_24h|volume_24h|liquidity_usd|buy_pressure|dexscreener_url
TICK_NO_SIGNAL|HH:MM UTC
SIGNAL_ERROR|message
"""
import sys, json, datetime

try:
    d = json.load(sys.stdin)
    err = d.get("error")
    if err:
        print(f"SIGNAL_ERROR|{err}")
    else:
        bn = d.get("buy_now", [])
        for t in bn:
            parts = "|".join([
                t.get("symbol", ""), t.get("token", ""), t.get("price_usd", ""),
                t.get("change_1h", ""), t.get("change_6h", ""), t.get("change_24h", ""),
                t.get("volume_24h", ""), t.get("liquidity_usd", ""),
                t.get("buy_pressure", ""), t.get("dexscreener_url", ""),
            ])
            print("BUY_NOW|" + parts)
        if not bn:
            ts = datetime.datetime.utcnow().strftime("%H:%M UTC")
            print(f"TICK_NO_SIGNAL|{ts}")
except Exception as e:
    print(f"PARSE_ERROR|{e}")
