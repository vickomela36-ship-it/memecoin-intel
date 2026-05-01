#!/usr/bin/env bash
set -euo pipefail
LOG=/home/user/memecoin-intel/signals.log
cd /home/user/memecoin-intel
output=$(python signals.py 2>&1) || true
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$output" | python3 -c "
import sys, json, os
ts = os.environ.get('TS', '')
try:
    data = json.load(sys.stdin)
    for s in data:
        if s.get('signal') == 'buy now':
            print('BUY_NOW:' + json.dumps(s), flush=True)
    print('HEARTBEAT:' + ts, flush=True)
except:
    print('HEARTBEAT:' + ts + ':parse_error', flush=True)
" TS="$ts" >> "$LOG" 2>&1
