#!/bin/bash
# Runs every hour via cron. Filters 'buy now' signals and appends to log.
cd /home/user/memecoin-intel

python signals.py 2>/tmp/memecoin_err.log | python3 - <<'PYEOF'
import json, sys

try:
    signals = json.load(sys.stdin)
except Exception as e:
    print(json.dumps({"error": str(e), "raw": sys.stdin.read()}))
    sys.exit(1)

for s in signals:
    if s.get("signal") == "buy now":
        print(json.dumps(s), flush=True)
PYEOF
