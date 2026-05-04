#!/usr/bin/env bash
# Hourly runner — called by cron.  Logs to /tmp/memecoin-intel.log
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/memecoin-intel.log"

echo "──────────────────────────────────────────" >> "$LOG"
echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') — scan start" >> "$LOG"

cd "$DIR"
python3 main.py >> "$LOG" 2>&1

echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') — scan end" >> "$LOG"
