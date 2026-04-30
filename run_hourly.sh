#!/usr/bin/env bash
# Sourced by cron so env vars are available to signal_runner.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load credentials if a .env file exists
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

mkdir -p "$SCRIPT_DIR/logs"
LOG="$SCRIPT_DIR/logs/runner_$(date +%Y%m%d).log"

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] --- hourly run ---" >> "$LOG"
cd "$SCRIPT_DIR"
python signal_runner.py >> "$LOG" 2>&1
