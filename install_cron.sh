#!/usr/bin/env bash
# Installs an hourly cron job that runs the memecoin signal checker.
# Run once after setting up config.py:
#   chmod +x install_cron.sh && ./install_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
LOG_FILE="/tmp/memecoin-checker.log"

CRON_LINE="0 * * * * cd \"$SCRIPT_DIR\" && $PYTHON run_checker.py >> $LOG_FILE 2>&1"

# Remove any existing entry for run_checker.py, then add the fresh line
( crontab -l 2>/dev/null | grep -v "run_checker.py" ; echo "$CRON_LINE" ) | crontab -

echo ""
echo "✓ Hourly cron job installed:"
echo "  $CRON_LINE"
echo ""
echo "Logs  : $LOG_FILE"
echo "Verify: crontab -l"
echo "Remove: crontab -l | grep -v run_checker.py | crontab -"
