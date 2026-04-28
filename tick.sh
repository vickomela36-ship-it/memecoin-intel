#!/usr/bin/env bash
set -euo pipefail
cd /home/user/memecoin-intel
result=$(python3 check_signals.py 2>&1)
count=$(echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(len(d.get('buy_now', [])))
" 2>/dev/null || echo "ERR")
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "HOURLY_TICK count=$count ts=$ts"
# Emit one line per buy-now token for easy parsing
echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d.get('buy_now', []):
    fields = '|'.join([
        r.get('symbol',''), r.get('token',''), r.get('price_usd',''),
        r.get('change_1h',''), r.get('change_24h',''), r.get('volume_24h',''),
        r.get('liquidity_usd',''), r.get('buy_pressure',''),
        r.get('dexscreener_url',''), r.get('change_6h',''),
    ])
    print('BUY:' + fields)
" 2>/dev/null || true
