#!/usr/bin/env bash
# Adds an hourly cron job for the signal runner.
# Run once: bash setup_cron.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_CMD="0 * * * * cd $SCRIPT_DIR && python3 runner.py >> $SCRIPT_DIR/runner.log 2>&1"

# Add only if not already present
( crontab -l 2>/dev/null | grep -qF "runner.py" ) && {
  echo "Cron job already exists."
  exit 0
}

( crontab -l 2>/dev/null; echo "$CRON_CMD" ) | crontab -
echo "Cron job installed:"
echo "  $CRON_CMD"
