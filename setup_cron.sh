#!/usr/bin/env bash
# Installs a cron job that runs run_check.py every hour.
# Run once: bash setup_cron.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
LOG="$SCRIPT_DIR/signal_check.log"
CRON_LINE="0 * * * * cd \"$SCRIPT_DIR\" && $PYTHON run_check.py >> \"$LOG\" 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -qF "run_check.py"; then
    echo "Cron job already installed."
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron job installed: runs every hour."
    echo "  $CRON_LINE"
fi

echo "Current crontab:"
crontab -l
