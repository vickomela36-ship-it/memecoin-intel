#!/usr/bin/env bash
# run_hourly.sh — called by cron every hour.
# Checks the Notion DB for unprocessed buy signals and emails them.
# Log output → /home/user/memecoin-intel/logs/hourly.log

set -euo pipefail

REPO="/home/user/memecoin-intel"
LOG="$REPO/logs/hourly.log"

mkdir -p "$REPO/logs"

{
  echo "=== $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  cd "$REPO"
  python3 notifier.py
  echo ""
} >> "$LOG" 2>&1
