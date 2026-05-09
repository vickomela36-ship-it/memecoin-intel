#!/usr/bin/env bash
# Run once to install the daily cron job for memecoin-intel.
# The job fires at 09:00 AM server local time every day.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(command -v python3)"
LOG="$PROJECT_DIR/cron.log"
CRON_LINE="0 9 * * * cd \"$PROJECT_DIR\" && \"$PYTHON\" daily_runner.py >> \"$LOG\" 2>&1"

# Append only if not already present
if crontab -l 2>/dev/null | grep -qF "daily_runner.py"; then
  echo "Cron job already installed:"
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "Cron job installed (runs daily at 09:00 AM):"
fi

crontab -l | grep "daily_runner.py"
echo ""
echo "To remove it later run:  crontab -e"
echo "Logs will appear in:     $LOG"
