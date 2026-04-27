#!/usr/bin/env bash
# Install the hourly cron job (works on systems with crontab).
# On containerized / systemd-less environments use scheduler.py instead.
#
# Usage: bash setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
CRON_LINE="0 * * * * cd \"$SCRIPT_DIR\" && $PYTHON runner.py >> \"$SCRIPT_DIR/signal_runner.log\" 2>&1"

echo "Attempting to install cron job:"
echo "  $CRON_LINE"
echo

if ! command -v crontab &>/dev/null; then
    echo "crontab not found on this system."
    echo "Use the Python scheduler instead:"
    echo "  nohup python3 scheduler.py &"
    echo "  echo PID=\$! > scheduler.pid"
    exit 0
fi

if crontab -l 2>/dev/null | grep -qF "runner.py"; then
    echo "Cron job already exists — no changes made."
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron job installed. Verify with: crontab -l"
fi
