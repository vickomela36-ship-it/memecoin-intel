#!/usr/bin/env bash
# Installs (or replaces) the hourly cron job for run_signals.py.
# Run once after cloning / setting up the project:
#   bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$(command -v python3)}"
LOG_DIR="$SCRIPT_DIR/logs"
CRON_CMD="0 * * * * cd \"$SCRIPT_DIR\" && \"$PYTHON\" run_signals.py >> \"$LOG_DIR/signals.log\" 2>&1"
MARKER="run_signals.py"

mkdir -p "$LOG_DIR"

# Remove any existing entry for this script, then add the new one.
( crontab -l 2>/dev/null | grep -v "$MARKER"; echo "$CRON_CMD" ) | crontab -

echo "Cron job installed. Runs every hour on the hour."
echo "Logs → $LOG_DIR/signals.log"
echo ""
echo "Current crontab:"
crontab -l
