#!/usr/bin/env bash
# Adds a cron job to run scheduler.py --once every hour.
# Run once: bash setup_cron.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(command -v python3)"
CRON_LINE="0 * * * * cd $REPO_DIR && $PYTHON scheduler.py --once >> $REPO_DIR/memecoin_intel.log 2>&1"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -qF "scheduler.py --once"; then
    echo "Cron job already installed."
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron job installed:"
    echo "  $CRON_LINE"
fi
