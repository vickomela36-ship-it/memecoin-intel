#!/usr/bin/env bash
# Installs a daily cron job that runs the memecoin signal scanner at 08:00 UTC.
# Run once: bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
CRON_CMD="0 8 * * * cd \"$SCRIPT_DIR\" && $PYTHON runner.py >> \"$SCRIPT_DIR/runner.log\" 2>&1"

# Remove any existing entry for this runner, then add the new one
( crontab -l 2>/dev/null | grep -v "memecoin-intel/runner.py" ; echo "$CRON_CMD" ) | crontab -

echo "Cron job installed. The scanner will run daily at 08:00 UTC."
echo "Current crontab:"
crontab -l
