#!/usr/bin/env bash
# Installs an hourly cron job to run the memecoin signal checker.
# Usage:
#   ./setup_cron.sh                          # uses system python3
#   ./setup_cron.sh /path/to/venv/bin/python # uses venv python

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${1:-python3}"
LOG="$SCRIPT_DIR/memecoin.log"
CRON_CMD="$PYTHON $SCRIPT_DIR/run_check.py >> $LOG 2>&1"
CRON_LINE="0 * * * * $CRON_CMD"

if crontab -l 2>/dev/null | grep -qF "run_check.py"; then
    echo "Cron job already installed — no changes made."
    crontab -l | grep "run_check.py"
    exit 0
fi

(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
echo "Cron job installed:"
echo "  $CRON_LINE"
echo "Logs: $LOG"
