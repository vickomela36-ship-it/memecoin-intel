#!/usr/bin/env bash
# Hourly signal check runner — called by cron.
# Writes JSON output to /tmp/memecoin_signals.json for the monitor to pick up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="/tmp/memecoin_signals.json"

python "$SCRIPT_DIR/signals.py" > "$OUT" 2>/tmp/memecoin_signals_err.log
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) signals written to $OUT"
