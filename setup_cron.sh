#!/usr/bin/env bash
# Installs a daily 09:00 UTC cron job that runs run_daily.py.
# Run once after setting up your .env file:  bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
LOG="$SCRIPT_DIR/memecoin_intel.log"

JOB="0 9 * * * cd \"$SCRIPT_DIR\" && \"$PYTHON\" run_daily.py >> \"$LOG\" 2>&1"

# Add the job only if it isn't already present
if crontab -l 2>/dev/null | grep -qF "run_daily.py"; then
    echo "Cron job already installed — no changes made."
else
    ( crontab -l 2>/dev/null; echo "$JOB" ) | crontab -
    echo "Cron job installed: runs daily at 09:00 UTC."
    echo "  Script : $SCRIPT_DIR/run_daily.py"
    echo "  Log    : $LOG"
fi

echo ""
echo "Current crontab:"
crontab -l
