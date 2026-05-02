#!/usr/bin/env bash
# Runs watcher.py every hour. Start with: bash run_watcher_loop.sh &
# Or add to systemd / supervisor as a persistent service.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/logs/watcher.log"
mkdir -p "$SCRIPT_DIR/logs"

echo "[loop] started at $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

while true; do
    python "$SCRIPT_DIR/watcher.py" 2>&1 | tee -a "$LOG"
    echo "[loop] sleeping 3600s — next run at $(date -u -d '+1 hour' +%H:%M:%SZ 2>/dev/null || date -u -v+1H +%H:%M:%SZ)" | tee -a "$LOG"
    sleep 3600
done
